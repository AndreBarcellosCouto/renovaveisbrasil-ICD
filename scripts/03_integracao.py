"""Integração: dimensões, capacidade mensal, preço, clima agregado e painéis analíticos.

Uso: python scripts/03_integracao.py --meses 2021-08 2025-08
Etapas (todas idempotentes; --so para escolher): dim_tempo, dim_usina, capacidade, preco,
clima_agregado, painel_subsistema, painel_uf. Requer saídas de 02_*.
"""
from __future__ import annotations

import argparse
import difflib
import re
import unicodedata

import numpy as np
import pandas as pd

import config as C
from common import LOG, parse_months, write_parquet

P = C.PROCESSED
SUBS = ["SE", "S", "NE", "N"]

# --------------------------------------------------------------- fatores de emissão (D08)
# tCO2/TJ (IPCC 2006, vol.2, tab.2.2) × 3,6 TJ/GWh ÷ eficiência → tCO2/MWh gerado
IPCC_TCO2_TJ = {"gas_natural": 56.1, "oleo_diesel": 74.1, "oleo_combustivel": 77.4,
                "carvao": 96.1, "gas_processo": 56.1, "gnl": 56.1}
EFICIENCIA = {"gas_natural": 0.45, "gnl": 0.45, "oleo_diesel": 0.38, "oleo_combustivel": 0.38,
              "carvao": 0.33, "gas_processo": 0.35}


def fator_tco2_mwh(comb: str) -> float | None:
    if comb not in IPCC_TCO2_TJ:
        return None
    return IPCC_TCO2_TJ[comb] * 3.6e-3 / EFICIENCIA[comb]


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def classificar(tipo: str, comb: str) -> tuple[str, str | None]:
    """→ (grupo, combustivel_padronizado)."""
    t, c = norm(tipo), norm(comb)
    # tipo da usina primeiro: há conjuntos solares com combustível "Eólica" no cadastro (CJU_CEUFAL, D26)
    for chave, grupo in (("eol", "eolica"), ("foto", "solar"), ("solar", "solar"), ("hidr", "hidro"), ("nucle", "nuclear")):
        if chave in t:
            return grupo, None
    if "eol" in c:
        return "eolica", None
    if "solar" in c:
        return "solar", None
    if "hidr" in c:
        return "hidro", None
    if "uran" in c or "nucle" in c:
        return "nuclear", None
    if "term" in t or "ute" in t or c:
        if any(k in c for k in ["bagaco", "biomassa", "biogas", "licor", "residu", "lenha", "casca", "capim", "carvao vegetal", "etanol"]):
            return "biomassa", "biomassa"
        if "gnl" in c:
            return "fossil", "gnl"
        if "gas natural" in c or c.startswith("gas") and "processo" not in c:
            return "fossil", "gas_natural"
        if "processo" in c or "siderurg" in c or "alto forno" in c or "coqueria" in c:
            return "fossil", "gas_processo"
        if "diesel" in c:
            return "fossil", "oleo_diesel"
        if "oleo" in c or "combustivel" in c:
            return "fossil", "oleo_combustivel"
        if "carvao" in c:
            return "fossil", "carvao"
        return "outro", None
    return "outro", None


def read_parts(tabela: str, meses: list[str]) -> pd.DataFrame:
    fs = [P / tabela / f"{tabela}_{m}.parquet" for m in meses]
    fs = [f for f in fs if f.exists()]
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


# --------------------------------------------------------------- dim_tempo
def feriados_br(anos) -> set:
    """Feriados nacionais (lei 662/1949, 6.802/1980, 14.759/2023) + pontos facultativos de
    Carnaval/Corpus Christi. Usa o pacote `holidays` se instalado; senão, cálculo próprio."""
    try:
        import holidays
        return set(holidays.country_holidays("BR", years=anos).keys())
    except ImportError:
        from dateutil.easter import easter
        from datetime import date, timedelta
        out = set()
        for y in anos:
            for md in ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)):
                out.add(date(y, *md))
            if y >= 2024:
                out.add(date(y, 11, 20))
            e = easter(y)
            out |= {e - timedelta(48), e - timedelta(47), e - timedelta(2), e + timedelta(60)}
        return out


def dim_tempo(meses: list[str]) -> None:
    t0 = pd.Period(min(meses), "M").start_time.tz_localize(C.TZ_LOCAL)
    t1 = (pd.Period(max(meses), "M").end_time.floor("h")).tz_localize(C.TZ_LOCAL)
    idx = pd.date_range(t0.tz_convert("UTC"), t1.tz_convert("UTC"), freq="h")
    loc = idx.tz_convert(C.TZ_LOCAL)
    br = feriados_br(range(loc.year.min(), loc.year.max() + 1))
    df = pd.DataFrame({"ts_utc": idx, "ts_local": loc.tz_localize(None)})
    df["data_local"] = loc.date; df["hora_local"] = loc.hour.astype("int8")
    df["dia_semana"] = loc.dayofweek.astype("int8"); df["mes"] = loc.month.astype("int8"); df["ano"] = loc.year.astype("int16")
    df["feriado_nacional"] = pd.Series(df["data_local"]).map(lambda d: d in br).astype("int8").values
    df["fim_de_semana_ou_feriado"] = ((df["dia_semana"] >= 5) | (df["feriado_nacional"] == 1)).astype("int8")
    if (P / "dim_tempo.parquet").exists():
        old = pd.read_parquet(P / "dim_tempo.parquet")
        df = pd.concat([old, df]).drop_duplicates("ts_utc").sort_values("ts_utc")
    write_parquet(df, P / "dim_tempo.parquet")


# --------------------------------------------------------------- dim_usina
def load_cadastro(nome: str, stem: str) -> pd.DataFrame:
    d = C.RAW / "ons" / "cadastros" / nome
    for ext in ("parquet", "csv"):
        p = d / f"{stem}.{ext}"
        if p.exists():
            df = pd.read_parquet(p) if ext == "parquet" else pd.read_csv(p, sep=None, engine="python")
            df.columns = [c.lower() for c in df.columns]
            return df
    LOG.warning("cadastro %s ausente", nome)
    return pd.DataFrame()


def uf_subsistema() -> pd.DataFrame:
    cap = load_cadastro("capacidade_geracao", "CAPACIDADE_GERACAO")
    if cap.empty:
        return pd.DataFrame(columns=["uf", "subsistema"])
    m = (cap.groupby(["id_estado", "id_subsistema"]).size().reset_index(name="n")
         .sort_values("n", ascending=False).drop_duplicates("id_estado"))
    m = m.rename(columns={"id_estado": "uf", "id_subsistema": "subsistema"})[["uf", "subsistema"]]
    write_parquet(m, P / "uf_subsistema.parquet")
    return m


def ceg_para_id_ons(ger: pd.DataFrame, mod: pd.DataFrame) -> dict:
    """CAPACIDADE_GERACAO não traz id_ons, e a geração horária é reportada pelo id do
    conjunto (usinas II-C) ou do agrupamento de pequenas usinas (tipo III), sem CEG.
    Mapeia CEG → id_ons na ordem: id observado na geração, conjunto, pequenas usinas,
    modalidade_usina."""
    m: dict = {}

    def add(df: pd.DataFrame, c_ceg: str, c_id: str) -> None:
        if df.empty or c_ceg not in df or c_id not in df:
            return
        d = df.dropna(subset=[c_ceg, c_id]).drop_duplicates(c_ceg)
        for k, v in zip(d[c_ceg], d[c_id]):
            m.setdefault(k, v)

    add(ger, "ceg", "id_ons")
    add(load_cadastro("usina_conjunto", "RELACIONAMENTO_USINA_CONJUNTO"), "ceg", "id_ons_conjunto")
    add(load_cadastro("usina_pqu", "RELACIONAMENTO_USINA_PEQUENAUSINA"), "ceg", "id_ons_pequenasusinas")
    add(mod, "ceg", "id_ons")
    return m


def dim_usina(meses: list[str]) -> None:
    cap = load_cadastro("capacidade_geracao", "CAPACIDADE_GERACAO")
    mod = load_cadastro("modalidade_usina", "MODALIDADE_USINA")
    ger = read_parts("geracao_usina_h", meses)
    fc = read_parts("fator_capacidade_renovavel_h", meses)
    siga = pd.read_parquet(P / "siga_usinas.parquet") if (P / "siga_usinas.parquet").exists() else pd.DataFrame()

    # 1) base: cadastro de unidades geradoras → usina
    cap["ceg"] = cap["ceg"].replace({"-": None})
    if "id_ons" not in cap:
        cap["id_ons"] = cap["ceg"].map(ceg_para_id_ons(ger, mod))
    cap["chave"] = cap["id_ons"].fillna(cap["ceg"])
    cap["dat_entradaoperacao"] = pd.to_datetime(cap["dat_entradaoperacao"], errors="coerce")
    cap["dat_desativacao"] = pd.to_datetime(cap["dat_desativacao"], errors="coerce")
    ativa = cap["dat_desativacao"].isna()
    base = cap.groupby("chave").agg(
        id_ons=("id_ons", "first"), ceg_ons=("ceg", "first"), nome=("nom_usina", "first"),
        tipo_usina=("nom_tipousina", "first"), combustivel_ons=("nom_combustivel", "first"),
        modalidade_ons=("nom_modalidadeoperacao", "first"), subsistema=("id_subsistema", "first"),
        uf=("id_estado", "first"), data_inicio_operacao=("dat_entradaoperacao", "min"),
        potencia_total_mw=("val_potenciaefetiva", "sum")).reset_index()
    pot_ativa = cap[ativa].groupby("chave")["val_potenciaefetiva"].sum().rename("potencia_mw")
    base = base.merge(pot_ativa, on="chave", how="left")
    base["potencia_mw"] = base["potencia_mw"].fillna(0.0)
    base["origem_cadastro"] = "capacidade_geracao"

    # 2) ids vistos na geração horária que não estão no cadastro (conjuntos II-C, grupos III)
    if not ger.empty:
        vis = ger.groupby("id_ons").agg(ceg_ons=("ceg", "first"), nome=("nom_usina", "first"),
                                        tipo_usina=("nom_tipousina", "first"), combustivel_ons=("nom_tipocombustivel", "first"),
                                        modalidade_ons=("cod_modalidadeoperacao", "first"), subsistema=("id_subsistema", "first"),
                                        uf=("id_estado", "first")).reset_index()
        novos = vis[~vis["id_ons"].isin(base["id_ons"])].copy()
        novos["chave"] = novos["id_ons"]; novos["origem_cadastro"] = "geracao_usina_h"
        base = pd.concat([base, novos], ignore_index=True)

    base[["grupo", "combustivel"]] = base.apply(lambda r: pd.Series(classificar(r["tipo_usina"], r["combustivel_ons"])), axis=1)
    base["fonte"] = base["grupo"].map({"eolica": "eolica", "solar": "solar", "hidro": "hidro", "nuclear": "nuclear",
                                       "fossil": "termica", "biomassa": "termica", "outro": "outro"})

    # 3) coordenadas: (a) fator de capacidade (eólica/solar, subestação coletora)
    base["lat"] = np.nan; base["lon"] = np.nan; base["qualidade_match"] = "sem_match"; base["fonte_coord"] = None
    if not fc.empty and "val_latitudesecoletora" in fc:
        xy = fc.dropna(subset=["val_latitudesecoletora"]).groupby("id_ons")[["val_latitudesecoletora", "val_longitudesecoletora"]].first()
        m = base["id_ons"].map(xy["val_latitudesecoletora"]); base.loc[m.notna(), "lat"] = m
        m2 = base["id_ons"].map(xy["val_longitudesecoletora"]); base.loc[m2.notna(), "lon"] = m2
        base.loc[m.notna(), ["qualidade_match", "fonte_coord"]] = ["exato", "ons_fator_capacidade_coletora"]

    # (b) SIGA por CEG exato; (c) nome aproximado dentro da mesma UF e tipo
    base["ceg_aneel"] = None
    if not siga.empty:
        # núcleo do CEG (sem o sufixo de versão): ONS grava "…001161-4.01", ANEEL "…001161-4.1" (D30)
        nucleo = lambda s: s.astype(str).str.upper().str.strip().str.replace(r"\.\d+$", "", regex=True).str.replace(r"[^A-Z0-9]", "", regex=True)
        siga = siga.copy(); siga["ceg_n"] = nucleo(siga["ceg_aneel"])
        base["ceg_n"] = nucleo(base["ceg_ons"])
        s1 = siga.drop_duplicates("ceg_n").set_index("ceg_n")
        hit = base["ceg_n"].isin(s1.index) & base["ceg_n"].ne("") & base["ceg_n"].ne("NONE")
        base.loc[hit, "ceg_aneel"] = base.loc[hit, "ceg_n"].map(s1["ceg_aneel"])
        need = hit & base["lat"].isna()
        base.loc[need, "lat"] = base.loc[need, "ceg_n"].map(s1["lat"]); base.loc[need, "lon"] = base.loc[need, "ceg_n"].map(s1["lon"])
        base.loc[need & base["lat"].notna(), ["qualidade_match", "fonte_coord"]] = ["exato", "siga_ceg"]
        sem_data = hit & base["data_inicio_operacao"].isna()
        base.loc[sem_data, "data_inicio_operacao"] = base.loc[sem_data, "ceg_n"].map(s1["data_inicio_operacao"])
        # aproximado por nome
        siga["nome_n"] = siga["nome_aneel"].map(norm)
        rev = []
        for i, r in base[base["lat"].isna()].iterrows():
            cand = siga[(siga["uf"] == r["uf"]) & siga["lat"].notna()]
            if cand.empty or not r["nome"]:
                continue
            best = difflib.get_close_matches(norm(r["nome"]), cand["nome_n"].tolist(), n=1, cutoff=0.85)
            if best:
                c = cand[cand["nome_n"] == best[0]].iloc[0]
                base.loc[i, ["lat", "lon", "qualidade_match", "fonte_coord", "ceg_aneel"]] = [c["lat"], c["lon"], "aproximado", "siga_nome", c["ceg_aneel"]]
                rev.append(dict(id_ons=r["id_ons"], nome_ons=r["nome"], nome_aneel=c["nome_aneel"], ceg_aneel=c["ceg_aneel"], uf=r["uf"]))
        if rev:
            pd.DataFrame(rev).to_csv(C.DOCS / "revisao_match_usinas.csv", index=False)
            LOG.info("dim_usina: %d correspondencias aproximadas gravadas em docs/revisao_match_usinas.csv", len(rev))

    # 4) município por ponto-em-polígono
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        mun = gpd.read_file(f"zip://{C.RAW / 'ibge' / 'BR_Municipios_2024.zip'}").to_crs("EPSG:4326")
        # revisão manual (D32): coordenada errada na fonte → centroide do município declarado pela ANEEL
        rev_p = C.DOCS / "revisao_manual_coordenadas.csv"
        if rev_p.exists():
            rev = pd.read_csv(rev_p)
            rev = rev[rev["classificacao"] == "corrigir_centroide_municipio"]
            cent = mun.to_crs("EPSG:5880").copy()
            cent["geometry"] = cent.geometry.representative_point()
            cent = cent.to_crs("EPSG:4326")
            cent["k"] = cent["NM_MUN"].map(norm) + "|" + cent["SIGLA_UF"]
            cent = cent.drop_duplicates("k").set_index("k")
            for _, r in rev.iterrows():
                k = norm(r["municipio"]) + "|" + r["uf_municipio"]
                sel = base["id_ons"] == r["id_ons"]
                if k not in cent.index or not sel.any():
                    LOG.warning("revisao manual: %s / %s nao aplicada", r["id_ons"], k)
                    continue
                pt = cent.loc[k, "geometry"]
                base.loc[sel, ["lat", "lon", "qualidade_match", "fonte_coord"]] = [pt.y, pt.x, "centroide_municipio", "revisao_manual"]
            LOG.info("revisao manual de coordenadas: %d correcoes aplicadas", len(rev))
            rem = pd.read_csv(rev_p).query("classificacao == 'remover_coordenada'")["id_ons"]
            sel = base["id_ons"].isin(rem)
            base.loc[sel, ["lat", "lon", "ceg_aneel"]] = [np.nan, np.nan, None]
            base.loc[sel, ["qualidade_match", "fonte_coord"]] = ["sem_match", "revisao_manual_removida"]
        ok = base["lat"].notna()
        pts = gpd.GeoDataFrame(base.loc[ok, ["chave"]], geometry=[Point(x, y) for x, y in zip(base.loc[ok, "lon"], base.loc[ok, "lat"])], crs="EPSG:4326")
        j = gpd.sjoin(pts, mun[["CD_MUN", "NM_MUN", "SIGLA_UF", "geometry"]], how="left", predicate="within")
        j = j.drop_duplicates("chave").set_index("chave")
        base["cod_municipio_ibge"] = base["chave"].map(j["CD_MUN"]); base["municipio"] = base["chave"].map(j["NM_MUN"])
        base["uf_geo"] = base["chave"].map(j["SIGLA_UF"])
        base["flag_uf_diverge"] = (base["uf_geo"].notna() & (base["uf_geo"] != base["uf"])).astype("int8")
        if rev_p.exists():  # divisas conferidas à mão
            div = pd.read_csv(rev_p).query("classificacao == 'divisa'")["id_ons"]
            rv = pd.read_csv(rev_p).set_index("id_ons")["classificacao"]
            base["revisao_coordenada"] = base["id_ons"].map(rv.replace({"divisa": "divisa_conferida", "corrigir_centroide_municipio": "corrigida",
                                                                        "remover_coordenada": "removida", "match_aproximado_aceito": "aproximado_aceito"}))
    except Exception as e:
        LOG.warning("municipio por coordenada nao calculado: %s", e)

    base = base.drop(columns=[c for c in ["ceg_n"] if c in base])
    write_parquet(base, P / "dim_usina.parquet")
    tot = base["potencia_mw"].sum()
    sem = base.loc[base["lat"].isna(), "potencia_mw"].sum()
    LOG.info("dim_usina: %d usinas; %.1f%% da potencia sem coordenada", len(base), 100 * sem / tot if tot else float("nan"))


# --------------------------------------------------------------- capacidade mensal
def capacidade_mensal(meses: list[str]) -> None:
    cap = load_cadastro("capacidade_geracao", "CAPACIDADE_GERACAO")
    if cap.empty:
        return
    cap["dat_entradaoperacao"] = pd.to_datetime(cap["dat_entradaoperacao"], errors="coerce")
    cap["dat_desativacao"] = pd.to_datetime(cap["dat_desativacao"], errors="coerce")
    cap[["grupo", "combustivel"]] = cap.apply(lambda r: pd.Series(classificar(r["nom_tipousina"], r["nom_combustivel"])), axis=1)
    rows = []
    for m in meses:
        p = pd.Period(m, "M")
        on = (cap["dat_entradaoperacao"] <= p.end_time) & (cap["dat_desativacao"].isna() | (cap["dat_desativacao"] > p.start_time))
        g = cap[on].groupby(["id_estado", "id_subsistema", "grupo"])["val_potenciaefetiva"].sum().reset_index()
        g["mes"] = m; rows.append(g)
    out = pd.concat(rows).rename(columns={"id_estado": "uf", "id_subsistema": "subsistema", "val_potenciaefetiva": "potencia_mw"})
    out["flag_sem_data_operacao_excluida"] = 0
    n_sem = cap["dat_entradaoperacao"].isna().sum()
    if n_sem:
        LOG.warning("capacidade_mensal: %d unidades sem data de entrada em operacao (excluidas)", n_sem)
    old = pd.read_parquet(P / "capacidade_mensal.parquet") if (P / "capacidade_mensal.parquet").exists() else pd.DataFrame()
    out = pd.concat([old[~old["mes"].isin(meses)] if len(old) else old, out], ignore_index=True)
    write_parquet(out, P / "capacidade_mensal.parquet")


# --------------------------------------------------------------- preço
def preco(meses: list[str]) -> None:
    pld = read_parts("pld_h", meses); cmo = read_parts("cmo_h", meses)
    if pld.empty and cmo.empty:
        return
    if not cmo.empty:
        cmo = cmo.rename(columns={"submercado": "submercado"})[["ts_utc", "ts_local", "submercado", "cmo_rs_mwh", "flag_hora_incompleta"]]
    out = pld[["ts_utc", "ts_local", "submercado", "pld_rs_mwh"]] if not pld.empty else cmo[["ts_utc", "ts_local", "submercado"]]
    if not cmo.empty:
        out = out.merge(cmo, on=["ts_utc", "ts_local", "submercado"], how="outer") if not pld.empty else cmo
    for c in ("pld_rs_mwh", "cmo_rs_mwh"):
        if c not in out:
            out[c] = np.nan
    out["flag_pld_nulo"] = out["pld_rs_mwh"].isna().astype("int8")
    out["flag_cmo_nulo"] = out["cmo_rs_mwh"].isna().astype("int8")
    for m in meses:
        part = out[out["ts_local"].dt.strftime("%Y-%m") == m]
        if len(part):
            write_parquet(part, P / "preco_h" / f"preco_h_{m}.parquet")


# --------------------------------------------------------------- clima agregado
def celula_de(lat: pd.Series, lon: pd.Series, cel: pd.DataFrame) -> pd.Series:
    """Célula mais próxima (grade regular 0,5°)."""
    step = C.ERA5_GRID[0]
    la = (lat / step).round() * step; lo = (lon / step).round() * step
    key = pd.Series([f"{a:.2f}_{b:.2f}" for a, b in zip(la, lo)], index=lat.index)
    cel_key = pd.Series(cel["id_celula"].values, index=[f"{a:.2f}_{b:.2f}" for a, b in zip(cel["lat"], cel["lon"])])
    return key.map(cel_key)


def pesos_mes(m: str, cel: pd.DataFrame) -> pd.DataFrame | None:
    """Capacidade média no mês por id_ons eólico/solar, com coordenada da subestação coletora,
    UF e subsistema da própria usina (fator_capacidade_renovavel_h). None se a tabela não existir."""
    f = P / "fator_capacidade_renovavel_h" / f"fator_capacidade_renovavel_h_{m}.parquet"
    if not f.exists():
        return None
    fc = pd.read_parquet(f, columns=["id_ons", "id_estado", "id_subsistema", "nom_tipousina", "val_latitudesecoletora",
                                     "val_longitudesecoletora", "capacidade_instalada_mw"])
    fc = fc.dropna(subset=["val_latitudesecoletora", "val_longitudesecoletora"])
    u = fc.groupby("id_ons").agg(uf=("id_estado", "first"), subsistema=("id_subsistema", "first"), tipo=("nom_tipousina", "first"),
                                 lat=("val_latitudesecoletora", "first"), lon=("val_longitudesecoletora", "first"),
                                 cap_mw=("capacidade_instalada_mw", "mean")).reset_index()
    t = u["tipo"].map(norm)  # "Eólica"/"Solar"
    u["grupo"] = np.where(t.str.contains("eol"), "eolica", np.where(t.str.contains("foto|solar"), "solar", None))
    u["id_celula"] = celula_de(u["lat"], u["lon"], cel)
    return u.dropna(subset=["grupo", "id_celula"]).query("cap_mw > 0")


def clima_agregado(meses: list[str]) -> None:
    if not (P / "dim_celula.parquet").exists():
        LOG.warning("dim_celula ausente; clima_agregado pulado"); return
    cel = pd.read_parquet(P / "dim_celula.parquet")
    us = uf_subsistema()
    cel = cel.drop(columns=["subsistema"]).merge(us, on="uf", how="left")
    write_parquet(cel, P / "dim_celula.parquet")
    dim = pd.read_parquet(P / "dim_usina.parquet") if (P / "dim_usina.parquet").exists() else pd.DataFrame()
    pesos = {}
    if not dim.empty:
        d = dim.dropna(subset=["lat"]).copy()
        d["id_celula"] = celula_de(d["lat"], d["lon"], cel)
        for g in ("eolica", "solar"):
            w = d[d["grupo"] == g].groupby("id_celula")["potencia_mw"].sum()
            pesos[f"ponderada_cap_{g}"] = w[w > 0]
    for m in meses:
        f = P / "clima_h" / f"clima_h_{m}.parquet"
        if not f.exists():
            continue
        cl = pd.read_parquet(f).merge(cel[["id_celula", "uf", "subsistema"]], on="id_celula", how="left")
        pm = pesos_mes(m, cel)
        outs = []
        for unidade in ("uf", "subsistema"):
            g = cl.groupby(["ts_utc", unidade])[["ws100_ms", "ghi_wm2", "t2m_c"]].mean().reset_index()
            g["unidade_tipo"] = unidade; g = g.rename(columns={unidade: "unidade"}); g["metodo"] = "media_area"; g["n_celulas"] = cl.groupby(["ts_utc", unidade]).size().values
            outs.append(g)
            if pm is not None:
                # D28: pesos = capacidade das usinas que geram no mês (fator_capacidade), agrupados pela
                # UF/subsistema da USINA (o mesmo da geração), não pela UF geográfica da célula
                for grupo in ("eolica", "solar"):
                    w = pm[pm["grupo"] == grupo].groupby([unidade, "id_celula"])["cap_mw"].sum().rename("w").reset_index()
                    sub = cl[["ts_utc", "id_celula", "ws100_ms", "ghi_wm2", "t2m_c"]].merge(w, on="id_celula")
                    for c in ["ws100_ms", "ghi_wm2", "t2m_c"]:
                        sub[c] = sub[c] * sub["w"]
                    gg = sub.groupby(["ts_utc", unidade]).agg(ws100_ms=("ws100_ms", "sum"), ghi_wm2=("ghi_wm2", "sum"), t2m_c=("t2m_c", "sum"), w=("w", "sum"), n_celulas=("w", "size")).reset_index()
                    for c in ["ws100_ms", "ghi_wm2", "t2m_c"]:
                        gg[c] = gg[c] / gg["w"]
                    gg["unidade_tipo"] = unidade; gg = gg.rename(columns={unidade: "unidade"}).drop(columns="w"); gg["metodo"] = f"ponderada_cap_{grupo}"
                    outs.append(gg)
                continue
            for metodo, w in pesos.items():
                sub = cl[cl["id_celula"].isin(w.index)].copy()
                sub["w"] = sub["id_celula"].map(w)
                for c in ["ws100_ms", "ghi_wm2", "t2m_c"]:
                    sub[c] = sub[c] * sub["w"]
                gg = sub.groupby(["ts_utc", unidade]).agg(ws100_ms=("ws100_ms", "sum"), ghi_wm2=("ghi_wm2", "sum"), t2m_c=("t2m_c", "sum"), w=("w", "sum"), n_celulas=("w", "size")).reset_index()
                for c in ["ws100_ms", "ghi_wm2", "t2m_c"]:
                    gg[c] = gg[c] / gg["w"]
                gg["unidade_tipo"] = unidade; gg = gg.rename(columns={unidade: "unidade"}).drop(columns="w"); gg["metodo"] = metodo
                outs.append(gg)
        out = pd.concat(outs, ignore_index=True).dropna(subset=["unidade"])
        write_parquet(out, P / "clima_agregado_h" / f"clima_agregado_h_{m}.parquet")


# --------------------------------------------------------------- painéis
def _ger_por_grupo(meses, chave: str) -> pd.DataFrame:
    ger = read_parts("geracao_usina_h", meses)
    if ger.empty:
        return pd.DataFrame()
    dim = pd.read_parquet(P / "dim_usina.parquet")[["id_ons", "grupo", "combustivel"]]
    ger = ger.merge(dim, on="id_ons", how="left")
    ger["grupo"] = ger["grupo"].fillna("outro")
    ger["id_estado"] = ger["id_estado"].replace({"I": "PY"})  # Itaipu 50 Hz (Paraguai), como em dim_usina
    col = "id_subsistema" if chave == "subsistema" else "id_estado"
    # sistemas isolados (D27): fora do SIN → fora do painel por subsistema; no painel por UF ficam, com coluna à parte
    fora = ger[ger["flag_fora_balanco_sin"] == 1] if "flag_fora_balanco_sin" in ger else ger.iloc[:0]
    iso = fora.groupby(["ts_utc", col])["geracao_mwh"].sum().rename("ger_fora_sin_mwh").reset_index().rename(columns={col: chave})
    if chave == "subsistema" and len(fora):
        ger = ger[ger["flag_fora_balanco_sin"] != 1]
    g = ger.pivot_table(index=["ts_utc", col], columns="grupo", values="geracao_mwh", aggfunc="sum").reset_index()
    g = g.rename(columns={col: chave, **{k: f"ger_{k}_mwh" for k in ["hidro", "fossil", "biomassa", "nuclear", "eolica", "solar", "outro"]}})
    # emissões estimadas (D08)
    ger["fator"] = ger["combustivel"].map(lambda c: fator_tco2_mwh(c) if isinstance(c, str) else None)
    em = ger[ger["grupo"] == "fossil"].assign(e=lambda d: d["geracao_mwh"] * d["fator"]).groupby(["ts_utc", col])["e"].sum().rename("emissoes_estimadas_tco2").reset_index().rename(columns={col: chave})
    semf = ger[(ger["grupo"] == "fossil") & ger["fator"].isna()].groupby(["ts_utc", col])["geracao_mwh"].sum().rename("ger_fossil_sem_fator_mwh").reset_index().rename(columns={col: chave})
    return (g.merge(em, on=["ts_utc", chave], how="left").merge(semf, on=["ts_utc", chave], how="left")
            .merge(iso, on=["ts_utc", chave], how="left"))


def painel_subsistema(meses: list[str]) -> None:
    g = _ger_por_grupo(meses, "subsistema")
    if g.empty:
        return
    carga = read_parts("carga_h", meses)
    if not carga.empty:
        carga = carga[carga["subsistema"].notna()][["ts_utc", "subsistema", "carga_global_mwh", "parcela_mmgd_mwh", "regime_metodologico", "flag_mmgd_nulo"]]
        # códigos de área SECO→SE
        carga["subsistema"] = carga["subsistema"].replace({"SECO": "SE"})
        g = g.merge(carga, on=["ts_utc", "subsistema"], how="outer")
    tm = read_parts("termica_motivo_h", meses)
    if not tm.empty:
        dim = pd.read_parquet(P / "dim_usina.parquet")
        cegmap = dim.dropna(subset=["ceg_ons"]).drop_duplicates("ceg_ons").set_index("ceg_ons")["grupo"]
        tm["grupo"] = tm["ceg"].map(cegmap).fillna("fossil")  # térmica sem CEG no cadastro: assume fóssil, flag
        tm["flag_grupo_assumido"] = tm["ceg"].map(cegmap).isna().astype("int8")
        piv = tm[tm["grupo"] == "fossil"].pivot_table(index=["ts_utc", "id_subsistema"], columns="motivo", values="geracao_verificada_mwh", aggfunc="sum")
        piv.columns = [f"term_fossil_{c}_mwh" for c in piv.columns]
        g = g.merge(piv.reset_index().rename(columns={"id_subsistema": "subsistema"}), on=["ts_utc", "subsistema"], how="left")
    cu = read_parts("curtailment_h", meses)
    if not cu.empty:
        c = cu.groupby(["ts_utc", "id_subsistema", "fonte"]).agg(v=("geracao_verificada_mwh", "sum"), r=("geracao_referencia_mwh", "sum")).reset_index()
        c["corte_mwh"] = (c["r"] - c["v"]).clip(lower=0)
        piv = c.pivot_table(index=["ts_utc", "id_subsistema"], columns="fonte", values=["corte_mwh", "r"], aggfunc="sum")
        piv.columns = [f"curtail_{a}_{b}" if a == "corte_mwh" else f"ref_{b}_mwh" for a, b in piv.columns]
        g = g.merge(piv.reset_index().rename(columns={"id_subsistema": "subsistema"}), on=["ts_utc", "subsistema"], how="left")
    ic = read_parts("intercambio_h", meses)
    if not ic.empty:
        exp_ = ic.groupby(["ts_utc", "origem"])["fluxo_mwh"].sum().rename("exp").reset_index().rename(columns={"origem": "subsistema"})
        imp_ = ic.groupby(["ts_utc", "destino"])["fluxo_mwh"].sum().rename("imp").reset_index().rename(columns={"destino": "subsistema"})
        n = exp_.merge(imp_, on=["ts_utc", "subsistema"], how="outer").fillna(0.0)
        n["intercambio_liquido_mwh"] = n["imp"] - n["exp"]
        g = g.merge(n[["ts_utc", "subsistema", "intercambio_liquido_mwh"]], on=["ts_utc", "subsistema"], how="left")
    pr = read_parts("preco_h", meses)
    if not pr.empty:
        g = g.merge(pr[["ts_utc", "submercado", "pld_rs_mwh", "cmo_rs_mwh"]].rename(columns={"submercado": "subsistema"}), on=["ts_utc", "subsistema"], how="left")
    hd = read_parts("hidro_d", meses)
    if not hd.empty:
        g["data_local"] = pd.to_datetime(g["ts_utc"], utc=True).dt.tz_convert(C.TZ_LOCAL).dt.date
        hd["data"] = pd.to_datetime(hd["data"]).dt.date
        g = g.merge(hd.rename(columns={"data": "data_local"})[["data_local", "subsistema", "ear_pct", "ena_mwmed", "ena_pct_mlt"]], on=["data_local", "subsistema"], how="left")
    ca = read_parts("clima_agregado_h", meses)
    if not ca.empty:
        for met, suf in (("media_area", ""), ("ponderada_cap_eolica", "_pe"), ("ponderada_cap_solar", "_ps")):
            x = ca[(ca["unidade_tipo"] == "subsistema") & (ca["metodo"] == met)][["ts_utc", "unidade", "ws100_ms", "ghi_wm2", "t2m_c"]]
            x = x.rename(columns={"unidade": "subsistema", "ws100_ms": f"ws100_ms{suf}", "ghi_wm2": f"ghi_wm2{suf}", "t2m_c": f"t2m_c{suf}"})
            g = g.merge(x, on=["ts_utc", "subsistema"], how="left")
    bal = read_parts("balanco_subsistema_h", meses)
    if not bal.empty:
        g = g.merge(bal[["ts_utc", "subsistema", "carga_mwh", "ger_hidraulica_mwh", "ger_termica_mwh", "ger_eolica_mwh", "ger_solar_mwh", "intercambio_liquido_mwh"]]
                    .rename(columns=lambda c: c if c in ("ts_utc", "subsistema") else f"bal_{c}"), on=["ts_utc", "subsistema"], how="left")
        # balanço inclui intercâmbio internacional (S ↔ Argentina/Uruguai); intercambio_h só o nacional
        if "intercambio_liquido_mwh" in g:
            g["intercambio_internacional_mwh"] = (g["bal_intercambio_liquido_mwh"] - g["intercambio_liquido_mwh"]).round(3)
    om = read_parts("mcti_margem_operacao_h", meses)
    if not om.empty:  # fator marginal oficial do SIN (MCTI/MDL, D29): mesmo valor nos 4 subsistemas
        g = g.merge(om[["ts_utc", "fator_om_tco2_mwh"]].rename(columns={"fator_om_tco2_mwh": "fator_om_mcti_tco2_mwh"}), on="ts_utc", how="left")
    for c in ["ger_eolica_mwh", "ger_solar_mwh", "parcela_mmgd_mwh"]:
        if c not in g:
            g[c] = np.nan
    g["carga_liquida_mwh"] = g["carga_global_mwh"] - g["ger_eolica_mwh"].fillna(0) - g["ger_solar_mwh"].fillna(0) - g["parcela_mmgd_mwh"].fillna(0)
    g["flag_carga_liquida_sem_mmgd"] = g["parcela_mmgd_mwh"].isna().astype("int8")
    g["ts_local"] = pd.to_datetime(g["ts_utc"], utc=True).dt.tz_convert(C.TZ_LOCAL).dt.tz_localize(None)
    g = g[g["subsistema"].isin(SUBS)].sort_values(["ts_utc", "subsistema"])
    for m in meses:
        part = g[g["ts_local"].dt.strftime("%Y-%m") == m]
        if len(part):
            write_parquet(part, C.ANALYTIC / "painel_subsistema_h" / f"painel_subsistema_h_{m}.parquet")


def painel_uf(meses: list[str]) -> None:
    g = _ger_por_grupo(meses, "uf")
    if g.empty:
        return
    carga = read_parts("carga_h", meses)
    if not carga.empty:
        ufs = carga[carga["area_carga"].str.len() == 2]
        if len(ufs):
            g = g.merge(ufs[["ts_utc", "area_carga", "carga_global_mwh", "parcela_mmgd_mwh", "regime_metodologico"]].rename(columns={"area_carga": "uf"}), on=["ts_utc", "uf"], how="left")
    cu = read_parts("curtailment_h", meses)
    if not cu.empty:
        c = cu.groupby(["ts_utc", "id_estado", "fonte"]).agg(v=("geracao_verificada_mwh", "sum"), r=("geracao_referencia_mwh", "sum")).reset_index()
        c["corte_mwh"] = (c["r"] - c["v"]).clip(lower=0)
        piv = c.pivot_table(index=["ts_utc", "id_estado"], columns="fonte", values="corte_mwh", aggfunc="sum")
        piv.columns = [f"curtail_{b}_mwh" for b in piv.columns]
        g = g.merge(piv.reset_index().rename(columns={"id_estado": "uf"}), on=["ts_utc", "uf"], how="left")
    cap = pd.read_parquet(P / "capacidade_mensal.parquet") if (P / "capacidade_mensal.parquet").exists() else pd.DataFrame()
    g["ts_local"] = pd.to_datetime(g["ts_utc"], utc=True).dt.tz_convert(C.TZ_LOCAL).dt.tz_localize(None)
    g["mes"] = g["ts_local"].dt.strftime("%Y-%m")
    if not cap.empty:
        piv = cap.pivot_table(index=["mes", "uf"], columns="grupo", values="potencia_mw", aggfunc="sum")
        piv.columns = [f"cap_{c}_mw" for c in piv.columns]
        g = g.merge(piv.reset_index(), on=["mes", "uf"], how="left")
    ca = read_parts("clima_agregado_h", meses)
    if not ca.empty:
        for met, suf in (("media_area", ""), ("ponderada_cap_eolica", "_pe"), ("ponderada_cap_solar", "_ps")):
            x = ca[(ca["unidade_tipo"] == "uf") & (ca["metodo"] == met)][["ts_utc", "unidade", "ws100_ms", "ghi_wm2", "t2m_c"]]
            x = x.rename(columns={"unidade": "uf", "ws100_ms": f"ws100_ms{suf}", "ghi_wm2": f"ghi_wm2{suf}", "t2m_c": f"t2m_c{suf}"})
            g = g.merge(x, on=["ts_utc", "uf"], how="left")
    us = pd.read_parquet(P / "uf_subsistema.parquet") if (P / "uf_subsistema.parquet").exists() else uf_subsistema()
    g = g.merge(us, on="uf", how="left")
    for m in meses:
        part = g[g["mes"] == m].drop(columns=["mes"])
        if len(part):
            write_parquet(part, C.ANALYTIC / "painel_uf_h" / f"painel_uf_h_{m}.parquet")


ETAPAS = {"dim_tempo": dim_tempo, "dim_usina": dim_usina, "capacidade": capacidade_mensal, "preco": preco,
          "clima_agregado": clima_agregado, "painel_subsistema": painel_subsistema, "painel_uf": painel_uf}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*"); ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--so", nargs="*", choices=list(ETAPAS))
    a = ap.parse_args()
    meses = parse_months(a.meses, a.inicio, a.fim)
    for k in (a.so or list(ETAPAS)):
        LOG.info("== %s", k)
        try:
            ETAPAS[k](meses)
        except Exception as e:
            LOG.exception("%s falhou: %s", k, e)


if __name__ == "__main__":
    main()
