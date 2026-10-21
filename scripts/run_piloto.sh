#!/usr/bin/env bash
# Etapa 1 — piloto: agosto/2021 e agosto/2025. Idempotente.
# OBSOLETO desde a Etapa 2: use scripts/run_ano.sh <ano>. Mantido só como registro do piloto.
set -euo pipefail
if [ "${1:-}" != "--forcar" ]; then
  echo "run_piloto.sh esta obsoleto; use: bash scripts/run_ano.sh 2025 (ou --forcar para rodar o piloto)" >&2
  exit 1
fi
cd "$(dirname "$0")/.."
M="2021-08 2025-08"
python scripts/01_download_ons.py --meses $M
python scripts/01_download_ccee_aneel_ibge.py --anos 2021 2025
python scripts/01_download_era5.py --meses $M
python scripts/02_limpeza_ons.py --meses $M
python scripts/02_limpeza_ccee_aneel.py --meses $M
python scripts/02_limpeza_era5.py --meses $M --perfil
python scripts/03_integracao.py --meses $M
python scripts/04_validacao.py --meses $M --titulo "Relatório de qualidade — piloto (ago/2021, ago/2025)" --saida docs/relatorio_qualidade_piloto.md
