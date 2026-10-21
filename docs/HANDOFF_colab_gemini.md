# HANDOFF para o Gemini (Colab) — onde novos MW eólicos/solares evitam mais térmica fóssil

Cole este arquivo inteiro no Gemini do Colab. Ele descreve os dados (já carregados no Colab como `projeto_energia_csv_2025.zip`), a pergunta de pesquisa, o método recomendado e as armadilhas conhecidas. Trabalhe passo a passo, mostrando o resultado de cada etapa antes de seguir.

## 1. Pergunta e unidade de análise
**Pergunta:** em que locais do Brasil um MW novo de eólica ou de solar evita mais emissões de térmica fóssil no SIN?
**Unidade:** célula terrestre da grade ERA5 de 0,5° (`dim_celula`, `terrestre == 1`, ~2 842 células, cada uma com `uf` e `subsistema`). Análises separadas para **eólica** e **solar**.
**Ano-base:** 2025 (horário). Um ano só — tratar como estudo de caso, não como média climatológica.

## 2. Dados (dentro do zip; ler com `zipfile` + `pd.read_csv(z.open(...))`)
| Tabela | Uso | Colunas-chave |
|---|---|---|
| `clima_perfil_mes_hora.csv` | recurso por célula (818 496 linhas = 2 842 células × 12 meses × 24 h) | `id_celula, mes, hora_local, n_horas, ws100_ms_media, ws100_ms_dp, ghi_wm2_media, ghi_wm2_dp, t2m_c_media, t2m_c_dp` |
| `dim_celula.csv` | localização | `id_celula, lat, lon, uf, municipio, terrestre, subsistema` |
| `painel_subsistema_h.csv` | sistema, hora a hora × 4 subsistemas (35 040 linhas) | `ts_local, subsistema, fator_om_mcti_tco2_mwh, curtail_corte_mwh_eolica, curtail_corte_mwh_solar, ref_eolica_mwh, ref_solar_mwh, term_fossil_ordemmerito_mwh, term_fossil_total_mwh, ger_*_mwh, carga_global_mwh, carga_liquida_mwh, pld_rs_mwh, emissoes_estimadas_tco2` |
| `painel_uf_h.csv` | calibração do fator de capacidade | `ts_local, uf, ger_eolica_mwh, ger_solar_mwh, curtail_eolica_mwh, curtail_solar_mwh, cap_eolica_mw, cap_solar_mw` |
| `dim_usina.csv` | usinas existentes (para mapa/validação) | `nome, grupo, uf, subsistema, potencia_mw, lat, lon` |

Convenções: `ts_local` = início da hora (Brasília); `*_mwh` = MWh na hora (= MW médio). **Atenção ao nome:** no painel por subsistema o corte é `curtail_corte_mwh_eolica`/`_solar`; no painel por UF é `curtail_eolica_mwh`/`_solar`. Corte nulo = sem dado de corte naquela hora/subsistema → tratar como 0 só onde `ref_*` também for nulo. Dicionário completo: `docs/dicionario_dados.md` do pacote.

## 3. Método (etapas)

### Etapa 1 — Fator de capacidade (CF) por célula × mês × hora
**Eólica** (curva genérica de turbina moderna a 100 m): `P(v)=0` se v<3; `(v³−3³)/(12³−3³)` se 3≤v<12; `1` se 12≤v<25; `0` se v≥25 m/s.
Não aplique a curva à velocidade média (a curva é não linear e isso subestima o CF). Use média e desvio: ajuste uma Weibull por célula×mês×hora com `k = (dp/média)^−1,086`, `c = média / Γ(1+1/k)` e calcule `CF = ∫ P(v)·f(v) dv` numericamente (ex.: grade de v de 0 a 30 m/s em passos de 0,1). Multiplique por perdas de 0,88.
**Solar:** `CF = (ghi_media/1000) × 0,80 × [1 − 0,004·(T_cel − 25)]`, com `T_cel = t2m_media + 0,03·ghi_media`. Limite a [0, 1].
**Calibração (obrigatória):** compare o CF anual previsto (média ponderada pela capacidade das células onde há usinas — use `dim_usina` com lat/lon arredondados para 0,5°) com o CF observado por UF em 2025: `(ger + curtail) / cap` do `painel_uf_h` (somando o corte, porque o recurso não depende do corte). Se a razão observado/previsto for estável entre UFs, aplique um fator único por fonte; mostre a tabela UF × CF previsto × observado.

### Etapa 2 — Valor de um MWh por subsistema × mês × hora
A partir do `painel_subsistema_h` (agrupar por `subsistema`, mês e hora de `ts_local`):
- `om[m,h]` = média de `fator_om_mcti_tco2_mwh` (fator marginal oficial do MCTI; igual nos 4 subsistemas).
- `r_fonte[s,m,h]` = Σ corte / Σ referência da fonte (taxa de curtailment). Um MW novo naquele subsistema e hora tende a ser cortado pelo menos nessa taxa.
- **Valor efetivo:** `E_fonte[s,m,h] = om[m,h] × (1 − r_fonte[s,m,h])` (tCO₂ evitadas por MWh gerado).
Mostre heatmaps mês × hora de `om` e de `r` por subsistema. Já conferido nos dados de 2025: o OM varia sobretudo por **mês** (0,22–0,25 em jan–mar → 0,53–0,58 em jul–nov, seca) e pouco por hora (0,37–0,45; mínimo às 18–21h); a eólica do NE é mais forte à noite e em jul–out (coincide com OM alto); no NE o corte ao meio-dia chega a ~50 % da eólica (9h–12h) e ~30 % da solar. Ou seja: horário e estação contam tanto quanto a quantidade de recurso.

### Etapa 3 — Métricas por célula
Para cada célula c no subsistema s, por fonte (dias do mês de 2025 = `d_m`):
- `energia_mwh_por_mw = Σ_m d_m Σ_h CF[c,m,h]`
- `co2_evitado_t_por_mw = Σ_m d_m Σ_h CF[c,m,h] · E[s,m,h]` ← **métrica principal**
- `intensidade_evitada = co2_evitado / energia` (qualidade do horário, independente da quantidade de recurso)
- `perda_por_corte = 1 − Σ CF·(1−r) / Σ CF`
Grave uma tabela `scores_celulas.csv` com essas colunas + `id_celula, lat, lon, uf, subsistema, fonte`.

### Etapa 4 — Clustering (regionalização)
Objetivo: agrupar células com **regimes** semelhantes e depois ordenar os grupos pela métrica principal — o cluster em si não é "o melhor"; a ordenação é.
- **Features (por fonte):** perfil médio de 24 h do CF (média nos meses) e perfil de 12 meses, ambos divididos pela média anual da célula (forma), + CF anual (nível) + `intensidade_evitada` + `perda_por_corte`. Padronize (`StandardScaler`); PCA guardando ~90 % da variância.
- **Algoritmos:** `KMeans` (k de 4 a 10; escolha por silhueta + cotovelo + interpretabilidade, `n_init=20`, `random_state=0`). Compare com `AgglomerativeClustering(linkage='ward')` com `connectivity=kneighbors_graph(lat/lon, 8)` para regiões espacialmente contíguas, e opcionalmente `GaussianMixture`. Para células "representativas" de cada grupo, use o medoide.
- **Saídas:** mapa dos clusters (plotly `scatter_geo` ou geopandas), tabela por cluster (nº de células, UFs, CF médio, `co2_evitado_t_por_mw` mediana e p10–p90, perda por corte), perfis médios (24 h e 12 meses) de cada cluster, e as 20 melhores células por fonte com município/UF.
- **Validação:** sobreponha as usinas existentes (`dim_usina`, `grupo` eólica/solar, tamanho ∝ `potencia_mw`) — os clusters de maior CF devem conter os polos atuais (BA, RN, PI, CE para eólica). Mostre também onde a métrica principal discorda do CF puro (lugares com muito vento mas muito corte).

### Etapa 5 — Sensibilidade (mostrar se o ranking muda)
1. Sem desconto de corte (`E = om`).
2. Valor pela intensidade média estimada do próprio subsistema: `emissoes_estimadas_tco2 / Σ ger_*` em vez do OM.
3. Valor proporcional ao fóssil despachável: `om × term_fossil_ordemmerito_mwh / term_fossil_total_mwh` (só a parte fóssil por ordem de mérito é deslocável; inflexível não sai).
4. Valor econômico: `pld_rs_mwh × (1 − r)` (R$/MW/ano), para comparar emissões evitadas com receita.
Use a correlação de Spearman entre rankings e a sobreposição do top-10 %.

### Etapa 6 (opcional, mais robusta) — Deslocamento marginal empírico
Regressão horária: `Δfóssil_SIN(t)` contra `Δeólica_s(t)` e `Δsolar_s(t)` de cada subsistema, com controles de carga, `ear_pct` e efeitos fixos de mês×hora (abordagem tipo Callaway, Fowlie & McCormick 2018). O coeficiente estima quantos MWh fósseis saem por MWh renovável a mais em cada subsistema; compare com o `E` da Etapa 2.

## 4. Armadilhas e limitações (documentar no relatório)
- Um único ano (2025, com seca no 2º semestre e PLD alto) — o resultado muda com a hidrologia.
- `fator_om_mcti_tco2_mwh` é do SIN inteiro (não diferencia subsistema); a diferença entre locais vem do recurso, do horário e do corte. No arquivo do MCTI, o OM de jan–jun/2025 é ≈ 10 × o fator médio (possível inconsistência da fonte) — por isso a sensibilidade 2.
- Curtailment: a taxa média subestima o corte marginal de um MW adicional; transmissão não é modelada.
- ERA5 a 0,5° (~55 km) suaviza o vento de serras; o CF da curva genérica precisa da calibração da Etapa 1.
- Sem restrições de uso do solo, áreas protegidas, distância à rede ou custo — o ranking é de **potencial de abatimento**, não de viabilidade.
- Emissões próprias (`emissoes_estimadas_tco2`) ficam +7 % acima do fator médio oficial do MCTI em 2025.

## 5. Entregáveis no notebook
1. Seções na ordem das etapas, com texto curto explicando cada decisão.
2. Tabelas: calibração do CF; `scores_celulas.csv`; resumo por cluster; top-20 células por fonte; sensibilidades.
3. Figuras: heatmaps mês×hora (OM, corte); mapas de CF, de `co2_evitado_t_por_mw` e de clusters; perfis por cluster; seleção de k (silhueta/cotovelo).
4. Um parágrafo final respondendo à pergunta: quais regiões/clusters, por fonte, e com que robustez.
