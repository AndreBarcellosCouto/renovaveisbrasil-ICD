# HANDOFF — Etapa 3 concluída (base 2025)

Atualizado em 2026-10-09 08:30 (sessão desktop). Leia este arquivo primeiro; depois `docs/STATUS.md` → `docs/decisoes.md` (D15–D32) → `docs/dicionario_dados.md` → `docs/relatorio_qualidade_2025.md`.

## Estado em uma frase
Base de **2025** validada e fechada: Σ usinas = balanço do ONS em 100,0–100,1 % para toda fonte × subsistema; intensidade de emissões estimada 0,0494 vs 0,0461 do fator médio do MCTI (r mensal 0,98); margem de operação horária do MCTI no painel; todas as pendências técnicas resolvidas (D24–D31); pacotes CSV horário e em 3 h regerados. Nenhum bloqueio.

## O que a próxima sessão deve fazer
1. `source .venv/bin/activate` e perguntar ao usuário o próximo passo. Opções já mapeadas: (a) recalibrar as eficiências de D08 contra o fator médio do MCTI (+7 %); (b) outros anos com `run_ano.sh <ano>` (PLD manual; reconferir a regra de Roraima D27; `mcti_fator_medio` já cobre 2006 → ago/2026, o MDL é por ano); (c) ~~revisão manual de coordenadas~~ feita (D32). Pasta para o Drive pronta em `data/export/drive_projeto_energia_2025/` (o upload é do usuário; refazer com `06_pacote_drive.py --ano 2025` depois de qualquer reexportação).
2. Mudou `02_*`/`03_*` → rerodar limpeza/integração do ano e reexportar: `05_exportar_csv.py --ano 2025`, `--horas 3` e `--completo --horas 3` (no zsh, via `bash -c` ou opções literais).
3. Atualizar `docs/STATUS.md` e PARAR.

## Sessão de estudo
Para um chat focado em ensinar o código, o processo e a base ao usuário: `docs/HANDOFF_estudo.md` (papel de tutor, mapa do pipeline, modelo de dados, 12 casos reais de apuramento, plano de estudo com exercícios).

## Análise no Colab
**Notebook pronto (2026-10-09): `notebooks/analise_locais_2025.ipynb`**, feito por Claude a pedido do usuário (substitui o roteiro do Gemini). Etapas de cálculo testadas localmente contra o zip; células de sklearn/matplotlib só verificadas na sintaxe (não há essas libs no .venv e o usuário não quer instalar). Calibração: escala do vento α = 1,47 (CF observado embutido, vindo de `fator_capacidade_renovavel_h` + `curtailment_h`; o `cap_*` do painel UF infla o CF solar), fator solar 1,60. Achados preliminares: top eólica = litoral/serras RN-PB-CE, sertão BA-PE, litoral RS; ranking solar NÃO é robusto (N e S sem dado de corte solar). Regressão de deslocamento horário ≈ 0 (hidro absorve).
O grupo carregou `projeto_energia_csv_2025.zip` no Colab. Roteiro para o Gemini: `docs/HANDOFF_colab_gemini.md` (CF por célula via Weibull, valor = OM do MCTI × (1 − corte), métrica tCO₂/MW/ano, clustering KMeans/Ward com conectividade espacial, sensibilidades). Se o usuário trouxer resultados, revisar contra esse roteiro.

## Fatos operacionais
- Rede do desktop liberada, exceto CCEE (anti-bot; PLD é manual — D15). O usuário coloca arquivos manuais em `data/raw/` (às vezes na raiz): `ls -lat data/raw` antes de registrar.
- CDS: chave em `~/.cdsapirc`, licença aceita. Saída vem como ZIP com dois NetCDF (D21).
- Pacotes atuais em `data/export/`: `projeto_energia_csv_2025.zip` (88 MB), `_2025_3h.zip` (60 MB), `_2025_completo_3h.zip` (172 MB). O completo horário (~400 MB) não foi regerado.
- Não instalar pacotes sem perguntar (o usuário recusou `pip install openpyxl`).
- `data/export/projeto_energia_csv_2025/` (pasta antiga do usuário, só ago/2025) pode ser removida por ele.

## Regras que não mudam
Nunca editar `data/raw/`; tudo via scripts + manifesto; lacuna = nulo com flag; base em parquet continua horária (3 h só na exportação); credenciais só fora do repositório; parar e reportar domínio bloqueado; parar ao fim de cada etapa.

## Prompt para colar na nova sessão
> Retomar a partir de docs/HANDOFF.md e docs/STATUS.md na pasta projeto_energia. A base 2025 está fechada; perguntar qual das opções do HANDOFF seguir e parar ao final.
