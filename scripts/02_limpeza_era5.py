"""ERA5 NetCDF mensal → dim_celula, clima_h (por mês), clima_perfil_mes_hora (ao final).

Uso: python scripts/02_limpeza_era5.py --meses 2021-08 2025-08
     python scripts/02_limpeza_era5.py --inicio 2019-01 --fim 2026-08 --perfil

Convenções: ts_utc = carimbo ERA5 (instantâneo para vento/temperatura). ssrd é acumulada
(J/m²) na hora que TERMINA no carimbo → ghi_wm2 = ssrd/3600, atribuída à hora que COMEÇA em
carimbo−1h para alinhar com a convenção "início do intervalo" das demais tabelas (documentado
no dicionário; a coluna ghi_conv registra a escolha). Máscara terrestre: malha IBGE de UF.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
from common import LOG, parse_months, write_parquet

DIM_CELULA = C.PROCESSED / "dim_celula.parquet"


def open_era5(path: Path):
    """O CDS novo devolve um ZIP (nomeado .nc pelo download) com dois NetCDF quando a
    requisição mistura variáveis instantâneas (u/v/t2m) e acumuladas (ssrd). Abre ambos,
    descarta as coordenadas auxiliares (number, expver) e funde num único Dataset em memória."""
    import tempfile
    import xarray as xr

    def limpa(ds):
        return ds.drop_vars([c for c in ("number", "expver") if c in ds.coords or c in ds.variables])

    if not zipfile.is_zipfile(path):
        return limpa(xr.open_dataset(path))
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        parts = []
        for name in zf.namelist():
            if name.endswith(".nc"):
                parts.append(limpa(xr.open_dataset(zf.extract(name, tmp))).load())
    return xr.merge(parts)


def build_dim_celula(sample_nc: Path) -> pd.DataFrame:
    import geopandas as gpd
    from shapely.geometry import Point

    ds = open_era5(sample_nc)
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    lons, lats = np.meshgrid(lon, lat)
    cel = pd.DataFrame({"lat": lats.ravel(), "lon": lons.ravel()})
    cel["id_celula"] = [f"c{la:+06.2f}_{lo:+07.2f}".replace("+", "p").replace("-", "m") for la, lo in zip(cel.lat, cel.lon)]
    # UF e município por ponto-em-polígono (IBGE 2024)
    uf = gpd.read_file(f"zip://{C.RAW / 'ibge' / 'BR_UF_2024.zip'}")
    mun = gpd.read_file(f"zip://{C.RAW / 'ibge' / 'BR_Municipios_2024.zip'}")
    pts = gpd.GeoDataFrame(cel, geometry=[Point(x, y) for x, y in zip(cel.lon, cel.lat)], crs="EPSG:4326")
    pts = gpd.sjoin(pts, uf[["SIGLA_UF", "geometry"]].to_crs("EPSG:4326"), how="left", predicate="within").drop(columns="index_right")
    pts = gpd.sjoin(pts, mun[["CD_MUN", "NM_MUN", "geometry"]].to_crs("EPSG:4326"), how="left", predicate="within").drop(columns="index_right")
    out = pd.DataFrame(pts.drop(columns="geometry")).rename(columns={"SIGLA_UF": "uf", "CD_MUN": "cod_municipio_ibge", "NM_MUN": "municipio"})
    out["terrestre"] = out["uf"].notna().astype("int8")
    # subsistema: derivado de UF→subsistema (03_integracao preenche a partir do cadastro do ONS)
    out["subsistema"] = None
    out = out.drop_duplicates("id_celula")
    LOG.info("dim_celula: %d células, %d terrestres", len(out), out["terrestre"].sum())
    write_parquet(out, DIM_CELULA)
    return out


def clima_mes(ym: str, cel: pd.DataFrame) -> None:
    import xarray as xr
    stem = C.RAW / "era5" / f"era5_sl_0p5_{ym.replace('-', '_')}"
    nc = next((p for p in (stem.with_suffix(".zip"), stem.with_suffix(".nc")) if p.exists()), stem.with_suffix(".nc"))
    if not nc.exists():
        LOG.warning("ERA5 %s ausente", ym)
        return
    ds = open_era5(nc)
    tcoord = "valid_time" if "valid_time" in ds.coords else "time"
    ws100 = np.sqrt(ds["u100"] ** 2 + ds["v100"] ** 2)
    ws10 = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
    t2m = ds["t2m"] - 273.15
    ghi = ds["ssrd"] / 3600.0
    # ssrd: acumulado na hora que termina no carimbo → deslocar −1h para "início da hora"
    ghi = ghi.assign_coords({tcoord: ghi[tcoord] - np.timedelta64(1, "h")})
    df = xr.Dataset({"ws100_ms": ws100, "ws10_ms": ws10, "t2m_c": t2m}).to_dataframe().reset_index()
    dg = ghi.to_dataframe(name="ghi_wm2").reset_index()
    df = df.merge(dg, on=[tcoord, "latitude", "longitude"], how="left")
    df = df.rename(columns={tcoord: "ts_utc", "latitude": "lat", "longitude": "lon"})
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df = df.merge(cel[["id_celula", "lat", "lon", "terrestre"]], on=["lat", "lon"], how="inner")
    df = df[df["terrestre"] == 1]
    df = df[df["ts_utc"].dt.strftime("%Y-%m") == ym]  # o deslocamento cria 1 h fora do mês
    df["flag_ghi_nulo"] = df["ghi_wm2"].isna().astype("int8")  # última hora do mês perde ghi (vem no mês seguinte)
    out = df[["ts_utc", "id_celula", "ws100_ms", "ws10_ms", "ghi_wm2", "t2m_c", "flag_ghi_nulo"]].copy()
    for c in ["ws100_ms", "ws10_ms", "ghi_wm2", "t2m_c"]:
        out[c] = out[c].astype("float32")
    write_parquet(out, C.PROCESSED / "clima_h" / f"clima_h_{ym}.parquet")


def perfil() -> None:
    files = sorted((C.PROCESSED / "clima_h").glob("clima_h_*.parquet"))
    acc = []
    for f in files:
        d = pd.read_parquet(f)
        loc = d["ts_utc"].dt.tz_convert(C.TZ_LOCAL)
        d["mes"] = loc.dt.month.astype("int8"); d["hora_local"] = loc.dt.hour.astype("int8")
        for c in ["ws100_ms", "ghi_wm2", "t2m_c"]:
            d[f"{c}_sq"] = d[c] ** 2
        g = d.groupby(["id_celula", "mes", "hora_local"]).agg(
            n=("ws100_ms", "size"), ws100_s=("ws100_ms", "sum"), ws100_ss=("ws100_ms_sq", "sum"),
            ghi_s=("ghi_wm2", "sum"), ghi_ss=("ghi_wm2_sq", "sum"), t2m_s=("t2m_c", "sum"), t2m_ss=("t2m_c_sq", "sum"))
        acc.append(g)
    tot = pd.concat(acc).groupby(level=[0, 1, 2]).sum().reset_index()
    for v in ["ws100", "ghi", "t2m"]:
        m = tot[f"{v}_s"] / tot["n"]
        var = tot[f"{v}_ss"] / tot["n"] - m ** 2
        name = {"ws100": "ws100_ms", "ghi": "ghi_wm2", "t2m": "t2m_c"}[v]
        tot[f"{name}_media"] = m; tot[f"{name}_dp"] = np.sqrt(var.clip(lower=0))
    out = tot[["id_celula", "mes", "hora_local", "n"] + [c for c in tot if c.endswith(("_media", "_dp"))]]
    out = out.rename(columns={"n": "n_horas"})
    write_parquet(out, C.PROCESSED / "clima_perfil_mes_hora.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*"); ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--perfil", action="store_true", help="recalcula clima_perfil_mes_hora com tudo que existe em clima_h")
    a = ap.parse_args()
    meses = parse_months(a.meses, a.inicio, a.fim)
    ncs = sorted([*(C.RAW / "era5").glob("era5_sl_0p5_*.nc"), *(C.RAW / "era5").glob("era5_sl_0p5_*.zip")])
    if not ncs:
        LOG.error("nenhum NetCDF ERA5 em data/raw/era5")
        return
    cel = pd.read_parquet(DIM_CELULA) if DIM_CELULA.exists() else build_dim_celula(ncs[0])
    for ym in meses:
        out = C.PROCESSED / "clima_h" / f"clima_h_{ym}.parquet"
        if out.exists():
            LOG.info("clima_h %s ja existe", ym); continue
        clima_mes(ym, cel)
    if a.perfil:
        perfil()


if __name__ == "__main__":
    main()
