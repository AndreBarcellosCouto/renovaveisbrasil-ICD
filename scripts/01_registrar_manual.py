"""Registra no manifesto arquivos obtidos manualmente (ex.: MCTI, atrás de CAPTCHA).

Uso: python scripts/01_registrar_manual.py data/raw/mcti/fatores_medios_sin.xlsx \
        --fonte mcti --url "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/sirene/dados-e-ferramentas/fatores-de-emissao" \
        --obs "baixado manualmente em 2026-09-12"
"""
import argparse
from pathlib import Path

from common import LOG, manifest_add


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo")
    ap.add_argument("--fonte", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--obs", default="download manual")
    a = ap.parse_args()
    p = Path(a.arquivo).resolve()
    manifest_add(a.fonte, p, a.url, "", obs=a.obs)
    LOG.info("registrado %s", p)


if __name__ == "__main__":
    main()
