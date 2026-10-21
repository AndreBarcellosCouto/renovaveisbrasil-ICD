# projeto_energia — base de dados (Etapa 0: inventário)

Projeto acadêmico (PUC-Rio) de ciência de dados sobre geração e consumo de eletricidade no Brasil (ODS 13).
Pergunta provisória: onde novos MW eólicos e solares geram mais energia nas horas/estações em que o SIN depende de térmica fóssil flexível, descontado o risco de curtailment.

Estado atual (2026-09-11): Etapa 2 concluída — base de **2025 inteiro** gerada e validada; ver `docs/STATUS.md`, `docs/dicionario_dados.md`, `docs/relatorio_qualidade_2025.md`. Pacotes CSV para Colab em `data/export/projeto_energia_csv_2025.zip` (leve) e `..._completo.zip`.

## Como reproduzir
1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. Criar `~/.cdsapirc` com a chave do Copernicus CDS (não versionar) e aceitar a licença do ERA5 no site.
3. Baixar no navegador o PLD horário do ano (CCEE bloqueia scripts — D15) para `data/raw/ccee/pld_horario/pld_horario_<ano>.csv` e registrar com `scripts/01_registrar_manual.py`.
4. `bash scripts/run_ano.sh 2025` (download → limpeza → integração → validação → CSV). Para o pacote completo: `python scripts/05_exportar_csv.py --ano 2025 --completo`.

Layout de pastas:
```
data/raw/        originais + manifest.csv (nunca editar)
data/processed/  tabelas normalizadas (Parquet zstd)
data/analytic/   painel_subsistema_h, painel_uf_h
scripts/         pipeline numerado
docs/            fontes.md, decisoes.md, STATUS.md, dicionario_dados.md, relatorio_qualidade.md
```
