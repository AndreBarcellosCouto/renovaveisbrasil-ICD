"""Exporta as tabelas processadas/analíticas de um ano para CSV (uso em Colab/aulas).

Uso: python scripts/05_exportar_csv.py --ano 2025 [--completo] [--horas 3]
Saída: data/export/csv_<ano>/*.csv + data/export/projeto_energia_csv_<ano>[_completo][_3h].zip
--horas N agrega as tabelas horárias em blocos de N horas (D25): valores = média das horas do
bloco (unidades horárias preservadas: *_mwh = MWmed), flags = máximo, contagens = soma,
n_horas = horas presentes no bloco. A base em parquet continua horária.
Tabelas mensais são filtradas pelos meses do ano existentes; tabelas sem tempo (dimensões,
cadastros) vão inteiras. Não altera nada em data/raw.
"""
from __future__ import annotations

import argparse
import shutil
import zipfile

import pandas as pd

import config as C
from common import LOG

# Pacote padrão ("leve"): painéis, séries agregadas por subsistema/UF, dimensões e cadastros.
# --completo acrescenta as tabelas horárias por usina (num ano: ~2,7 GB em CSV, ~400 MB zip).
# clima_h por célula (25 M linhas/ano) só em parquet.
MENSAIS = ["balanco_subsistema_h", "curva_carga_h", "intercambio_h", "cmo_h", "hidro_d", "cvu_semanal",
           "carga_h", "pld_h", "preco_h", "clima_agregado_h", "mcti_margem_operacao_h"]
MENSAIS_COMPLETO = ["geracao_usina_h", "fator_capacidade_renovavel_h", "termica_motivo_h", "curtailment_h"]
ANALITICAS = ["painel_subsistema_h", "painel_uf_h"]
INTEIRAS = ["dim_usina", "dim_celula", "clima_perfil_mes_hora", "siga_usinas", "uf_subsistema", "mcti_fatores_mdl", "mcti_fator_medio"]


# texto que varia dentro do bloco: não entra na chave (união dos valores distintos)
TEXTO_NAO_CHAVE = {"curtailment_h": ["motivo"]}
TEXTO_PRIMEIRO = ["regime_metodologico", "convencao_hora_origem", "data_local"]


def agregar_horas(df: pd.DataFrame, nome: str, n: int) -> pd.DataFrame:
    """Blocos de n horas alinhados à meia-noite local (Brasília = UTC−3 sem horário de verão
    desde 2019, então o piso em UTC coincide com o local)."""
    if n <= 1 or "ts_utc" not in df:
        return df
    df = df.copy()
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True).dt.floor(f"{n}h")
    texto_var = TEXTO_NAO_CHAVE.get(nome, [])
    agg, chaves = {}, ["ts_utc"]
    for c in df.columns:
        if c in ("ts_utc", "ts_local"):
            continue
        if c.startswith("flag_"):
            agg[c] = "max"
        elif c in texto_var:
            agg[c] = lambda s: "|".join(sorted(set("|".join(s.dropna()).split("|")) - {""})) or None
        elif c in TEXTO_PRIMEIRO:
            agg[c] = "first"
        elif c.startswith(("n_semihoras", "num_")):
            agg[c] = "sum"
        elif c.startswith("n_"):
            agg[c] = "max"
        elif pd.api.types.is_float_dtype(df[c]):
            agg[c] = "mean"
        else:
            chaves.append(c)
    df["n_horas"] = 1
    agg["n_horas"] = "sum"
    g = df.groupby(chaves, dropna=False, sort=False).agg(agg).reset_index()
    g["ts_local"] = g["ts_utc"].dt.tz_convert(C.TZ_LOCAL).dt.tz_localize(None)
    g["flag_bloco_incompleto"] = (g["n_horas"] < n).astype("int8")
    return g


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--completo", action="store_true", help="inclui tabelas horarias por usina/celula")
    ap.add_argument("--horas", type=int, default=1, help="agrega series horarias em blocos de N horas (ex.: 3)")
    ap.add_argument("--manter-csv", action="store_true", help="nao apaga a pasta de CSVs apos gerar o zip")
    a = ap.parse_args()
    ano = str(a.ano)
    mensais = MENSAIS + (MENSAIS_COMPLETO if a.completo else [])
    sufixo = ("_completo" if a.completo else "") + (f"_{a.horas}h" if a.horas > 1 else "")
    out = C.ROOT / "data" / "export" / f"csv_{ano}{sufixo}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    def dump(df: pd.DataFrame, nome: str) -> None:
        if df.empty:
            return
        if a.horas > 1 and nome.endswith("_h"):
            df = agregar_horas(df, nome, a.horas)
            nome = f"{nome[:-2]}_{a.horas}h"
        p = out / f"{nome}.csv"
        df.to_csv(p, index=False)
        LOG.info("%s: %d linhas, %.1f MB", p.name, len(df), p.stat().st_size / 1e6)

    for t in mensais + ANALITICAS:
        base = C.ANALYTIC if t in ANALITICAS else C.PROCESSED
        fs = sorted((base / t).glob(f"{t}_{ano}-*.parquet"))
        if fs:
            dump(pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True), t)
    for t in INTEIRAS:
        p = C.PROCESSED / f"{t}.parquet"
        if p.exists():
            dump(pd.read_parquet(p), t)
    for t, col in (("dim_tempo", "ano"), ("capacidade_mensal", "mes"), ("mmgd_mensal", "mes")):
        p = C.PROCESSED / f"{t}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            dump(df[df[col].astype(str).str.startswith(ano)], t)

    z = out.parent / f"projeto_energia_csv_{ano}{sufixo}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(out.glob("*.csv")):
            zf.write(f, f.name)
    LOG.info("zip: %s (%.1f MB)", z.relative_to(C.ROOT), z.stat().st_size / 1e6)
    if not a.manter_csv:
        shutil.rmtree(out)


if __name__ == "__main__":
    main()
