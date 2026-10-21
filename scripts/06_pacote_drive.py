"""Monta a pasta para o Drive do grupo (CSV + parquet + documentação) de um ano.

Uso: python scripts/06_pacote_drive.py --ano 2025
Requer os zips de 05_exportar_csv.py (--ano, --horas 3, --completo --horas 3) já gerados.
Saída: data/export/drive_projeto_energia_<ano>/{csv,parquet,docs}/ + LEIAME.md
Os zips de CSV entram por hard link (não duplicam espaço). Parquets: só as partições do ano;
tabelas inteiras com coluna de ano/mês são filtradas para o ano. Não altera data/raw nem data/processed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import zipfile
from datetime import datetime

import pandas as pd

import config as C
from common import LOG

# tabelas inteiras filtradas pelo ano (coluna → prefixo do ano)
FILTRAR = {"dim_tempo": "ano", "capacidade_mensal": "mes", "mmgd_mensal": "mes", "mcti_fatores_mdl": "ano"}
DOCS = ["dicionario_dados.md", "decisoes.md", "fontes.md", "revisao_manual_coordenadas.csv",
        "revisao_match_usinas.csv", "revisao_uf_coordenada.csv"]


def sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, required=True)
    a = ap.parse_args()
    ano = str(a.ano)
    exp = C.ROOT / "data" / "export"
    out = exp / f"drive_projeto_energia_{ano}"
    if out.exists():
        shutil.rmtree(out)
    for d in ("csv", "parquet", "docs"):
        (out / d).mkdir(parents=True)

    # 1) CSV (hard link dos zips já gerados)
    csvs = [f"projeto_energia_csv_{ano}.zip", f"projeto_energia_csv_{ano}_3h.zip", f"projeto_energia_csv_{ano}_completo_3h.zip"]
    for z in csvs:
        src = exp / z
        if not src.exists():
            raise SystemExit(f"falta {src.name}: rode 05_exportar_csv.py antes")
        os.link(src, out / "csv" / z)

    # 2) parquet: partições do ano (estrutura <tabela>/<tabela>_<AAAA-MM>.parquet) + tabelas inteiras
    def zip_parquet(nome: str, incluir) -> None:
        z = out / "parquet" / nome
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:  # parquet já é comprimido (zstd)
            for base, pasta in ((C.PROCESSED, "processed"), (C.ANALYTIC, "analytic")):
                for d in sorted(p for p in base.iterdir() if p.is_dir()):
                    if not incluir(d.name):
                        continue
                    for f in sorted(d.glob(f"{d.name}_{ano}-*.parquet")):
                        zf.write(f, f"{pasta}/{d.name}/{f.name}")
                if pasta == "processed" and incluir("_inteiras"):
                    for f in sorted(base.glob("*.parquet")):
                        if f.stem in FILTRAR:
                            df = pd.read_parquet(f)
                            df = df[df[FILTRAR[f.stem]].astype(str).str.startswith(ano)]
                            buf = io.BytesIO(); df.to_parquet(buf, index=False, compression="zstd")
                            zf.writestr(f"{pasta}/{f.name}", buf.getvalue())
                        else:
                            zf.write(f, f"{pasta}/{f.name}")
        LOG.info("%s: %.1f MB", z.name, z.stat().st_size / 1e6)

    zip_parquet(f"projeto_energia_parquet_{ano}.zip", lambda n: n != "clima_h")
    zip_parquet(f"projeto_energia_parquet_{ano}_clima_h.zip", lambda n: n == "clima_h")

    # 3) documentação
    for d in DOCS + [f"relatorio_qualidade_{ano}.md"]:
        p = C.DOCS / d
        if p.exists():
            shutil.copy2(p, out / "docs" / d)
    for p in C.DOCS.glob(f"usinas_horas_faltantes_{ano}-*.csv"):
        shutil.copy2(p, out / "docs" / p.name)

    # 4) LEIAME com tamanhos e sha256
    linhas = []
    for f in sorted(out.rglob("*")):
        if f.is_file():
            linhas.append(f"| `{f.relative_to(out)}` | {f.stat().st_size / 1e6:.1f} MB | `{sha256(f)[:16]}…` |")
    leiame = (C.DOCS / "LEIAME_drive.md").read_text().replace("{ANO}", ano)
    leiame = leiame.replace("{GERADO}", datetime.now().strftime("%Y-%m-%d %H:%M")).replace("{ARQUIVOS}", "\n".join(linhas))
    (out / "LEIAME.md").write_text(leiame)
    tot = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    LOG.info("pasta pronta: %s (%.0f MB)", out.relative_to(C.ROOT), tot / 1e6)


if __name__ == "__main__":
    main()
