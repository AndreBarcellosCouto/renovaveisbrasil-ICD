"""Limpeza CCEE (PLD horário), ANEEL SIGA (cadastro de usinas) e ANEEL MMGD (acumulado mensal).

Uso: python scripts/02_limpeza_ccee_aneel.py --meses 2021-08 2025-08
Os nomes de colunas dos portais mudam de caixa/acentos; usamos busca tolerante (`col()`),
e o script falha listando as colunas reais quando não encontra — nunca adivinha em silêncio.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
from common import LOG, local_to_utc, parse_months, write_parquet


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def col(df: pd.DataFrame, *cands: str, required: bool = True) -> str | None:
    m = {norm(c): c for c in df.columns}
    for c in cands:
        if norm(c) in m:
            return m[norm(c)]
    if required:
        raise KeyError(f"coluna nao encontrada; candidatas={cands}; colunas reais={list(df.columns)}")
    return None


def read_csv_br(path: Path, **kw) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"nao foi possivel ler {path}")


# ----------------------------------------------------------------- PLD
def pld(meses: list[str]) -> None:
    anos = sorted({m[:4] for m in meses if m >= "2021-01"})
    parts = []
    for y in anos:
        p = C.RAW / "ccee" / "pld_horario" / f"pld_horario_{y}.csv"
        if not p.exists():
            LOG.warning("PLD %s ausente", y)
            continue
        df = read_csv_br(p)
        LOG.info("pld_horario_%s: colunas=%s", y, list(df.columns))
        c_sub = col(df, "SUBMERCADO", "submercado", "nom_submercado", "sigla_submercado")
        c_val = col(df, "PLD", "pld", "VALOR", "val_pld", "PLD_HORARIO", "PLD_HORA")
        c_hora = col(df, "HORA", "hora", "hora_ref")
        c_mes = col(df, "MES_REFERENCIA", required=False)
        if c_mes:
            # layout 2025: MES_REFERENCIA=AAAAMM + DIA (número do dia)
            c_dia = col(df, "DIA", "dia")
            d = pd.to_datetime(df[c_mes].astype(str).str[:6] + df[c_dia].astype(int).astype(str).str.zfill(2),
                               format="%Y%m%d", errors="coerce")
        else:
            c_data = col(df, "DATA", "data", "DIA", "dia", "dat_referencia", "DATA_REFERENCIA")
            d = pd.to_datetime(df[c_data], dayfirst=True, errors="coerce")
        h = df[c_hora].astype(str).str.extract(r"(\d{1,2})")[0].astype(float)
        # Convenção 0–23 vs 1–24: registrada em decisoes.md após inspeção do piloto
        conv_1_24 = h.max() == 24
        if conv_1_24:
            h = h - 1
        ts_local = d + pd.to_timedelta(h, unit="h")
        val = pd.to_numeric(df[c_val].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                            if df[c_val].dtype == object else df[c_val], errors="coerce")
        sub = df[c_sub].astype(str).str.upper().str.strip()
        sub = sub.replace({"SUDESTE": "SE", "SUDESTE/CENTRO-OESTE": "SE", "SUL": "S", "NORDESTE": "NE", "NORTE": "N"})
        out = pd.DataFrame(dict(ts_local=ts_local, submercado=sub, pld_rs_mwh=val))
        out["ts_utc"] = local_to_utc(out["ts_local"])
        out["flag_ts_ambiguo"] = (out["ts_local"].notna() & out["ts_utc"].isna()).astype("int8")
        out["convencao_hora_origem"] = "1-24" if conv_1_24 else "0-23"
        parts.append(out)
    if not parts:
        return
    df = pd.concat(parts, ignore_index=True)
    ym = df["ts_local"].dt.strftime("%Y-%m")
    for m in meses:
        part = df[ym == m]
        if len(part):
            write_parquet(part, C.PROCESSED / "pld_h" / f"pld_h_{m}.parquet")


# ----------------------------------------------------------------- SIGA
def siga() -> None:
    p = C.RAW / "aneel" / "siga" / "siga-empreendimentos-geracao.csv"
    if not p.exists():
        LOG.warning("SIGA ausente")
        return
    df = read_csv_br(p, dtype=str)
    LOG.info("SIGA: %d linhas; colunas=%s", len(df), list(df.columns))
    g = lambda *c, **k: col(df, *c, **k)
    c_mun = g("DscMuninicpios", "DscMunicipios", "NomMunicipio", "municipio", required=False)  # grafia da fonte
    out = pd.DataFrame({
        "ceg_aneel": df[g("CodCEG", "ceg")].str.strip(),
        "nome_aneel": df[g("NomEmpreendimento", "nome_empreendimento")].str.strip(),
        "uf": df[g("SigUFPrincipal", "uf")].str.strip(),
        "tipo_geracao": df[g("SigTipoGeracao", "tipo_geracao")].str.strip(),
        "fase": df[g("DscFaseUsina", "fase")].str.strip(),
        "origem_combustivel": df[g("DscOrigemCombustivel", required=False) or g("DscFonteCombustivel")].str.strip(),
        "fonte_combustivel": df[g("DscFonteCombustivel", "fonte_combustivel")].str.strip(),
        "nome_combustivel": df[g("NomFonteCombustivel", required=False) or g("DscFonteCombustivel")].str.strip(),
        "municipio_aneel": df[c_mun].str.strip() if c_mun else None,
        "potencia_outorgada_kw": pd.to_numeric(df[g("MdaPotenciaOutorgadaKw")].str.replace(",", ".", regex=False), errors="coerce"),
        "potencia_fiscalizada_kw": pd.to_numeric(df[g("MdaPotenciaFiscalizadaKw")].str.replace(",", ".", regex=False), errors="coerce"),
        "data_inicio_operacao": pd.to_datetime(df[g("DatEntradaOperacao")], format="%Y-%m-%d", errors="coerce"),
        "lat": pd.to_numeric(df[g("NumCoordNEmpreendimento")].str.replace(",", ".", regex=False), errors="coerce"),
        "lon": pd.to_numeric(df[g("NumCoordEEmpreendimento")].str.replace(",", ".", regex=False), errors="coerce"),
    })
    out["potencia_mw"] = out["potencia_fiscalizada_kw"].fillna(out["potencia_outorgada_kw"]) / 1000.0
    out["flag_coord_invalida"] = (~out["lat"].between(-34, 6) | ~out["lon"].between(-74, -34)).astype("int8")
    out.loc[out["flag_coord_invalida"] == 1, ["lat", "lon"]] = np.nan
    write_parquet(out, C.PROCESSED / "siga_usinas.parquet")


# ----------------------------------------------------------------- MMGD
def mmgd(meses: list[str]) -> None:
    p = C.RAW / "aneel" / "mmgd" / "empreendimento-geracao-distribuida.parquet"
    if not p.exists():
        LOG.warning("MMGD ausente")
        return
    df = pd.read_parquet(p)
    LOG.info("MMGD: %d linhas; colunas=%s", len(df), list(df.columns))
    c_uf = col(df, "SigUF", "uf")
    c_mun = col(df, "NomMunicipio", "municipio")
    c_cod = col(df, "CodMunicipioIbge", "cod_municipio_ibge", required=False)
    c_fonte = col(df, "DscFonteGeracao", "SigTipoGeracao", "fonte")
    c_pot = col(df, "MdaPotenciaInstaladaKW", "potencia_instalada_kw", "MdaPotenciaInstalada")
    c_data = col(df, "DthConexao", "DatConexao", "data_conexao", "DthAtualizaCadastralEmpreend")
    d = pd.to_datetime(df[c_data], errors="coerce", dayfirst=True)
    pot = pd.to_numeric(df[c_pot].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    base = pd.DataFrame({"mes_conexao": d.dt.to_period("M"), "uf": df[c_uf], "municipio": df[c_mun],
                         "cod_municipio_ibge": df[c_cod] if c_cod else None, "fonte": df[c_fonte], "pot_kw": pot})
    base["flag_data_nula"] = base["mes_conexao"].isna().astype("int8")
    LOG.info("MMGD: %.1f%% unidades sem data de conexao (excluidas do acumulado, contadas em flag)",
             100 * base["flag_data_nula"].mean())
    base = base.dropna(subset=["mes_conexao"])
    inc = base.groupby(["uf", "municipio", "cod_municipio_ibge", "fonte", "mes_conexao"], dropna=False)["pot_kw"].sum()
    inc = inc.unstack("mes_conexao").fillna(0.0)
    # eixo mensal completo até o último mês pedido; acumulado = soma até o mês
    fim = pd.Period(max(meses), "M")
    cols = pd.period_range(inc.columns.min(), fim, freq="M")
    inc = inc.reindex(columns=cols, fill_value=0.0)
    acc = inc.cumsum(axis=1)
    long = acc.stack().rename("potencia_acumulada_kw").reset_index().rename(columns={"level_4": "mes"})
    long["mes"] = long["mes"].astype(str)
    long["potencia_acumulada_mw"] = long["potencia_acumulada_kw"] / 1000.0
    long = long[long["mes"].isin(meses)].drop(columns=["potencia_acumulada_kw"])
    write_parquet(long, C.PROCESSED / "mmgd_mensal.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*"); ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--so", nargs="*", choices=["pld", "siga", "mmgd"])
    a = ap.parse_args()
    meses = parse_months(a.meses, a.inicio, a.fim)
    alvo = a.so or ["pld", "siga", "mmgd"]
    if "pld" in alvo:
        pld(meses)
    if "siga" in alvo:
        siga()
    if "mmgd" in alvo:
        mmgd(meses)


if __name__ == "__main__":
    main()
