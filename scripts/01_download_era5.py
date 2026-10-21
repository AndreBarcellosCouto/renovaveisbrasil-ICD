"""Download ERA5 (single levels, horário) por mês, grade 0,5° (D01), via cdsapi.

Requer ~/.cdsapirc com a chave do usuário (nunca no repositório).
Uso: python scripts/01_download_era5.py --meses 2021-08 2025-08
     python scripts/01_download_era5.py --inicio 2019-01 --fim 2026-08 --paralelo 3

Um arquivo por mês em data/raw/era5/era5_sl_0p5_{AAAA}_{MM}.zip (zip do CDS com dois NetCDF, D21;
os baixados até 2026-09 ficaram com extensão .nc). Idempotente.
Convenções ERA5: carimbo UTC; u/v/t2m instantâneos no carimbo; ssrd (J/m²) acumulado
na hora que TERMINA no carimbo.
"""
from __future__ import annotations

import argparse
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import config as C
from common import LOG, in_manifest, manifest_add, parse_months


def request_for(ym: str) -> dict:
    y, m = ym[:4], ym[5:7]
    import calendar
    ndays = calendar.monthrange(int(y), int(m))[1]
    return {
        "product_type": ["reanalysis"],
        "variable": C.ERA5_VARS,
        "year": [y], "month": [m],
        "day": [f"{d:02d}" for d in range(1, ndays + 1)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": C.ERA5_AREA,
        "grid": C.ERA5_GRID,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def fetch(ym: str, force: bool) -> str:
    import cdsapi  # import tardio: só quem baixa precisa
    dest = C.RAW / "era5" / f"era5_sl_0p5_{ym.replace('-', '_')}.nc"
    if not force and (in_manifest(dest) or in_manifest(dest.with_suffix(".zip"))):
        return f"{ym}: ja existe"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".nc.part")
    c = cdsapi.Client(quiet=True)
    c.retrieve(C.ERA5_DATASET, request_for(ym), str(tmp))
    if zipfile.is_zipfile(tmp):  # CDS novo: zip com dois NetCDF (D21) → extensão correta
        dest = dest.with_suffix(".zip")
    tmp.replace(dest)
    manifest_add("era5", dest, f"cds:{C.ERA5_DATASET}", "",
                 obs=f"grid={C.ERA5_GRID}; area(N,W,S,E)={C.ERA5_AREA}; vars={','.join(C.ERA5_VARS)}")
    return f"{ym}: baixado {dest.stat().st_size/1e6:.0f} MB"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*")
    ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--paralelo", type=int, default=2, help="requisicoes simultaneas ao CDS")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not (Path.home() / ".cdsapirc").exists() and not os.environ.get("CDSAPI_KEY"):
        LOG.error("falta ~/.cdsapirc (ou CDSAPI_URL/CDSAPI_KEY). Peça a chave ao usuário.")
        raise SystemExit(3)
    meses = parse_months(a.meses, a.inicio, a.fim)
    with ThreadPoolExecutor(max_workers=a.paralelo) as ex:
        futs = {ex.submit(fetch, ym, a.force): ym for ym in meses}
        for f in as_completed(futs):
            try:
                LOG.info(f.result())
            except Exception as e:
                LOG.error("%s: FALHOU %s", futs[f], e)


if __name__ == "__main__":
    main()
