"""Limpeza dos fatores de emissão do MCTI (MDL, método "Despacho") → data/processed (D29).

Uso: python scripts/02_limpeza_mcti.py [--arquivo data/raw/mcti/Despacho_2025_jandez_corrigidacomMO.xlsx]

A planilha (aba MDL) traz, para um ano: margem de construção (anual), margem de operação mensal,
diária (dia × mês) e horária (dia × hora × mês). Hora 1–24 = hora que termina (hora 1 = 00h–01h,
horário de Brasília) → ts_local = início da hora. Só as colunas C..N (jan–dez, valores corrigidos);
as colunas à direita são valores antigos publicados com erro e ficam fora.
Lido com a biblioteca padrão (o xlsx é um zip de XML) para não depender de openpyxl.
Saídas: mcti_margem_operacao_h/<tabela>_<AAAA-MM>.parquet e mcti_fatores_mdl.parquet (anual/mensal/diário).
Também lê Inventario_*.xlsx (fator médio do SIN, série 2006→) → mcti_fator_medio.parquet.
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

import config as C
from common import LOG, local_to_utc, write_parquet

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MESES = "CDEFGHIJKLMN"  # colunas jan..dez


def ler_planilha(path: Path) -> dict[int, dict[str, str]]:
    """{linha: {coluna: valor-texto}} da primeira aba."""
    with zipfile.ZipFile(path) as z:
        ss = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        rows = ET.fromstring(z.read("xl/worksheets/sheet1.xml")).find(M + "sheetData")
    out: dict[int, dict[str, str]] = {}
    for r in rows:
        d = {}
        for c in r:
            v = c.find(M + "v")
            if v is None or v.text is None:
                continue
            x = ss[int(v.text)] if c.get("t") == "s" else v.text
            d[re.sub(r"\d", "", c.get("r"))] = x.strip()
        if d:
            out[int(r.get("r"))] = d
    return out


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def inventario(f: Path) -> None:
    """Fator médio do SIN (inventários corporativos): blocos por ano — coluna A = ano; linha +1,
    coluna O = fator anual; linha +2, colunas C..N = jan..dez (ano corrente parcial)."""
    L = ler_planilha(f)
    rows = []
    for k, d in L.items():
        a = d.get("A", "")
        if not (a.isdigit() and len(a) == 4):
            continue
        ano = int(a)
        anual = num(L.get(k + 1, {}).get("O"))
        if anual is not None:
            rows.append(dict(ano=ano, mes=None, fator_medio_tco2_mwh=anual, periodo="anual"))
        for i, col in enumerate(MESES):
            v = num(L.get(k + 2, {}).get(col))
            if v is not None:
                rows.append(dict(ano=ano, mes=i + 1, fator_medio_tco2_mwh=v, periodo="mensal"))
    df = pd.DataFrame(rows)
    df["arquivo_origem"] = f.name
    write_parquet(df, C.PROCESSED / "mcti_fator_medio.parquet")
    LOG.info("%s: %d anos (%d-%d), %d meses", f.name, df["ano"].nunique(), df["ano"].min(), df["ano"].max(), (df["periodo"] == "mensal").sum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arquivo", default=None)
    a = ap.parse_args()
    inv = sorted((C.RAW / "mcti").glob("Inventario_*.xlsx"))
    if inv and not a.arquivo:
        inventario(inv[-1])  # série histórica completa: basta o mais recente
    fs = [Path(a.arquivo)] if a.arquivo else sorted((C.RAW / "mcti").glob("Despacho_*.xlsx"))
    for f in fs:
        L = ler_planilha(f)
        # localiza blocos pelos rótulos da coluna F ("... - ANUAL/MENSAL/DIÁRIO/HORÁRIO")
        rot = {k: v["F"] for k, v in L.items() if "F" in v and "Fator de Emiss" in v["F"]}
        ano = int(next(v["A"] for v in L.values() if v.get("A", "").isdigit() and len(v["A"]) == 4))
        lin = {next(t for t in ("ANUAL", "MENSAL", "DIÁRIO", "HORÁRIO") if t in s): k for k, s in rot.items()}
        fat = []
        bm = next(num(x) for k in range(lin["ANUAL"], lin["ANUAL"] + 3) for x in L.get(k, {}).values() if num(x) and num(x) < 5)
        fat.append(dict(ano=ano, mes=None, dia=None, tipo="margem_construcao", fator_tco2_mwh=bm))
        r = lin["MENSAL"] + 3  # rótulo, ano, cabeçalho de meses, valores
        for i, col in enumerate(MESES):
            fat.append(dict(ano=ano, mes=i + 1, dia=None, tipo="margem_operacao_mensal", fator_tco2_mwh=num(L[r].get(col))))
        for k in range(lin["DIÁRIO"] + 3, lin["HORÁRIO"]):
            dia = num(L.get(k, {}).get("B"))
            if dia is None:
                continue
            for i, col in enumerate(MESES):
                v = num(L[k].get(col))
                if v is not None and dia <= pd.Period(f"{ano}-{i + 1:02d}", "M").days_in_month:
                    fat.append(dict(ano=ano, mes=i + 1, dia=int(dia), tipo="margem_operacao_diaria", fator_tco2_mwh=v))
        fat = pd.DataFrame(fat)
        # horário: coluna A = dia (só na primeira hora do dia), B = hora 1..24
        rows, dia, invalidos = [], None, []
        for k in sorted(x for x in L if x > lin["HORÁRIO"] + 2):
            d = L[k]
            if num(d.get("A")) is not None:
                dia = int(num(d["A"]))
            h = num(d.get("B"))
            if dia is None or h is None:
                continue
            for i, col in enumerate(MESES):
                v = num(d.get(col))
                if v is None:
                    continue
                if dia > pd.Period(f"{ano}-{i + 1:02d}", "M").days_in_month:  # 30/02 etc.: célula de fórmula
                    invalidos.append(v)
                    continue
                rows.append(dict(ts_local=pd.Timestamp(ano, i + 1, dia) + pd.Timedelta(hours=int(h) - 1), fator_om_tco2_mwh=v))
        if invalidos:
            LOG.info("%s: %d celulas em dias inexistentes descartadas (%d nao nulas)", f.name, len(invalidos), sum(1 for v in invalidos if v))
        h = pd.DataFrame(rows).sort_values("ts_local")
        h["ts_utc"] = local_to_utc(h["ts_local"], ambiguous="NaT", nonexistent="NaT")
        h["convencao_hora_origem"] = "1-24"
        h["arquivo_origem"] = f.name
        dup = h.duplicated("ts_local").sum()
        if dup:
            LOG.warning("%s: %d horas duplicadas", f.name, dup)
        for m, part in h.groupby(h["ts_local"].dt.strftime("%Y-%m")):
            write_parquet(part, C.PROCESSED / "mcti_margem_operacao_h" / f"mcti_margem_operacao_h_{m}.parquet")
        # conferência: média das horas de cada mês × fator mensal publicado
        chk = h.groupby(h["ts_local"].dt.month)["fator_om_tco2_mwh"].mean()
        mens = fat[fat["tipo"] == "margem_operacao_mensal"].set_index("mes")["fator_tco2_mwh"]
        LOG.info("%s: %d horas; BM=%.4f; |media horaria - mensal| max = %.4f", f.name, len(h), bm, (chk - mens).abs().max())
        p = C.PROCESSED / "mcti_fatores_mdl.parquet"
        old = pd.read_parquet(p) if p.exists() else pd.DataFrame()
        fat = pd.concat([old[old["ano"] != ano] if len(old) else old, fat], ignore_index=True)
        write_parquet(fat, p)


if __name__ == "__main__":
    main()
