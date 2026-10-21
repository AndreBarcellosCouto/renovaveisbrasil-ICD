"""Utilitários compartilhados: download com manifesto, hash, tempo, log."""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

import config as C

LOG = logging.getLogger("pipeline")
if not LOG.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    LOG.addHandler(h)
    LOG.setLevel(logging.INFO)

MANIFEST_COLS = ["fonte", "arquivo", "url", "data_acesso_utc", "tamanho_bytes",
                 "sha256", "last_modified_origem", "observacao"]


# ------------------------------------------------------------------ manifesto
def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def read_manifest() -> pd.DataFrame:
    if C.MANIFEST.exists() and C.MANIFEST.stat().st_size > 0:
        return pd.read_csv(C.MANIFEST, dtype=str).fillna("")
    return pd.DataFrame(columns=MANIFEST_COLS)


def manifest_add(fonte: str, path: Path, url: str, last_modified: str = "", obs: str = "") -> None:
    """Acrescenta (ou substitui) a linha do arquivo no manifesto."""
    df = read_manifest()
    rel = str(path.relative_to(C.RAW)).replace(os.sep, "/")
    row = dict(fonte=fonte, arquivo=rel, url=url,
               data_acesso_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               tamanho_bytes=str(path.stat().st_size), sha256=sha256_of(path),
               last_modified_origem=last_modified, observacao=obs)
    df = df[df["arquivo"] != rel]
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.sort_values(["fonte", "arquivo"]).to_csv(C.MANIFEST, index=False, quoting=csv.QUOTE_MINIMAL)


def in_manifest(path: Path) -> bool:
    df = read_manifest()
    rel = str(path.relative_to(C.RAW)).replace(os.sep, "/")
    return path.exists() and (df["arquivo"] == rel).any()


# ------------------------------------------------------------------ download
class BlockedByNetwork(RuntimeError):
    pass


def http_get(url: str, *, stream: bool = False, timeout: int = 120, tries: int = 4,
             **kw) -> requests.Response:
    """GET com tentativas. Levanta BlockedByNetwork em 403/407 do proxy ou falha de conexão."""
    last: Exception | None = None
    for i in range(tries):
        try:
            r = requests.get(url, stream=stream, timeout=timeout, **kw)
            if r.status_code in (403, 407) and "agentproxy" in (r.headers.get("server", "") + r.text[:200]).lower():
                raise BlockedByNetwork(f"dominio bloqueado pela rede: {url}")
            if r.status_code == 404:
                return r
            r.raise_for_status()
            return r
        except requests.exceptions.ProxyError as e:
            raise BlockedByNetwork(f"dominio bloqueado pela rede (proxy): {url}") from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last = e
            LOG.warning("tentativa %d/%d falhou para %s: %s", i + 1, tries, url, e)
            time.sleep(2 ** i)
    assert last is not None
    if isinstance(last, requests.exceptions.ConnectionError):
        raise BlockedByNetwork(f"sem conexao com {url}: {last}") from last
    raise last


def download(url: str, dest: Path, fonte: str, *, force: bool = False, obs: str = "") -> Path | None:
    """Baixa `url` para `dest` se ainda não estiver no manifesto. Retorna None em 404."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not force and in_manifest(dest):
        LOG.info("ja existe: %s", dest.name)
        return dest
    r = http_get(url, stream=True)
    if r.status_code == 404:
        LOG.warning("404: %s", url)
        return None
    tmp = dest.with_suffix(dest.suffix + ".part")
    n = 0
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
            n += len(chunk)
    tmp.replace(dest)
    manifest_add(fonte, dest, url, r.headers.get("Last-Modified", ""), obs)
    LOG.info("baixado: %s (%.1f MB)", dest.name, n / 1e6)
    return dest


# ------------------------------------------------------------------ período
def months_between(inicio: str, fim: str) -> list[str]:
    """['2019-01', ..., '2026-08'] inclusivo."""
    return [p.strftime("%Y-%m") for p in pd.period_range(inicio, fim, freq="M")]


def parse_months(args_meses: list[str] | None, inicio: str | None, fim: str | None) -> list[str]:
    if args_meses:
        return sorted(set(args_meses))
    return months_between(inicio or C.PERIODO_INICIO, fim or C.PERIODO_FIM)


# ------------------------------------------------------------------ tempo
def local_to_utc(ts_local_naive: pd.Series, *, ambiguous="NaT", nonexistent="NaT") -> pd.Series:
    """Converte carimbos ingênuos em horário de Brasília (com horário de verão legal
    até fev/2019) para UTC. Horas ambíguas/inexistentes viram NaT por padrão — o
    chamador deve sinalizar (flag) em vez de imputar."""
    s = pd.to_datetime(ts_local_naive)
    loc = s.dt.tz_localize(C.TZ_LOCAL, ambiguous=ambiguous, nonexistent=nonexistent)
    return loc.dt.tz_convert("UTC")


def utc_to_local(ts_utc: pd.Series) -> pd.Series:
    return pd.to_datetime(ts_utc, utc=True).dt.tz_convert(C.TZ_LOCAL)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", compression="zstd", index=False)
    LOG.info("gravado %s (%d linhas)", path.relative_to(C.ROOT), len(df))
