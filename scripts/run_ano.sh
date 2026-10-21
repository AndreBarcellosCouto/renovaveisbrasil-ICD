#!/usr/bin/env bash
# Etapa 2 — processa um ano inteiro. Uso: bash scripts/run_ano.sh 2025 [MM_fim]
# Idempotente: downloads já registrados no manifesto não se repetem.
# PLD (CCEE) é download manual — coloque data/raw/ccee/pld_horario/pld_horario_<ano>.csv e registre antes.
set -euo pipefail
cd "$(dirname "$0")/.."
ANO="${1:?informe o ano, ex.: 2025}"
FIM="${2:-12}"
INI="$ANO-01"; FIMM="$ANO-$FIM"
PY=".venv/bin/python"
$PY scripts/01_download_ons.py --inicio "$INI" --fim "$FIMM"
$PY scripts/01_download_ccee_aneel_ibge.py --anos "$ANO"
$PY scripts/01_download_era5.py --inicio "$INI" --fim "$FIMM" --paralelo 3
$PY scripts/02_limpeza_ons.py --inicio "$INI" --fim "$FIMM" --lote 12
$PY scripts/02_limpeza_ccee_aneel.py --inicio "$INI" --fim "$FIMM"
[ -n "$(ls data/raw/mcti/Despacho_${ANO}_*.xlsx 2>/dev/null)" ] && $PY scripts/02_limpeza_mcti.py
$PY scripts/02_limpeza_era5.py --inicio "$INI" --fim "$FIMM" --perfil
$PY scripts/03_integracao.py --inicio "$INI" --fim "$FIMM"
$PY scripts/04_validacao.py --inicio "$INI" --fim "$FIMM" --titulo "Relatório de qualidade — $ANO" --saida "docs/relatorio_qualidade_$ANO.md"
$PY scripts/05_exportar_csv.py --ano "$ANO"
