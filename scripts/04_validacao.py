"""Validações 1–8 → docs/relatorio_qualidade.md (não altera dados).

Uso: python scripts/04_validacao.py --meses 2021-08 2025-08 --titulo "Piloto"
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config as C
from common import LOG, parse_months

P, A = C.PROCESSED, C.ANALYTIC
TAB_H = ["geracao_usina_h", "fator_capacidade_renovavel_h", "termica_motivo_h", "curtailment_h", "carga_h",
         "intercambio_h", "cmo_h", "pld_h", "preco_h", "balanco_subsistema_h", "curva_carga_h", "clima_h", "clima_agregado_h"]


def parts(tabela: str, meses, base=P) -> pd.DataFrame:
    fs = [base / tabela / f"{tabela}_{m}.parquet" for m in meses]
    fs = [f for f in fs if f.exists()]
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def md_table(df: pd.DataFrame, floatfmt: str = "{:.1f}") -> str:
    if df is None or len(df) == 0:
        return "_(sem dados)_\n"
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines) + "\n"


# 1 ---------------------------------------------------------------- cobertura
def v1_cobertura(meses) -> str:
    rows = []
    for t in TAB_H:
        for m in meses:
            f = P / t / f"{t}_{m}.parquet"
            horas = pd.Period(m, "M").end_time.day * 24
            if not f.exists():
                rows.append(dict(serie=t, mes=m, pct_horas=0.0, linhas=0, obs="arquivo ausente")); continue
            d = pd.read_parquet(f, columns=["ts_utc"])
            rows.append(dict(serie=t, mes=m, pct_horas=100 * d["ts_utc"].nunique() / horas, linhas=len(d), obs=""))
    df = pd.DataFrame(rows)
    piv = df.pivot(index="serie", columns="mes", values="pct_horas").reset_index()
    return "% de horas do mês com ao menos um registro (por série):\n\n" + md_table(piv) + "\nLinhas por série × mês:\n\n" + md_table(df.pivot(index="serie", columns="mes", values="linhas").reset_index(), "{:.0f}")


# 2 ---------------------------------------------------------------- fechamento
def v2_fechamento(meses) -> str:
    g = parts("painel_subsistema_h", meses, A)
    if g.empty:
        return "_painel ausente_\n"
    ger = g[[c for c in g if c.startswith("ger_") and c.endswith("_mwh") and "sem_fator" not in c and "fora_sin" not in c]].sum(axis=1)
    g["residuo_mwh"] = (ger + g.get("intercambio_liquido_mwh", 0).fillna(0)
                        + g.get("intercambio_internacional_mwh", pd.Series(0.0, index=g.index)).fillna(0) - g["carga_global_mwh"])
    g["residuo_pct"] = 100 * g["residuo_mwh"] / g["carga_global_mwh"]
    q = g.groupby("subsistema")["residuo_pct"].describe(percentiles=[.05, .25, .5, .75, .95])[["count", "mean", "5%", "25%", "50%", "75%", "95%"]].reset_index()
    txt = ("Resíduo = Σ geração por usina (ONS, sem sistemas isolados) + intercâmbio líquido nacional e internacional − carga global (API), em % da carga.\n"
           "Esperado: resíduo negativo sistemático ≈ −(MMGD + pequenas usinas não medidas + perdas), maior após 2023-04 quando a carga passou a incluir MMGD.\n\n" + md_table(q))
    if "bal_carga_mwh" in g:
        g["res_bal_pct"] = 100 * (g["bal_ger_hidraulica_mwh"] + g["bal_ger_termica_mwh"] + g["bal_ger_eolica_mwh"] + g["bal_ger_solar_mwh"] + g["bal_intercambio_liquido_mwh"] - g["bal_carga_mwh"]) / g["bal_carga_mwh"]
        q2 = g.groupby("subsistema")["res_bal_pct"].describe(percentiles=[.05, .5, .95])[["mean", "5%", "50%", "95%"]].reset_index()
        txt += ("\nMesmo cálculo usando somente o Balanço do ONS (referência interna do operador; "
                "esperado ≈ 0 — o balanço fecha por construção, com `val_intercambio` convertido para positivo = importação):\n\n" + md_table(q2, "{:.2f}"))
    return txt


# 3 ---------------------------------------------------------------- usina vs balanço
def v3_usina_vs_balanco(meses) -> str:
    g = parts("painel_subsistema_h", meses, A)
    if g.empty or "bal_carga_mwh" not in g:
        return "_balanço ausente_\n"
    pares = [("ger_hidro_mwh", "bal_ger_hidraulica_mwh"), ("ger_eolica_mwh", "bal_ger_eolica_mwh"), ("ger_solar_mwh", "bal_ger_solar_mwh")]
    g["ger_termica_total_mwh"] = g[[c for c in ["ger_fossil_mwh", "ger_biomassa_mwh", "ger_nuclear_mwh"] if c in g]].sum(axis=1)
    pares.append(("ger_termica_total_mwh", "bal_ger_termica_mwh"))
    rows = []
    for a, b in pares:
        if a in g and b in g:
            s = g.groupby("subsistema")[[a, b]].sum()
            for sub, r in s.iterrows():
                rows.append(dict(fonte=a.replace("ger_", "").replace("_mwh", ""), subsistema=sub, soma_usinas_gwh=r[a] / 1e3, balanco_gwh=r[b] / 1e3, razao_pct=100 * r[a] / r[b] if r[b] else np.nan))
    return "Σ geração por usina ÷ balanço do ONS (por fonte × subsistema, meses do escopo). Nota: nuclear entra em 'térmica' no balanço.\n\n" + md_table(pd.DataFrame(rows))


# 4 ---------------------------------------------------------------- sanidade
def v4_sanidade(meses) -> str:
    out = []
    ger = parts("geracao_usina_h", meses)
    if not ger.empty:
        dim = pd.read_parquet(P / "dim_usina.parquet")[["id_ons", "grupo"]]
        ger = ger.merge(dim, on="id_ons", how="left")
        sol = ger[ger["grupo"] == "solar"]
        h = sol["ts_local"].dt.hour
        noite = sol[(h >= 21) | (h <= 4)]
        out.append(f"- Solar noturno (21h–04h local): {len(noite)} registros; geração média {noite['geracao_mwh'].mean():.3f} MWh; "
                   f"máx {noite['geracao_mwh'].max():.2f} MWh; {100 * (noite['geracao_mwh'] > 0.5).mean():.2f}% > 0,5 MWh.")
        if "flag_solar_noturno" in ger:
            fl = ger[ger["flag_solar_noturno"] == 1].groupby("id_ons")["geracao_mwh"].agg(["size", "mean", "max"])
            top = ", ".join(f"`{i}` ({int(r['size'])} h, média {r['mean']:.1f}, máx {r['max']:.1f} MWh)"
                            for i, r in fl.sort_values("size", ascending=False).head(5).iterrows())
            out.append(f"- `flag_solar_noturno=1`: {int(ger['flag_solar_noturno'].sum())} registros em {len(fl)} usinas "
                       f"({fl['size'].mul(fl['mean']).sum() / 1e3:.2f} GWh). Principais: {top}.")
        if "flag_subsistema_reatribuido" in ger:
            ra = ger[ger["flag_subsistema_reatribuido"] == 1]
            if len(ra):
                desc = ra.groupby(["id_ons", "id_subsistema_origem", "id_subsistema"])["geracao_mwh"].sum()
                out.append("- Subsistema reatribuído pelo cadastro de conjuntos (D24): " + "; ".join(
                    f"`{i}` {o}→{d} ({v / 1e3:.1f} GWh)" for (i, o, d), v in desc.items()) + ".")
        out.append(f"- Valores negativos em geracao_usina_h: {int((ger['geracao_mwh'] < 0).sum())} ({100 * (ger['geracao_mwh'] < 0).mean():.3f}%).")
        out.append(f"- Duplicatas (id_ons × hora): {int(ger['flag_duplicata'].sum())}.")
        out.append(f"- Horas ambíguas/inexistentes (horário de verão): {int(ger['flag_ts_ambiguo'].sum())}.")
        # horas faltantes por usina
        for m in meses:
            sub = ger[ger["ts_local"].dt.strftime("%Y-%m") == m]
            horas = pd.Period(m, "M").end_time.day * 24
            n = sub.groupby("id_ons")["ts_utc"].nunique()
            out.append(f"- {m}: {len(n)} usinas; {int((n < horas).sum())} com horas faltantes; {int((n > horas).sum())} com horas a mais que o mês.")
        out.append("\n" + horas_faltantes(ger, meses))
    for t in ["carga_h", "cmo_h", "curtailment_h"]:
        d = parts(t, meses)
        if not d.empty and "flag_hora_incompleta" in d:
            out.append(f"- {t}: {int(d['flag_hora_incompleta'].sum())} horas com n_semihoras ≠ 2 de {len(d)}.")
    cl = parts("clima_h", meses)
    if not cl.empty:
        h = cl["ts_utc"].dt.tz_convert(C.TZ_LOCAL).dt.hour
        out.append(f"- ERA5 GHI noturno (22h–03h local): média {cl.loc[(h >= 22) | (h <= 3), 'ghi_wm2'].mean():.2f} W/m²; GHI negativo: {int((cl['ghi_wm2'] < 0).sum())}; ghi nulo: {int(cl['flag_ghi_nulo'].sum())}.")
    return "\n".join(out) + "\n"


def horas_faltantes(ger: pd.DataFrame, meses) -> str:
    """Classifica cada usina × mês com horas faltantes: entrada (lacuna só no início do mês),
    saída (só no fim), entrada/saída intramês (início e fim) ou lacuna interna. Lista completa
    em docs/usinas_horas_faltantes_<periodo>.csv."""
    rows = []
    for m in meses:
        p = pd.Period(m, "M")
        t0 = pd.Timestamp(p.start_time).tz_localize(C.TZ_LOCAL).tz_convert("UTC")
        t1 = pd.Timestamp(p.end_time.floor("h")).tz_localize(C.TZ_LOCAL).tz_convert("UTC")
        horas = len(pd.date_range(t0, t1, freq="h"))
        sub = ger[ger["ts_local"].dt.strftime("%Y-%m") == m]
        for uid, d in sub.groupby("id_ons"):
            ts = d["ts_utc"].dropna().drop_duplicates().sort_values()
            n = len(ts)
            if n >= horas:
                continue
            ini, fim = ts.iloc[0], ts.iloc[-1]
            gap_ini = int((ini - t0) / pd.Timedelta("1h")); gap_fim = int((t1 - fim) / pd.Timedelta("1h"))
            internas = (horas - n) - gap_ini - gap_fim
            tipo = ("lacuna_interna" if internas > 0 else "entrada_e_saida" if gap_ini and gap_fim
                    else "entrada" if gap_ini else "saida")
            rows.append(dict(mes=m, id_ons=uid, nome=d["nom_usina"].iloc[0], tipo_usina=d["nom_tipousina"].iloc[0],
                             uf=d["id_estado"].iloc[0], horas_presentes=n, horas_faltantes=horas - n,
                             faltantes_inicio=gap_ini, faltantes_fim=gap_fim, faltantes_internas=internas,
                             primeira_hora_local=d["ts_local"].min(), ultima_hora_local=d["ts_local"].max(),
                             gwh_no_mes=d["geracao_mwh"].sum() / 1e3, classificacao=tipo))
    if not rows:
        return "Nenhuma usina com horas faltantes.\n"
    df = pd.DataFrame(rows)
    nome = f"usinas_horas_faltantes_{meses[0]}_{meses[-1]}.csv"
    df.to_csv(C.DOCS / nome, index=False)
    # usina que some num mês e volta noutro continua 'entrada'/'saida' no mês da transição
    resumo = df.pivot_table(index="mes", columns="classificacao", values="id_ons", aggfunc="count", fill_value=0).reset_index()
    tipos = df.groupby(["classificacao", "tipo_usina"]).agg(usinas_mes=("id_ons", "size"), gwh=("gwh_no_mes", "sum")).reset_index()
    return (f"Usinas × mês com horas faltantes, por classificação (lista completa em `docs/{nome}`; "
            "`entrada` = lacuna só no início do mês, típico de entrada em operação; `saida` = só no fim):\n\n"
            + md_table(resumo, "{:.0f}") + "\nPor tipo de usina:\n\n" + md_table(tipos, "{:.1f}"))


# 5 ---------------------------------------------------------------- alinhamento
def v5_alinhamento(meses) -> str:
    g = parts("painel_uf_h", meses, A)
    if g.empty or "ghi_wm2" not in g:
        return "_painel_uf ou clima ausente_\n"
    rows = []
    if "curtail_eolica_mwh" in g:
        g["ger_eolica_ref_mwh"] = g["ger_eolica_mwh"].fillna(0) + g["curtail_eolica_mwh"].fillna(0)
    for uf, d in g.groupby("uf"):
        d = d.sort_values("ts_utc")
        wcol = "ws100_ms_pe" if "ws100_ms_pe" in d else "ws100_ms"
        for nome, x, y in (("solar×ghi", "ger_solar_mwh", "ghi_wm2"), ("eolica×ws100³", "ger_eolica_mwh", wcol),
                           ("eolica+corte×ws100³", "ger_eolica_ref_mwh", wcol)):
            if x not in d or d[x].fillna(0).sum() < 1:
                continue
            xs = d[x].fillna(0).values; ys = d[y].values if "ws" not in y else d[y].values ** 3
            if np.nanstd(xs) == 0 or np.nanstd(ys) == 0:
                continue
            cors = {}
            for lag in range(-3, 4):
                a = pd.Series(xs); b = pd.Series(ys).shift(lag)
                cors[lag] = a.corr(b)
                best = max(cors, key=lambda k: cors[k] if pd.notna(cors[k]) else -9)
            rows.append(dict(uf=uf, par=nome, lag_melhor=best, r_lag0=cors[0], r_melhor=cors[best], gwh=xs.sum() / 1e3))
    df = pd.DataFrame(rows).sort_values(["par", "gwh"], ascending=[True, False])
    return ("Correlação cruzada por UF entre geração agregada e variável ERA5 (lag em horas; lag>0 = clima adiantado). Esperado: pico em 0.\n"
            "`eolica+corte` = geração verificada + corte (≈ geração de referência, sem curtailment). O lag −1/−2 h da geração verificada "
            "some quando o corte é somado: o deslocamento vem do curtailment, não do carimbo de tempo.\n\n"
            + md_table(df, "{:.3f}"))


# 6 ---------------------------------------------------------------- curtailment
def v6_curtailment(meses) -> str:
    cu = parts("curtailment_h", meses)
    if cu.empty:
        return "_curtailment_h ausente nos meses do escopo (esperado antes de 2022-09 eólica / 2024-04 solar)_\n"
    rows = []
    for (m, f), d in cu.groupby([cu["ts_local"].dt.strftime("%Y-%m"), "fonte"]):
        rows.append(dict(mes=m, fonte=f, registros=len(d), usinas=d["id_ons"].nunique(),
                         pct_ref_menor_verif=100 * d["flag_ref_menor_que_verif"].mean(),
                         corte_gwh=(d["geracao_referencia_mwh"] - d["geracao_verificada_mwh"]).clip(lower=0).sum() / 1e3,
                         referencia_gwh=d["geracao_referencia_mwh"].sum() / 1e3,
                         pct_horas_com_motivo=100 * d["motivo"].notna().mean()))
    df = pd.DataFrame(rows); df["corte_pct_ref"] = 100 * df["corte_gwh"] / df["referencia_gwh"]
    return md_table(df, "{:.2f}")


# 7 ---------------------------------------------------------------- ONS↔ANEEL
def v7_match(meses) -> str:
    if not (P / "dim_usina.parquet").exists():
        return "_dim_usina ausente_\n"
    d = pd.read_parquet(P / "dim_usina.parquet")
    d = d[d["potencia_mw"] > 0]
    q = d.groupby("qualidade_match").agg(usinas=("id_ons", "size"), mw=("potencia_mw", "sum")).reset_index()
    q["pct_usinas"] = 100 * q["usinas"] / q["usinas"].sum(); q["pct_mw"] = 100 * q["mw"] / q["mw"].sum()
    top = d[d["lat"].isna()].sort_values("potencia_mw", ascending=False).head(15)[["id_ons", "nome", "grupo", "uf", "potencia_mw"]]
    txt = md_table(q) + "\nMaiores usinas sem coordenada:\n\n" + md_table(top)
    if "flag_uf_diverge" in d:
        cols = ["id_ons", "nome", "grupo", "uf", "uf_geo", "municipio", "lat", "lon", "fonte_coord", "potencia_mw"] + (["revisao_coordenada"] if "revisao_coordenada" in d else [])
        dv = d[d["flag_uf_diverge"] == 1][cols]
        if "revisao_coordenada" in d:
            nrev = int(d["revisao_coordenada"].notna().sum())
            pend = dv[dv["revisao_coordenada"].isna()]
            txt += (f"\nRevisão manual (D32, `docs/revisao_manual_coordenadas.csv`): {nrev} usinas conferidas — "
                    f"{int((d['revisao_coordenada'] == 'corrigida').sum())} coordenadas corrigidas para o centroide do município declarado pela ANEEL, "
                    f"{int((d['revisao_coordenada'] == 'divisa_conferida').sum())} divisas mantidas; {len(pend)} divergências ainda não revisadas.\n")
        dv.sort_values("potencia_mw", ascending=False).to_csv(C.DOCS / "revisao_uf_coordenada.csv", index=False)
        txt += (f"\n{len(dv)} usinas ({dv['potencia_mw'].sum():.0f} MW) com coordenada em UF diferente da cadastrada "
                "(`flag_uf_diverge=1`; lista em `docs/revisao_uf_coordenada.csv`). Hidrelétricas de divisa são esperadas; "
                "casos distantes (ex.: UF MA com ponto em SC/ES) indicam erro de coordenada na fonte — não corrigidos.\n")
    return txt


# 8 ---------------------------------------------------------------- emissões
def v8_emissoes(meses) -> str:
    g = parts("painel_subsistema_h", meses, A)
    if g.empty or "emissoes_estimadas_tco2" not in g:
        return "_painel/emissões ausentes_\n"
    rows = []
    for m, d in g.groupby(g["ts_local"].dt.strftime("%Y-%m")):
        ger = d[[c for c in d if c.startswith("ger_") and c.endswith("_mwh") and "sem_fator" not in c and "fora_sin" not in c]].sum().sum()
        rows.append(dict(mes=m, emissoes_ktco2=d["emissoes_estimadas_tco2"].sum() / 1e3, geracao_gwh=ger / 1e3,
                         intensidade_tco2_mwh=d["emissoes_estimadas_tco2"].sum() / ger if ger else np.nan,
                         fossil_sem_fator_gwh=d.get("ger_fossil_sem_fator_mwh", pd.Series(dtype=float)).sum() / 1e3))
    df = pd.DataFrame(rows)
    fm = P / "mcti_fatores_mdl.parquet"
    txt_om = ""
    if fm.exists():
        f = pd.read_parquet(fm)
        om = f[f["tipo"] == "margem_operacao_mensal"].assign(mes=lambda d: d["ano"].astype(int).astype(str) + "-" + d["mes"].astype(int).map("{:02d}".format))
        df = df.merge(om[["mes", "fator_tco2_mwh"]].rename(columns={"fator_tco2_mwh": "mcti_margem_operacao"}), on="mes", how="left")
        if "fator_om_mcti_tco2_mwh" in g:
            sin = g.groupby("ts_utc").agg(om=("fator_om_mcti_tco2_mwh", "first"), em=("emissoes_estimadas_tco2", "sum"),
                                          fos=("ger_fossil_mwh", "sum"), pld=("pld_rs_mwh", "mean"))
            ger_cols = [c for c in g if c.startswith("ger_") and c.endswith("_mwh") and "sem_fator" not in c and "fora_sin" not in c]
            sin["ger"] = g.groupby("ts_utc")[ger_cols].sum().sum(axis=1)
            sin["int"] = sin["em"] / sin["ger"]
            txt_om = (f"\nCorrelação horária (SIN) da margem de operação do MCTI com: nossa intensidade média {sin['om'].corr(sin['int']):.2f}; "
                      f"geração fóssil {sin['om'].corr(sin['fos']):.2f}; PLD médio {sin['om'].corr(sin['pld']):.2f}.\n")
    fmed = P / "mcti_fator_medio.parquet"
    txt_med = ""
    if fmed.exists():
        f = pd.read_parquet(fmed)
        mm = f[f["periodo"] == "mensal"].assign(mes=lambda d: d["ano"].astype(int).astype(str) + "-" + d["mes"].astype(int).map("{:02d}".format))
        df = df.merge(mm[["mes", "fator_medio_tco2_mwh"]].rename(columns={"fator_medio_tco2_mwh": "mcti_fator_medio"}), on="mes", how="left")
        df["dif_pct_vs_medio"] = 100 * (df["intensidade_tco2_mwh"] / df["mcti_fator_medio"] - 1)
        ok = df.dropna(subset=["mcti_fator_medio"])
        if len(ok):
            anos = sorted({m[:4] for m in ok["mes"]})
            an = f[(f["periodo"] == "anual") & f["ano"].astype(str).isin(anos)]
            nosso = ok["emissoes_ktco2"].sum() / ok["geracao_gwh"].sum()
            txt_med = (f"\n**Fator médio do SIN (MCTI, inventários corporativos)** — validação principal: correlação mensal "
                       f"{ok['intensidade_tco2_mwh'].corr(ok['mcti_fator_medio']):.2f}; diferença média {ok['dif_pct_vs_medio'].mean():+.1f} % "
                       f"(faixa {ok['dif_pct_vs_medio'].min():+.1f} a {ok['dif_pct_vs_medio'].max():+.1f} %). "
                       f"No período: nossa intensidade {nosso:.4f} × MCTI anual "
                       + ", ".join(f"{int(r['ano'])}: {r['fator_medio_tco2_mwh']:.4f}" for _, r in an.iterrows()) + " tCO₂/MWh. "
                       "Nossa estimativa usa fatores IPCC × eficiência assumida por tecnologia (D08); a superestimação nos meses de "
                       "muita térmica pode indicar eficiências assumidas baixas para parte do parque a gás (hipótese não testada).\n")
    mcti = list((C.RAW / "mcti").glob("*.xls*")) if (C.RAW / "mcti").exists() else []
    nota = (txt_med + "\n`mcti_margem_operacao` (fatores **MDL, método Despacho**) é a intensidade das usinas na margem — fator marginal, "
            "não comparável ao médio; serve de referência para emissões evitadas. Atenção: no arquivo de 2025 a margem de operação de jan–jun "
            "é ≈ 10 × o fator médio (razão 9,98–10,02), o que não ocorre em jul–dez (7,4–9,8) — possível inconsistência na fonte (D31)." + txt_om if mcti else
            "Arquivo do MCTI ausente (download manual pendente). Referência pública: fator médio mensal do SIN em 2025 (jan–abr) entre 0,021 e 0,029 tCO₂/MWh; "
            "em 2021 (crise hídrica) os valores mensais do MCTI ficaram na faixa de ~0,1 tCO₂/MWh.")
    return md_table(df, "{:.4f}") + "\n" + nota + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", nargs="*"); ap.add_argument("--inicio"); ap.add_argument("--fim")
    ap.add_argument("--titulo", default="Relatório de qualidade")
    ap.add_argument("--saida", default=str(C.DOCS / "relatorio_qualidade.md"))
    a = ap.parse_args()
    meses = parse_months(a.meses, a.inicio, a.fim)
    secs = [("1. Matriz de cobertura", v1_cobertura), ("2. Fechamento energético por subsistema", v2_fechamento),
            ("3. Soma por usina vs balanço do ONS", v3_usina_vs_balanco), ("4. Sanidade (solar noturno, negativos, duplicatas, horas)", v4_sanidade),
            ("5. Alinhamento temporal geração × clima", v5_alinhamento), ("6. Curtailment: referência ≥ verificada", v6_curtailment),
            ("7. Correspondência ONS ↔ ANEEL", v7_match), ("8. Intensidade de emissões vs MCTI", v8_emissoes)]
    out = [f"# {a.titulo}\n", f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · meses: {', '.join(meses)}\n"]
    for t, fn in secs:
        LOG.info(t)
        try:
            out.append(f"\n## {t}\n\n{fn(meses)}")
        except Exception as e:
            LOG.exception(t)
            out.append(f"\n## {t}\n\n_falhou: {e}_\n")
    open(a.saida, "w").write("\n".join(out))
    LOG.info("relatorio em %s", a.saida)


if __name__ == "__main__":
    main()
