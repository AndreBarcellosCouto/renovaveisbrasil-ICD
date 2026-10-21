# Base de dados — "Onde novos MW eólicos/solares evitam mais térmica fóssil" ({ANO})

Pacote gerado em {GERADO} pelo pipeline do projeto (`scripts/06_pacote_drive.py`). Cobertura: {ANO}-01 a {ANO}-12, horário, Sistema Interligado Nacional (4 subsistemas e 27 UFs + Itaipu 50 Hz como `PY`).

## Qual arquivo baixar

| Se você quer… | Baixe |
|---|---|
| Trabalhar no Colab com a resolução horária (recomendado) | `csv/projeto_energia_csv_{ANO}.zip` |
| Um pacote menor (blocos de 3 h) | `csv/projeto_energia_csv_{ANO}_3h.zip` |
| Dados por usina (geração, fator de capacidade, térmica por motivo, curtailment), em 3 h | `csv/projeto_energia_csv_{ANO}_completo_3h.zip` |
| Tudo em parquet, horário, inclusive por usina (mais leve e rápido no pandas) | `parquet/projeto_energia_parquet_{ANO}.zip` |
| Clima ERA5 por célula de 0,5° (25 M linhas; só se for preciso) | `parquet/projeto_energia_parquet_{ANO}_clima_h.zip` |

Comece por `painel_subsistema_h` (4 subsistemas × hora) ou `painel_uf_h` (UF × hora): já trazem geração por fonte, carga, curtailment, intercâmbio, preços (PLD/CMO), clima e emissões estimadas.

## Abrir no Colab

```python
from google.colab import drive
drive.mount('/content/drive')
PASTA = '/content/drive/MyDrive/<pasta do grupo>/drive_projeto_energia_{ANO}'

# CSV (zip lido direto, sem descompactar)
import pandas as pd, zipfile
z = zipfile.ZipFile(f'{PASTA}/csv/projeto_energia_csv_{ANO}.zip')
print(z.namelist())
painel = pd.read_csv(z.open('painel_subsistema_h.csv'), parse_dates=['ts_utc', 'ts_local'])

# Parquet (descompacta uma vez; cada tabela é uma pasta com um arquivo por mês)
!unzip -q -o "{PASTA}/parquet/projeto_energia_parquet_{ANO}.zip" -d /content/base
ger = pd.read_parquet('/content/base/processed/geracao_usina_h')       # todos os meses
dim = pd.read_parquet('/content/base/processed/dim_usina.parquet')
```

## Convenções (detalhes em `docs/dicionario_dados.md`)
- `ts_utc` = início da hora em UTC; `ts_local` = mesmo instante em horário de Brasília.
- Colunas `*_mwh` em séries horárias = MWh na hora (= MW médio). Nos arquivos `*_3h`: **média** das horas do bloco (energia do bloco = 3 × valor); `n_horas` e `flag_bloco_incompleto` indicam blocos com horas faltando.
- `flag_*` = 0/1. Nada é imputado: lacuna = nulo + flag.
- Subsistemas `N`, `NE`, `S`, `SE`. Intercâmbio: positivo = importação.
- Emissões (`emissoes_estimadas_tco2`) são estimativa própria (IPCC × eficiência assumida). Validação: intensidade {ANO} 0,0494 tCO₂/MWh vs 0,0461 do fator médio oficial do MCTI (correlação mensal 0,98). `fator_om_mcti_tco2_mwh` = margem de operação oficial (fator marginal) hora a hora.

## Qualidade (resumo de `docs/relatorio_qualidade_{ANO}.md`)
- Cobertura de 100 % das horas em todas as séries (CMO 96,8 % em maio — lacuna na fonte).
- Soma da geração por usina = balanço do ONS em 100,0–100,1 % para toda fonte × subsistema.
- Sistemas isolados de Roraima ficam fora do painel por subsistema (`ger_fora_sin_mwh`) e dentro do painel por UF.
- Decisões metodológicas numeradas (D01–D32) em `docs/decisoes.md`; fontes e licenças em `docs/fontes.md`.

## Arquivos

| Arquivo | Tamanho | SHA-256 (início) |
|---|---|---|
{ARQUIVOS}
