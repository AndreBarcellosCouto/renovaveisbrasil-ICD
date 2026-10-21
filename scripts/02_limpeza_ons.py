"""Limpeza dos dados do ONS → data/processed/*.parquet (esquema-alvo).

Uso: python scripts/02_limpeza_ons.py --meses 2021-08 2025-08
     python scripts/02_limpeza_ons.py --inicio 2019-01 --fim 2026-08   (processa em lotes mensais)

Regras: nada é imputado; lacunas ficam nulas com flag. Carimbo ONS (din_instante) =
horário de Brasília, INÍCIO do intervalo (dicionários de EVT, térmica e intercâmbio).
Semi-horário em MWmed → hora = média das duas semi-horas (D07); n_semihoras registrado.
Saídas particionadas por mês: data/processed/<tabela>/<tabela>_<AAAA-MM>.parquet
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
from common import LOG, local_to_utc, parse_months, write_parquet

RAW_ONS = C.RAW / "ons"


# ----------------------------------------------------------------- leitura
def read_any(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    # CSV do ONS: geralmente ';' (alguns ','); deixa o pandas detectar
    return pd.read_csv(path, sep=None, engine="python", encoding="utf-8", decimal=".")


def raw_files(nome: str, meses: list[str]) -> list[Path]:
    """Arquivos brutos necessários (anuais e mensais) para os meses pedidos."""
    ds = C.ONS_DATASETS[nome]
    d = RAW_ONS / nome
    wanted: set[str] = set()
    for ym in meses:
        y, m = int(ym[:4]), int(ym[5:7])
        if ds["monthly"] and ds["monthly_from"] is not None and y >= ds["monthly_from"]:
            wanted.add(ds["monthly"].format(y=y, m=m))
        elif ds["annual"]:
            wanted.add(ds["annual"].format(y=y))
        elif ds["monthly"]:
            wanted.add(ds["monthly"].format(y=y, m=m))
    out = []
    for stem in sorted(wanted):
        for ext in ("parquet", "csv"):
            p = d / f"{stem}.{ext}"
            if p.exists():
                out.append(p)
                break
    return out


def load(nome: str, meses: list[str]) -> pd.DataFrame:
    files = raw_files(nome, meses)
    if not files:
        LOG.warning("%s: nenhum arquivo bruto para %s", nome, meses)
        return pd.DataFrame()
    parts = []
    for f in files:
        df = read_any(f)
        df.columns = [c.strip().lower() for c in df.columns]
        df = coerce_numeric(df, f.name)
        df["_arquivo_origem"] = f.name
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)
    LOG.info("%s: %d linhas de %d arquivo(s)", nome, len(df), len(files))
    return df


NUM_COL = re.compile(r"^(val_|num_|ear_(max|verif)|ena_(bruta|armazenavel))")


def coerce_numeric(df: pd.DataFrame, origem: str) -> pd.DataFrame:
    """Parquets do ONS (anos mais antigos) guardam decimais como texto ('1893.18000000',
    '0E-8', '' = nulo). Converte para float; registra o que não parseou."""
    for c in df.columns:
        if df[c].dtype != object or not NUM_COL.match(c):
            continue
        s = df[c].astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "None": np.nan})
        num = pd.to_numeric(s, errors="coerce")
        bad = int((num.isna() & s.notna()).sum())
        if bad:
            LOG.warning("%s: coluna %s tem %d valores nao numericos (viraram nulo)", origem, c, bad)
        df[c] = num
    if "cod_usinaplanejamento" in df:
        df["cod_usinaplanejamento"] = pd.to_numeric(df["cod_usinaplanejamento"], errors="coerce").astype("Int64")
    return df


# ----------------------------------------------------------------- tempo
def add_time(df: pd.DataFrame, col: str = "din_instante") -> pd.DataFrame:
    """ts_local (naive, Brasília) e ts_utc; flag para horas ambíguas/inexistentes (fim/início do
    horário de verão de 2019). Não imputa: ts_utc fica NaT e flag_ts_ambiguo=1."""
    ts_local = pd.to_datetime(df[col], errors="coerce")
    ts_utc = local_to_utc(ts_local, ambiguous="NaT", nonexistent="NaT")
    df = df.assign(ts_local=ts_local, ts_utc=ts_utc)
    df["flag_ts_ambiguo"] = (df["ts_local"].notna() & df["ts_utc"].isna()).astype("int8")
    return df


def filter_months(df: pd.DataFrame, meses: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    ym = df["ts_local"].dt.strftime("%Y-%m")
    return df[ym.isin(meses)].copy()


def semihour_to_hour(df: pd.DataFrame, keys: list[str], mean_cols: list[str],
                     sum_cols: list[str] | None = None, first_cols: list[str] | None = None,
                     min_cols: list[str] | None = None) -> pd.DataFrame:
    """Agrega semi-horas (MWmed) em horas: média; registra n_semihoras (flag se != 2)."""
    df = df.copy()
    df["ts_local"] = df["ts_local"].dt.floor("h")
    agg: dict = {c: "mean" for c in mean_cols if c in df}
    agg.update({c: "sum" for c in (sum_cols or []) if c in df})
    agg.update({c: "first" for c in (first_cols or []) if c in df})
    agg.update({c: "min" for c in (min_cols or []) if c in df})
    agg["_n"] = "size"
    df["_n"] = 1
    g = df.groupby(keys + ["ts_local"], dropna=False).agg(agg).reset_index()
    g = g.rename(columns={"_n": "n_semihoras"})
    g["ts_utc"] = local_to_utc(g["ts_local"], ambiguous="NaT", nonexistent="NaT")
    g["flag_ts_ambiguo"] = (g["ts_utc"].isna()).astype("int8")
    g["flag_hora_incompleta"] = (g["n_semihoras"] != 2).astype("int8")
    return g


def save(df: pd.DataFrame, tabela: str, meses: list[str]) -> None:
    if df.empty:
        return
    ym = df["ts_local"].dt.strftime("%Y-%m") if "ts_local" in df else df["data"].astype(str).str[:7]
    for m in meses:
        part = df[ym == m]
        if len(part):
            write_parquet(part.drop(columns=[c for c in part.columns if c.startswith("_")]),
                          C.PROCESSED / tabela / f"{tabela}_{m}.parquet")


# ----------------------------------------------------------------- subsistema dos conjuntos (D24)
def subsistema_conjuntos() -> pd.Series:
    """id_ons_conjunto → id_subsistema segundo RELACIONAMENTO_USINA_CONJUNTO (só conjuntos com
    subsistema único). É a atribuição usada pelo balanço, pelo constrained-off e pelo cadastro de
    capacidade; a geração horária e o fator de capacidade às vezes trazem outro (ex.: CJU_BASDA1)."""
    d = RAW_ONS / "cadastros" / "usina_conjunto"
    fs = list(d.glob("RELACIONAMENTO_USINA_CONJUNTO.*"))
    if not fs:
        LOG.warning("RELACIONAMENTO_USINA_CONJUNTO ausente; subsistema dos conjuntos nao conferido")
        return pd.Series(dtype=object)
    rel = read_any(fs[0])
    rel.columns = [c.strip().lower() for c in rel.columns]
    rel["id_ons_conjunto"] = rel["id_ons_conjunto"].astype(str).str.strip()
    u = rel.groupby("id_ons_conjunto")["id_subsistema"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    return u.dropna()


def reatribuir_subsistema(out: pd.DataFrame) -> pd.DataFrame:
    sub = subsistema_conjuntos()
    novo = out["id_ons"].astype(str).str.strip().map(sub)
    muda = novo.notna() & (novo != out["id_subsistema"])
    out["id_subsistema_origem"] = out["id_subsistema"]
    out.loc[muda, "id_subsistema"] = novo[muda]
    out["flag_subsistema_reatribuido"] = muda.astype("int8")
    if muda.any():
        LOG.info("subsistema reatribuido pelo cadastro de conjuntos: %s",
                 out[muda].groupby(["id_ons", "id_subsistema_origem", "id_subsistema"]).size().to_dict())
    return out


def fora_balanco_sin(df: pd.DataFrame) -> pd.Series:
    """Sistemas isolados publicados na geração por usina mas fora do balanço do SIN (D27)."""
    m = pd.Series(False, index=df.index)
    for r in C.FORA_BALANCO_SIN:
        sel = pd.Series(True, index=df.index)
        if r.get("uf"):
            sel &= df["id_estado"] == r["uf"]
        if r.get("tipo"):
            sel &= df["nom_tipousina"] == r["tipo"]
        if r.get("ids"):
            sel &= df["id_ons"].astype(str).str.strip().isin(r["ids"])
        if r.get("desde"):
            sel &= df["ts_local"] >= pd.Timestamp(r["desde"])
        if r.get("ate"):
            sel &= df["ts_local"] < pd.Timestamp(r["ate"])
        m |= sel
    return m


# ----------------------------------------------------------------- tabelas
def geracao_usina(meses):
    df = load("geracao_usina", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    df["ceg"] = df["ceg"].replace({"-": None, "": None})
    df = reatribuir_subsistema(df)
    out = df.rename(columns={"val_geracao": "geracao_mwh"})[
        ["ts_utc", "ts_local", "id_ons", "ceg", "nom_usina", "id_subsistema", "id_estado",
         "cod_modalidadeoperacao", "nom_tipousina", "nom_tipocombustivel", "geracao_mwh",
         "id_subsistema_origem", "flag_subsistema_reatribuido", "flag_ts_ambiguo", "_arquivo_origem"]]
    out["flag_negativo"] = (out["geracao_mwh"] < 0).astype("int8")
    # solar > 0,5 MWh entre 21h e 04h (local): dado da fonte, mantido com flag
    h = out["ts_local"].dt.hour
    solar = out["nom_tipousina"].astype(str).str.contains("FOTO|SOLAR", case=False)
    out["flag_solar_noturno"] = (solar & ((h >= 21) | (h <= 4)) & (out["geracao_mwh"] > 0.5)).astype("int8")
    out["flag_fora_balanco_sin"] = fora_balanco_sin(out).astype("int8")
    # duplicatas exatas (mesma usina, mesma hora)
    dup = out.duplicated(["id_ons", "ts_local"], keep=False)
    out["flag_duplicata"] = dup.astype("int8")
    save(out, "geracao_usina_h", meses)


def fator_capacidade(meses):
    df = load("fator_capacidade", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    ren = {"val_fatorcapacidade": "fator_capacidade", "val_geracaoverificada": "geracao_verificada_mwh",
           "val_geracaoprogramada": "geracao_programada_mwh", "val_capacidadeinstalada": "capacidade_instalada_mw",
           "nom_usina_conjunto": "nom_usina"}
    df = reatribuir_subsistema(df.rename(columns=ren))
    cols = ["ts_utc", "ts_local", "id_ons", "ceg", "nom_usina", "id_subsistema", "id_subsistema_origem",
            "flag_subsistema_reatribuido", "id_estado",
            "nom_modalidadeoperacao", "nom_tipousina", "val_latitudesecoletora", "val_longitudesecoletora",
            "fator_capacidade", "geracao_verificada_mwh", "geracao_programada_mwh", "capacidade_instalada_mw",
            "flag_ts_ambiguo", "_arquivo_origem"]
    out = df[[c for c in cols if c in df]].copy()
    out["flag_fc_fora_faixa"] = ((out["fator_capacidade"] < 0) | (out["fator_capacidade"] > 1.05)).astype("int8")
    save(out, "fator_capacidade_renovavel_h", meses)


MOTIVOS = ["ordemmerito", "inflexibilidade", "razaoeletrica", "garantiaenergetica", "gfom",
           "reposicaoperdas", "exportacao", "reservapotencia", "gsub", "unitcommitment", "constrainedoff"]


def termica_motivo(meses):
    df = load("termica_motivo", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    ids = ["ts_utc", "ts_local", "ceg", "cod_usinaplanejamento", "nom_usina", "id_subsistema",
           "nom_tipocombustivel", "dsc_tpmotivorestricao", "flag_ts_ambiguo", "_arquivo_origem"]
    ids = [c for c in ids if c in df]
    rows = []
    for mot in ["total"] + MOTIVOS:
        pc = "val_proggeracao" if mot == "total" else f"val_prog{mot}"
        vc = "val_verifgeracao" if mot == "total" else f"val_verif{mot}"
        if pc not in df and vc not in df:
            continue
        part = df[ids].copy()
        part["motivo"] = mot
        part["geracao_programada_mwh"] = df[pc] if pc in df else np.nan
        part["geracao_verificada_mwh"] = df[vc] if vc in df else np.nan
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    # descarta linhas sem informação em ambos (mantém 'total')
    out = out[(out["motivo"] == "total") | out["geracao_programada_mwh"].notna() | out["geracao_verificada_mwh"].notna()]
    save(out, "termica_motivo_h", meses)


def curtailment(meses):
    parts = []
    for nome, fonte in (("coff_eolica", "eolica"), ("coff_fv", "solar")):
        df = load(nome, meses)
        if df.empty:
            continue
        df = filter_months(add_time(df), meses)
        df["fonte"] = fonte
        ren = {"val_geracao": "geracao_verificada_mwh", "val_geracaolimitada": "geracao_limitada_mwh",
               "val_geracaoreferencia": "geracao_referencia_mwh",
               "val_geracaoreferenciafinal": "geracao_referencia_final_mwh",
               "val_geracaonaorealizadaapurada": "geracao_nao_realizada_mwh",
               "val_disponibilidade": "disponibilidade_mw"}
        df = df.rename(columns=ren)
        df["motivo"] = df["cod_razaorestricao"].fillna("").astype(str) + "/" + df["cod_origemrestricao"].fillna("").astype(str)
        df.loc[df["motivo"] == "/", "motivo"] = None
        mean_cols = list(ren.values())
        sum_cols = [c for c in df.columns if c.startswith("num_minutos")]
        g = semihour_to_hour(df, ["id_ons", "fonte"], mean_cols, sum_cols,
                             first_cols=["ceg", "nom_usina", "id_subsistema", "id_estado", "_arquivo_origem"])
        # motivo da hora: código(s) distintos observados nas semi-horas (ordenados)
        mot = (df.assign(ts_local=df["ts_local"].dt.floor("h"))
               .dropna(subset=["motivo"]).groupby(["id_ons", "fonte", "ts_local"])["motivo"]
               .agg(lambda s: "|".join(sorted(set(s)))).rename("motivo").reset_index())
        g = g.merge(mot, on=["id_ons", "fonte", "ts_local"], how="left")
        g["flag_ref_menor_que_verif"] = (g["geracao_referencia_mwh"] < g["geracao_verificada_mwh"] - 1e-6).astype("int8")
        parts.append(g)
    if parts:
        save(pd.concat(parts, ignore_index=True), "curtailment_h", meses)


def balanco(meses):
    df = load("balanco", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    ren = {"val_gerhidraulica": "ger_hidraulica_mwh", "val_gertermica": "ger_termica_mwh",
           "val_gereolica": "ger_eolica_mwh", "val_gersolar": "ger_solar_mwh",
           "val_carga": "carga_mwh", "val_intercambio": "intercambio_liquido_mwh", "id_subsistema": "subsistema"}
    out = df.rename(columns=ren)[["ts_utc", "ts_local", "subsistema"] + list(ren.values())[:-1] + ["flag_ts_ambiguo", "_arquivo_origem"]].copy()
    # ONS publica val_intercambio como exportação líquida (positivo = sai do subsistema);
    # aqui positivo = importação, mesma convenção de intercambio_h. Com isso ger + interc − carga = 0.
    out["intercambio_liquido_mwh"] = -out["intercambio_liquido_mwh"]
    save(out, "balanco_subsistema_h", meses)


def curva_carga(meses):
    df = load("curva_carga", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    out = df.rename(columns={"val_cargaenergiahomwmed": "carga_mwh", "id_subsistema": "subsistema"})[
        ["ts_utc", "ts_local", "subsistema", "carga_mwh", "flag_ts_ambiguo", "_arquivo_origem"]]
    save(out, "curva_carga_h", meses)


def intercambio(meses):
    df = load("intercambio", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    out = df.rename(columns={"id_subsistema_origem": "origem", "id_subsistema_destino": "destino",
                             "val_intercambiomwmed": "fluxo_mwh", "val_intercambioprogmwmed": "fluxo_programado_mwh"})
    cols = ["ts_utc", "ts_local", "origem", "destino", "fluxo_mwh", "fluxo_programado_mwh", "flag_ts_ambiguo", "_arquivo_origem"]
    save(out[[c for c in cols if c in out]], "intercambio_h", meses)


def cmo(meses):
    df = load("cmo", meses)
    if df.empty:
        return
    df = filter_months(add_time(df), meses)
    df = df.rename(columns={"id_subsistema": "submercado", "val_cmo": "cmo_rs_mwh"})
    g = semihour_to_hour(df, ["submercado"], ["cmo_rs_mwh"], first_cols=["_arquivo_origem"])
    save(g, "cmo_h", meses)


def hidro(meses):
    ear = load("ear", meses)
    ena = load("ena", meses)
    if ear.empty and ena.empty:
        return
    out = None
    if not ear.empty:
        ear = ear.rename(columns={"ear_data": "data", "id_subsistema": "subsistema",
                                  "ear_verif_subsistema_percentual": "ear_pct",
                                  "ear_verif_subsistema_mwmes": "ear_mwmes", "ear_max_subsistema": "ear_max_mwmes"})
        ear["data"] = pd.to_datetime(ear["data"]).dt.date
        out = ear[["data", "subsistema", "ear_pct", "ear_mwmes", "ear_max_mwmes"]]
    if not ena.empty:
        ena = ena.rename(columns={"ena_data": "data", "id_subsistema": "subsistema",
                                  "ena_bruta_regiao_mwmed": "ena_mwmed", "ena_bruta_regiao_percentualmlt": "ena_pct_mlt",
                                  "ena_armazenavel_regiao_mwmed": "ena_armazenavel_mwmed",
                                  "ena_armazenavel_regiao_percentualmlt": "ena_armazenavel_pct_mlt"})
        ena["data"] = pd.to_datetime(ena["data"]).dt.date
        ena = ena[["data", "subsistema", "ena_mwmed", "ena_pct_mlt", "ena_armazenavel_mwmed", "ena_armazenavel_pct_mlt"]]
        out = ena if out is None else out.merge(ena, on=["data", "subsistema"], how="outer")
    out = out[out["data"].astype(str).str[:7].isin(meses)]
    save(out, "hidro_d", meses)


def cvu(meses):
    df = load("cvu", meses)
    if df.empty:
        return
    df = df.rename(columns={"val_cvu": "cvu_rs_mwh", "id_subsistema": "subsistema"})
    df["dat_iniciosemana"] = pd.to_datetime(df["dat_iniciosemana"])
    df["mes"] = df["dat_iniciosemana"].dt.strftime("%Y-%m")
    df = df[df["mes"].isin(meses)]
    out = df[["mes", "dat_iniciosemana", "dat_fimsemana", "num_revisao", "cod_usinaplanejamento",
              "nom_usina", "subsistema", "cvu_rs_mwh", "_arquivo_origem"]].copy()
    out["data"] = out["dat_iniciosemana"].dt.date  # para save()
    for m in meses:
        part = out[out["mes"] == m].drop(columns=["_arquivo_origem", "data"])
        if len(part):
            write_parquet(part, C.PROCESSED / "cvu_semanal" / f"cvu_semanal_{m}.parquet")


def regime_metodologico(ts_local: pd.Series) -> pd.Series:
    d = ts_local.dt.date
    return pd.Series(np.select(
        [d < pd.Timestamp("2021-03-01").date(), d < pd.Timestamp("2023-04-29").date()],
        ["pre_2021_03", "2021_03_a_2023_04"], default="pos_2023_04_mmgd"), index=ts_local.index)


def carga_api(meses):
    files = sorted((RAW_ONS / "carga_api").glob("carga_verificada_*.json"))
    files = [f for f in files if any(f.name.endswith(f"_{m}.json") for m in meses)]
    if not files:
        LOG.warning("carga_api: nenhum JSON bruto para %s", meses)
        return
    parts = []
    for f in files:
        try:
            recs = json.loads(f.read_text())
        except Exception as e:
            LOG.warning("carga_api: %s ilegivel (%s)", f.name, e)
            continue
        if recs:
            parts.append(pd.DataFrame(recs))
    df = pd.concat(parts, ignore_index=True).drop_duplicates()
    # din_referenciautc = FIM da semi-hora em UTC → início da semi-hora = -30 min
    fim = pd.to_datetime(df["din_referenciautc"], utc=True)
    df["ts_utc_semihora"] = fim - pd.Timedelta(minutes=30)
    df["ts_local"] = df["ts_utc_semihora"].dt.tz_convert(C.TZ_LOCAL).dt.tz_localize(None)
    ren = {"cod_areacarga": "area_carga", "val_cargaglobal": "carga_global_mwh",
           "val_cargaglobalcons": "carga_global_consistida_mwh", "val_cargaglobalsmmgd": "carga_global_sem_mmgd_mwh",
           "val_cargasupervisionada": "carga_supervisionada_mwh", "val_carganaosupervisionada": "carga_nao_supervisionada_mwh",
           "val_cargammgd": "parcela_mmgd_mwh", "val_consistencia": "consistencia_mwh"}
    df = df.rename(columns=ren)
    vals = list(ren.values())[1:]
    g = semihour_to_hour(df, ["area_carga"], vals, min_cols=["ts_utc_semihora"])
    # aqui ts_utc é exato (veio da API em UTC): usa o início da primeira semi-hora do grupo
    g["ts_utc"] = g["ts_utc_semihora"].dt.floor("h")
    g = g.drop(columns=["ts_utc_semihora"])
    g["flag_ts_ambiguo"] = 0
    g["regime_metodologico"] = regime_metodologico(g["ts_local"])
    g["subsistema"] = g["area_carga"].where(g["area_carga"].isin(["SECO", "S", "NE", "N"]))
    g["flag_mmgd_nulo"] = g["parcela_mmgd_mwh"].isna().astype("int8")
    save(g, "carga_h", meses)


TABELAS = {
    "geracao_usina": geracao_usina, "fator_capacidade": fator_capacidade, "termica_motivo": termica_motivo,
    "curtailment": curtailment, "balanco": balanco, "curva_carga": curva_carga, "intercambio": intercambio,
    "cmo": cmo, "hidro": hidro, "cvu": cvu, "carga_api": carga_api,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*"); ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--so", nargs="*", choices=list(TABELAS))
    ap.add_argument("--lote", type=int, default=12, help="meses por lote (anuais do ONS sao lidos uma vez por lote)")
    a = ap.parse_args()
    meses = parse_months(a.meses, a.inicio, a.fim)
    alvo = a.so or list(TABELAS)
    for i in range(0, len(meses), a.lote):
        lote = meses[i:i + a.lote]
        LOG.info("=== lote %s..%s", lote[0], lote[-1])
        for t in alvo:
            try:
                TABELAS[t](lote)
            except Exception as e:
                LOG.exception("%s falhou no lote %s: %s", t, lote[0], e)


if __name__ == "__main__":
    main()
