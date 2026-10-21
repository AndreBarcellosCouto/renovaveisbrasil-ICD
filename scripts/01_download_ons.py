"""Download dos conjuntos do ONS (bucket S3 público) e da API de Carga Verificada.

Uso:
  python scripts/01_download_ons.py --meses 2021-08 2025-08      # piloto
  python scripts/01_download_ons.py --inicio 2019-01 --fim 2026-08
  python scripts/01_download_ons.py --meses 2025-08 --so geracao_usina carga_api

Idempotente: não baixa o que já está no manifesto (use --force para rebaixar).
Descobre os nomes exatos dos arquivos listando o prefixo no S3 (parquet preferido, CSV como
alternativa), e baixa os dicionários de dados (JSON/PDF) de cada prefixo.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

import config as C
from common import LOG, BlockedByNetwork, download, http_get, in_manifest, manifest_add, parse_months

S3NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def s3_list(prefix: str) -> dict[str, dict]:
    """Lista as chaves diretamente sob o prefixo: {nome_arquivo: {size, last_modified, key}}.
    delimiter=/ evita descer em sub-prefixos (ex.: ear_subsistema_di/precipitacao_estacao_di/),
    cujos objetos podem ser privados (403)."""
    out: dict[str, dict] = {}
    token = None
    while True:
        url = f"{C.ONS_S3}/?list-type=2&prefix={prefix}/&delimiter=/&max-keys=1000"
        if token:
            url += f"&continuation-token={requests_quote(token)}"
        r = http_get(url)
        root = ET.fromstring(r.content)
        for c in root.findall(f"{S3NS}Contents"):
            key = c.find(f"{S3NS}Key").text
            name = key.split("/")[-1]
            if not name:
                continue
            out[name] = dict(key=key, size=int(c.find(f"{S3NS}Size").text),
                             last_modified=c.find(f"{S3NS}LastModified").text)
        trunc = root.find(f"{S3NS}IsTruncated")
        if trunc is not None and trunc.text == "true":
            token = root.find(f"{S3NS}NextContinuationToken").text
        else:
            return out


def requests_quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


def pick(listing: dict[str, dict], stem: str) -> str | None:
    """Escolhe parquet, senão csv, para um nome-base."""
    for ext in ("parquet", "csv"):
        if f"{stem}.{ext}" in listing:
            return f"{stem}.{ext}"
    return None


def stems_for(ds: dict, meses: list[str]) -> list[str]:
    """Nomes-base necessários para cobrir os meses pedidos (anual ou mensal)."""
    stems: set[str] = set()
    for ym in meses:
        if ym < ds["first"]:
            continue
        y, m = int(ym[:4]), int(ym[5:7])
        if ds["monthly"] and ds["monthly_from"] is not None and y >= ds["monthly_from"]:
            stems.add(ds["monthly"].format(y=y, m=m))
        elif ds["annual"]:
            stems.add(ds["annual"].format(y=y))
        elif ds["monthly"]:
            stems.add(ds["monthly"].format(y=y, m=m))
    return sorted(stems)


def download_dataset(nome: str, ds: dict, meses: list[str], force: bool) -> list[str]:
    faltando: list[str] = []
    listing = s3_list(ds["prefix"])
    dest_dir = C.RAW / "ons" / nome
    # dicionários
    for fname in listing:
        if fname.lower().startswith("dicionariodados"):
            download(f"{C.ONS_S3}/{listing[fname]['key']}", dest_dir / fname, f"ons/{nome}",
                     force=force, obs="dicionario de dados")
    for stem in stems_for(ds, meses):
        fname = pick(listing, stem)
        if fname is None:
            faltando.append(f"{nome}:{stem}")
            LOG.warning("nao encontrado no S3: %s/%s.{parquet,csv}", ds["prefix"], stem)
            continue
        info = listing[fname]
        download(f"{C.ONS_S3}/{info['key']}", dest_dir / fname, f"ons/{nome}", force=force,
                 obs=f"S3 LastModified={info['last_modified']}")
    return faltando


def download_cadastros(force: bool) -> None:
    for nome, prefix in C.ONS_CADASTROS.items():
        try:
            listing = s3_list(prefix)
        except Exception as e:  # prefixo pode estar errado (usina_conjunto/usina_pqu não confirmados)
            LOG.warning("cadastro %s: nao foi possivel listar %s (%s)", nome, prefix, e)
            continue
        if not listing:
            LOG.warning("cadastro %s: prefixo %s vazio — verificar nome no portal", nome, prefix)
            continue
        dest_dir = C.RAW / "ons" / "cadastros" / nome
        for fname, info in listing.items():
            if fname.endswith((".parquet", ".csv", ".json", ".pdf")) and not fname.endswith(".xlsx"):
                download(f"{C.ONS_S3}/{info['key']}", dest_dir / fname, f"ons/cadastros/{nome}",
                         force=force, obs=f"cadastro sem historico; S3 LastModified={info['last_modified']}")


# ----------------------------------------------------------------- API carga
def sondar_areas(dia: str = "2025-08-01") -> list[str]:
    """Descobre quais códigos de área de carga respondem na API."""
    areas_path = C.RAW / "ons" / "carga_api" / "areas.json"
    if areas_path.exists():
        return json.loads(areas_path.read_text())["areas"]
    ok = []
    for cod in C.ONS_AREAS_CANDIDATAS:
        r = http_get(f"{C.ONS_API_CARGA}?dat_inicio={dia}&dat_fim={dia}&cod_areacarga={cod}")
        try:
            n = len(r.json())
        except Exception:
            n = 0
        if n > 0:
            ok.append(cod)
        LOG.info("area %-4s -> %d registros", cod, n)
    areas_path.parent.mkdir(parents=True, exist_ok=True)
    areas_path.write_text(json.dumps({"dia_sondagem": dia, "candidatas": C.ONS_AREAS_CANDIDATAS,
                                      "areas": ok}, indent=2))
    return ok


def download_carga_api(meses: list[str], force: bool) -> None:
    """Um JSON por área × mês. Pede o mês com 1 dia de margem de cada lado
    (dat_referencia é dia local; precisamos cobrir o mês inteiro em UTC)."""
    areas = sondar_areas()
    dest_dir = C.RAW / "ons" / "carga_api"
    for ym in meses:
        p = pd.Period(ym, "M")
        d0 = (p.start_time - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        d1 = (p.end_time + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        for cod in areas:
            dest = dest_dir / f"carga_verificada_{cod}_{ym}.json"
            if not force and in_manifest(dest):
                continue
            url = f"{C.ONS_API_CARGA}?dat_inicio={d0}&dat_fim={d1}&cod_areacarga={cod}"
            r = http_get(url, timeout=180)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            try:
                n = len(r.json())
            except Exception:
                n = -1
            manifest_add("ons/carga_api", dest, url, "", obs=f"registros={n}; margem 1 dia")
            LOG.info("carga_api %s %s: %d registros", cod, ym, n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*")
    ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--so", nargs="*", help="subconjunto: nomes de ONS_DATASETS, 'cadastros', 'carga_api'")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--incluir-opcionais", action="store_true", help="inclui evt (D10)")
    a = ap.parse_args()
    meses = parse_months(a.meses, a.inicio, a.fim)
    alvo = set(a.so) if a.so else set(C.ONS_DATASETS) | {"cadastros", "carga_api"}
    faltando: list[str] = []
    try:
        for nome, ds in C.ONS_DATASETS.items():
            if nome not in alvo:
                continue
            if ds.get("optional") and not a.incluir_opcionais and not (a.so and nome in a.so):
                continue
            LOG.info("== %s", nome)
            faltando += download_dataset(nome, ds, meses, a.force)
        if "cadastros" in alvo:
            LOG.info("== cadastros")
            download_cadastros(a.force)
        if "carga_api" in alvo:
            LOG.info("== carga_api")
            download_carga_api(meses, a.force)
    except BlockedByNetwork as e:
        LOG.error("PARADO: %s", e)
        raise SystemExit(2)
    if faltando:
        LOG.warning("arquivos nao encontrados (registrar em relatorio_qualidade): %s", faltando)
        (C.RAW / "ons" / "faltando.txt").write_text("\n".join(faltando) + "\n")


if __name__ == "__main__":
    main()
