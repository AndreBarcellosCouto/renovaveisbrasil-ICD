# HANDOFF — sessão de estudo: entender o código, o processo e a base de dados

Criado em 2026-10-15. Leia este arquivo inteiro antes de responder ao usuário.

## 1. Seu papel nesta sessão
Você é **tutor**, não executor. O objetivo é o usuário (estudante da PUC-Rio, fala pt-BR) **entender a fundo** como a base foi construída e ganhar intimidade com os dados — não apenas o processo, mas o que cada tabela mede, como elas se ligam e onde estão as armadilhas.

Regras:
- **Não altere nada** em `data/` nem em `scripts/` sem pedido explícito. Ler, explicar e rodar consultas de leitura é o trabalho.
- **Ancore cada explicação no código ou nos dados reais**: cite `arquivo:linha`, mostre a coluna, rode uma consulta pequena e mostre o número. Não explique de memória — confira no arquivo antes (o código mudou várias vezes; este handoff pode estar desatualizado em detalhes).
- Didática: comece pela intuição, depois o mecanismo, depois o código. Use os casos reais da seção 8 como exemplos. Faça uma pergunta de checagem ao fim de cada tópico. Respostas curtas por padrão; aprofunde quando ele pedir.
- O usuário não quer instalar pacotes no `.venv` (sem `pip install`); use o que existe (pandas, numpy, pyarrow, geopandas, xarray). sklearn/scipy/matplotlib só no Colab.
- Se ele quiser rodar algo no Colab, escreva a célula; ele cola a saída de volta.

### Se esta sessão for no chat do claude.ai (Projeto), não no Claude Code
Você não acessa a pasta nem roda código. Os arquivos estão no conhecimento do Projeto: este handoff, `dicionario_dados.md`, `decisoes.md`, `relatorio_qualidade_2025.md`, `fontes.md`, `STATUS.md`, os scripts `config.py`, `common.py`, `02_*.py`, `03_integracao.py`, `04_validacao.py`, `05_exportar_csv.py` e `notebook_analise_locais_2025.py` (versão em texto do notebook). Cite trechos desses arquivos (nome da função) em vez de `arquivo:linha`. Quando precisar de um número que não está nos documentos, escreva uma célula curta para o Colab (CSV já extraído em `/content/extracted_data`) e peça ao usuário para colar a saída. Pastas citadas abaixo (`data/`, `scripts/`) são do computador dele — servem de contexto.

## 2. O projeto em uma frase
Base horária de 2025 do setor elétrico brasileiro para responder: **em que locais um MW novo de eólica ou solar evita mais emissões de térmica fóssil no SIN**, descontando o risco de corte (curtailment). Projeto de grupo (ODS 13); o grupo trabalha no Google Colab com os CSVs.

## 3. Onde está cada coisa (pasta `projeto_energia/`)
```
data/raw/         originais baixados + manifest.csv (URL, data, sha256) — NUNCA editar
data/processed/   tabelas limpas e normalizadas (Parquet zstd, uma partição por mês)
data/analytic/    painel_subsistema_h, painel_uf_h (tabelas "largas" prontas para análise)
data/export/      pacotes CSV (horário, 3 h, completo) e drive_projeto_energia_2025/ (o que foi para o Drive)
scripts/          pipeline numerado 01→06 + config.py + common.py
notebooks/        analise_locais_2025.ipynb (análise de locais, roda no Colab)
docs/             STATUS, HANDOFF, decisoes (D01–D32), dicionario_dados, fontes, relatorio_qualidade_2025, revisões
```
Leitura recomendada para você antes de ensinar: `docs/dicionario_dados.md` → `docs/decisoes.md` → `docs/relatorio_qualidade_2025.md` → `scripts/config.py` → os scripts na ordem.

## 4. O pipeline, camada por camada
| Passo | Script | O que faz | Conceito que ensina |
|---|---|---|---|
| Configuração | `config.py`, `common.py` | caminhos, fontes, URLs, fuso; manifesto, `write_parquet`, conversão local→UTC | reprodutibilidade; uma fonte de verdade |
| 1. Coleta | `01_download_ons.py`, `01_download_ccee_aneel_ibge.py`, `01_download_era5.py`, `01_registrar_manual.py` | baixa do S3 do ONS, ANEEL, IBGE, ERA5 (API do Copernicus); registra no manifesto o que veio à mão (PLD da CCEE, MCTI) | proveniência; idempotência; portais que bloqueiam robôs |
| 2. Limpeza | `02_limpeza_ons.py`, `02_limpeza_ccee_aneel.py`, `02_limpeza_era5.py`, `02_limpeza_mcti.py` | padroniza nomes, tipos, unidades e carimbos de tempo; semi-hora→hora; flags; nada imputado | *tidy data*; lacuna = nulo + flag |
| 3. Integração | `03_integracao.py` | dimensões (`dim_tempo`, `dim_usina`, `dim_celula`), capacidade mensal, preço, clima agregado, painéis | modelo estrela; chaves; agregação espacial |
| 4. Validação | `04_validacao.py` | 8 testes → `docs/relatorio_qualidade_2025.md` | como provar que a base está certa |
| 5. Exportação | `05_exportar_csv.py`, `06_pacote_drive.py` | CSV horário/3 h/completo; pasta do Drive com LEIAME e sha256 | entregar dados para outros |
| Orquestração | `run_ano.sh` | roda tudo para um ano | |
| Análise | `notebooks/analise_locais_2025.ipynb` | CF por célula, valor do MWh, tCO₂/MW, clustering, sensibilidades | da base à resposta |

## 5. Fontes e o que medem
- **ONS (dados abertos, S3):** geração horária por usina (`geracao_usina`), fator de capacidade eólico/solar por usina (`fator_capacidade`), térmica por motivo de despacho (ordem de mérito, inflexibilidade…), constrained-off eólico/solar (corte), balanço por subsistema, intercâmbio entre subsistemas, CMO, EAR/ENA (reservatórios), CVU; cadastros de usinas/unidades/conjuntos. **API de Carga Verificada:** carga semi-horária com MMGD separada.
- **CCEE:** PLD horário (download manual — o portal bloqueia scripts, D15).
- **ANEEL:** SIGA (empreendimentos: CEG, coordenadas, município) e MMGD (geração distribuída).
- **IBGE:** malhas de UF e municípios (para ponto-em-polígono).
- **ERA5 (Copernicus):** reanálise climática horária a 0,5°: vento a 100 m, irradiância (GHI), temperatura.
- **MCTI:** fator médio de emissão do SIN (inventários; série 2006→ago/2026) e fatores MDL (margem de operação horária = fator marginal; margem de construção).

## 6. Conceitos do setor elétrico que ele precisa dominar
SIN e os 4 subsistemas (N, NE, S, SE/CO) · MWh na hora = MW médio (MWmed) · carga × geração × intercâmbio (positivo = importação) · **curtailment/constrained-off**: geração de referência (o que o vento/sol permitiria) − verificada · PLD (preço de mercado) × CMO (custo marginal do operador) · térmica por **ordem de mérito** (deslocável) × **inflexível** (não sai) · MMGD (micro/minigeração distribuída, "atrás do medidor") · **fator de capacidade** (energia gerada ÷ capacidade × horas) · fator de emissão **médio** (intensidade do parque todo) × **marginal** (de quem sai quando entra um MWh renovável — é o que importa para "emissão evitada") · usinas Tipo I/II/III e **conjuntos** (o ONS reporta vários parques como um id) · **CEG** (código da usina na ANEEL).

## 7. Modelo de dados (grão, chaves, ligações)
- **Fatos horários (processed):** `geracao_usina_h` (usina × hora), `fator_capacidade_renovavel_h`, `curtailment_h`, `termica_motivo_h` (formato longo: usina × hora × motivo), `carga_h` (área × hora), `balanco_subsistema_h`, `intercambio_h` (origem × destino × hora), `cmo_h`, `pld_h`, `preco_h`, `clima_h` (célula × hora, 25 M linhas/ano, só parquet), `clima_agregado_h` (UF/subsistema × hora × método), `mcti_margem_operacao_h`.
- **Diárias/mensais/inteiras:** `hidro_d`, `cvu_semanal`, `capacidade_mensal`, `mmgd_mensal`, `mcti_fator_medio`, `mcti_fatores_mdl`, `clima_perfil_mes_hora` (célula × mês × hora, média e desvio).
- **Dimensões:** `dim_tempo` (hora, feriado, fim de semana), `dim_usina` (id_ons → grupo, combustível, UF, subsistema, coordenadas, revisão), `dim_celula` (célula ERA5 → UF, município, subsistema), `uf_subsistema`, `siga_usinas`.
- **Chave temporal:** `ts_utc` (início da hora, UTC) liga tudo; `ts_local` é o mesmo instante em Brasília (UTC−3, sem horário de verão em 2025).
- **Painéis (analytic):** `painel_subsistema_h` (4 × 8 760 = 35 040 linhas, 58 colunas) e `painel_uf_h` (UF × hora) juntam geração por grupo, carga, corte, intercâmbio, preços, reservatórios, clima, balanço do ONS, emissões estimadas e o fator marginal do MCTI. Bom exercício: reconstruir como `03_integracao.painel_subsistema` monta cada coluna.
- **Nomes que confundem:** corte = `curtail_corte_mwh_eolica` no painel por subsistema e `curtail_eolica_mwh` no painel por UF; `ger_fora_sin_mwh` (Roraima isolada) fica fora das colunas `ger_*` no painel por subsistema.

## 8. Casos reais de "apuramento" (ótimos para ensinar — sintoma → investigação → causa → correção → verificação)
1. **Decimais como texto (D16):** parquets antigos do ONS com `'1893.18000000'`, `'0E-8'` → coerção central em `02_limpeza_ons.coerce_numeric`.
2. **Sinal do intercâmbio (D22):** o balanço do ONS publica exportação líquida; com o sinal invertido, geração + intercâmbio − carga fecha em 0,0 % (antes: −35 % / +136 %).
3. **Eólica do SE a 9 % do balanço (D24):** correlação hora a hora do resíduo com cada parque → `CJU_BASDA1` (Serra das Almas II, BA) com **r = 1,000** e 547 GWh = o resíduo exato. Quatro publicações do ONS o põem no SE, duas no NE → subsistema dos conjuntos passa a seguir o cadastro.
4. **Eólica do NE a 100,7 % (D26):** o conjunto solar "Conj. Alex" (CE) tinha combustível "Eólica" no cadastro e era classificado pelo combustível → classificar pelo tipo primeiro.
5. **Térmica do N a 104,5 % (D27):** era Roraima, sistema isolado até a interligação em **15/07/2025**; depois disso, 5 usinas seguem fora (soma = resíduo, 73,2 GWh).
6. **Intercâmbio do S (sem decisão):** a diferença era o intercâmbio internacional (Argentina/Uruguai), pico de 1 534 MW em julho.
7. **Lag eólica × vento de −1/−2 h:** não era erro de relógio — some quando se soma o corte à geração (o corte distorce a série verificada).
8. **PE com r = 0,35 entre eólica e vento (D28):** o peso climático vinha de um conjunto sem geração em 2025; pesos passaram a vir das usinas que geram no mês → r = 0,69.
9. **25 % da potência sem coordenada (D30):** CEG com sufixo `.01` no ONS e `.1` na ANEEL → casar pelo núcleo → 0 %.
10. **Coordenadas em outra UF (D32):** 33 casos revisados à mão — 31 divisas legítimas (rios de fronteira), 4 erros da fonte (ex.: Maranhão IV com a coordenada da antiga localização em Joinville/SC).
11. **MCTI (D29/D31):** o primeiro arquivo era o MDL (fator marginal), não o médio; houve um erro de interpretação no meio do caminho (corrigido na D31) — bom exemplo de como checar uma hipótese antes de "corrigir" dados. Curiosidade não resolvida: a margem de operação de jan–jun/2025 é ≈ 10 × o fator médio.
12. **CF solar observado de 113 % em SP (notebook):** a capacidade do painel por UF vem do cadastro do ONS, que não inclui pequenas usinas, mas a geração inclui → numerador e denominador com coberturas diferentes.

## 9. Validações e os números que provam a base (relatório de 2025)
Cobertura 100 % das horas (CMO 96,8 % em maio — lacuna da fonte) · Σ usinas = balanço do ONS em **100,0–100,1 %** para toda fonte × subsistema · fechamento com a carga da API: −0,8 % a −2,5 % (MMGD/perdas) · solar × GHI r = 0,89–0,98 no lag 0 · eólica+corte × vento r = 0,69–0,88 · corte 2025: eólica 23 %, solar 29 % da referência · intensidade estimada 0,0494 vs **0,0461** do MCTI (r mensal 0,98) · fator marginal do MCTI: 0,22 (jan–mar) → 0,55 (jul–nov).

## 10. O notebook de análise (`notebooks/analise_locais_2025.ipynb`)
1. **CF por célula × mês × hora:** curva de potência genérica integrada sobre uma **Weibull** ajustada à média e ao desvio do vento (`k = (dp/média)^−1,086`); solar com correção de temperatura.
2. **Calibração:** escala do vento **α = 1,47** (bissecção para igualar o CF observado, ponderado pela capacidade) e fator solar **1,60**; CF observado por UF embutido (ONS fator de capacidade + corte). Erro por UF: −15 a +10 p.p. (eólica), ±3 p.p. (solar).
3. **Valor do MWh:** `E = OM do MCTI × (1 − taxa de corte do subsistema)`, por mês × hora.
4. **Métrica principal:** tCO₂ evitadas por MW por ano = Σ dias × CF × E. Também energia, intensidade evitada e perda por corte.
5. **Clustering:** forma do perfil (24 h + 12 meses, PCA) + escalares → KMeans (k por silhueta) e Ward com conectividade espacial; clusters ordenados pela métrica.
6. **Sensibilidades** e **regressão** de deslocamento (coeficientes ≈ 0: a hidro absorve a variação horária).
Achados: eólica robusta (litoral/serras RN-PB-CE, sertão BA-PE, litoral RS; ~1 700–2 000 tCO₂/MW/ano no topo); **solar não robusta** (N e S sem dado de corte solar → topo no MA cai para 14 % de sobreposição quando se aplica o corte do NE).

## 11. Plano de estudo sugerido (uma sessão por bloco; ajuste ao ritmo dele)
1. **Visão geral:** pergunta → por que horário → por que essas fontes → camadas raw/processed/analytic. Exercício: abrir `painel_subsistema_h` e descrever uma hora do NE em palavras.
2. **Tempo e unidades:** UTC × local, início da hora, semi-hora→hora (D07), GHI acumulado (D13), PLD 0–23 × MCTI 1–24. Exercício: achar no código onde cada conversão acontece.
3. **Usinas e chaves:** id_ons × CEG × conjunto (D17), `dim_usina`, classificação por grupo. Exercício: seguir o Serra das Almas pelas tabelas.
4. **Balanço e validação:** refazer à mão o fechamento do balanço e a razão Σ usinas ÷ balanço.
5. **Corte e preço:** curtailment por hora e mês, PLD × CMO, térmica por motivo.
6. **Clima:** ERA5, células, agregação por UF (média de área × ponderada por capacidade), correlação com a geração.
7. **Emissões:** fator médio × marginal, D08, comparação com o MCTI.
8. **Notebook:** Weibull, calibração, métrica, clustering — e como defender as limitações na apresentação.

Exemplos de consultas para os exercícios (Colab, CSV horário já extraído em `/content/extracted_data`):
```python
import pandas as pd
D = '/content/extracted_data'
p = pd.read_csv(f'{D}/painel_subsistema_h.csv', parse_dates=['ts_local'])
# fechamento do balanço do ONS por subsistema (deve dar ~0 %)
b = p.assign(res=p.bal_ger_hidraulica_mwh + p.bal_ger_termica_mwh + p.bal_ger_eolica_mwh + p.bal_ger_solar_mwh
                 + p.bal_intercambio_liquido_mwh - p.bal_carga_mwh)
print((100 * b.groupby('subsistema').res.sum() / b.groupby('subsistema').bal_carga_mwh.sum()).round(3))
# taxa de corte eólico no NE por hora do dia
ne = p[p.subsistema == 'NE']
print((ne.groupby(ne.ts_local.dt.hour).curtail_corte_mwh_eolica.sum() / ne.groupby(ne.ts_local.dt.hour).ref_eolica_mwh.sum()).round(2))
# fator marginal do MCTI por mês
print(p.groupby(p.ts_local.dt.month).fator_om_mcti_tco2_mwh.mean().round(2))
```
(Exercícios por usina — ex.: Serra das Almas — precisam de `geracao_usina_h`, que está no pacote *completo* ou no parquet, não no CSV horário leve.)

## 12. Perguntas para checar o entendimento
- Por que a geração horária de uma usina não basta para medir o recurso eólico? (corte)
- Por que o fator *marginal* e não o *médio* para "emissão evitada"?
- Se o balanço do ONS fecha em 0 % por construção, o que a validação 3 (Σ usinas ÷ balanço) testa de fato?
- O que muda no ranking solar se o N tiver corte igual ao do NE, e por quê?
- Por que o clustering sozinho não responde "onde é melhor"?

## 13. Prompts para começar
> Leia docs/HANDOFF_estudo.md na pasta projeto_energia e assuma o papel de tutor descrito nele. Quero entender a fundo o código, o processo de coleta, limpeza e validação, e ganhar intimidade com a base de dados. Comece me perguntando o que eu já sei e proponha por onde começar, seguindo o plano de estudo.

No chat do claude.ai, crie um Projeto, suba os arquivos da pasta `Claude outputs/estudo_projeto/` como conhecimento e cole nas **instruções do projeto**:
> Você é meu tutor neste projeto. Siga o arquivo HANDOFF_estudo.md (inclusive a parte "Se esta sessão for no chat do claude.ai"). Explique em pt-BR, começando pela intuição, com exemplos dos dados reais e uma pergunta de checagem ao fim de cada tópico. Quando precisar de números, me dê uma célula para rodar no Colab.

E na primeira mensagem do chat: "Vamos começar. Pergunte o que eu já sei e proponha por onde começar, seguindo o plano de estudo."
