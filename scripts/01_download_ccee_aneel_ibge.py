"""Download: CCEE (PLD horário), ANEEL (SIGA, MMGD), IBGE (malhas), placeholder MCTI.

Uso: python scripts/01_download_ccee_aneel_ibge.py --anos 2021 2025
     python scripts/01_download_ccee_aneel_ibge.py --inicio 2019-01 --fim 2026-08
"""
from __future__ import annotations

import argparse

import requests

import config as C
from common import LOG, BlockedByNetwork, download, http_get, in_manifest, parse_months


def ccee_pld(anos: list[int], force: bool) -> None:
    """Os links da CCEE são opacos (pda-download.ccee.org.br/<id>/content): resolve pela API CKAN.

    O portal fica atrás do Akamai Bot Manager e responde 403 "Acesso bloqueado" a clientes
    que não sejam navegador (curl/requests), inclusive nos links de download. Nesse caso o
    arquivo precisa ser baixado à mão no navegador e registrado com 01_registrar_manual.py."""
    dest_dir = C.RAW / "ccee" / "pld_horario"
    try:
        r = http_get(C.CCEE_CKAN)
    except requests.exceptions.HTTPError as e:
        if e.response is None or e.response.status_code != 403:
            raise
        faltam = [a for a in anos if not in_manifest(dest_dir / f"pld_horario_{a}.csv")]
        if faltam:
            LOG.warning("CCEE bloqueia clientes nao-navegador (403 Akamai). Baixe no navegador em "
                        "https://dadosabertos.ccee.org.br/dataset/pld_horario os recursos %s, salve em %s "
                        "e rode: python scripts/01_registrar_manual.py <arquivo> --fonte ccee/pld_horario "
                        "--url <link do recurso>", [f"pld_horario_{a}" for a in faltam], dest_dir)
        else:
            LOG.info("CCEE: PLD %s ja registrados manualmente", anos)
        return
    res = r.json()["result"]["resources"]
    for rs in res:
        name = rs.get("name", "")
        url = rs.get("url", "")
        if name.startswith("pld_horario_"):
            ano = int(name.split("_")[-1][:4])
            if ano in anos:
                download(url, dest_dir / f"{name}.csv", "ccee/pld_horario", force=force,
                         obs=f"CKAN resource id={rs.get('id')}; last_modified={rs.get('last_modified')}")
        elif name.startswith("pld_historico_semanal") and any(a <= 2020 for a in anos):
            download(url, dest_dir / f"{name}.csv", "ccee/pld_horario", force=force,
                     obs="PLD semanal por patamar (2001-2020); NAO e horario — ver D04")


def aneel(force: bool) -> None:
    d = C.RAW / "aneel"
    download(C.ANEEL_SIGA_CSV, d / "siga" / "siga-empreendimentos-geracao.csv", "aneel/siga", force=force)
    download(C.ANEEL_SIGA_DIC, d / "siga" / "dm-siga.pdf", "aneel/siga", force=force, obs="dicionario")
    download(C.ANEEL_MMGD_PARQUET, d / "mmgd" / "empreendimento-geracao-distribuida.parquet", "aneel/mmgd", force=force)
    download(C.ANEEL_MMGD_DIC, d / "mmgd" / "dm-geracao-distribuida.pdf", "aneel/mmgd", force=force, obs="dicionario")


def ibge(force: bool) -> None:
    for f in C.IBGE_FILES:
        download(C.IBGE_BASE + f, C.RAW / "ibge" / f, "ibge/malhas_2024", force=force)


def mcti_check() -> None:
    d = C.RAW / "mcti"
    d.mkdir(parents=True, exist_ok=True)
    xls = list(d.glob("*.xls*")) + list(d.glob("*.csv"))
    if not xls:
        LOG.warning("MCTI: coloque manualmente o XLSX dos fatores medios mensais do SIN em %s "
                    "(pagina exige CAPTCHA) e rode scripts/01_registrar_manual.py", d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", nargs="*", type=int)
    ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--so", nargs="*", help="ccee | aneel | ibge")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    anos = a.anos or sorted({int(m[:4]) for m in parse_months(None, a.inicio, a.fim)})
    alvo = set(a.so) if a.so else {"ccee", "aneel", "ibge"}
    try:
        if "ccee" in alvo:
            ccee_pld(anos, a.force)
        if "aneel" in alvo:
            aneel(a.force)
        if "ibge" in alvo:
            ibge(a.force)
    except BlockedByNetwork as e:
        LOG.error("PARADO: %s", e)
        raise SystemExit(2)
    mcti_check()


if __name__ == "__main__":
    main()
