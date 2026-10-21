# Relatório de qualidade — base ago/2025

Gerado em 2026-09-11 12:51 UTC · meses: 2025-08


## 1. Matriz de cobertura

% de horas do mês com ao menos um registro (por série):

| serie | 2025-08 |
|---|---|
| balanco_subsistema_h | 100.0 |
| carga_h | 100.0 |
| clima_agregado_h | 100.0 |
| clima_h | 100.0 |
| cmo_h | 100.0 |
| curtailment_h | 100.0 |
| curva_carga_h | 100.0 |
| fator_capacidade_renovavel_h | 100.0 |
| geracao_usina_h | 100.0 |
| intercambio_h | 100.0 |
| pld_h | 100.0 |
| preco_h | 100.0 |
| termica_motivo_h | 100.0 |

Linhas por série × mês:

| serie | 2025-08 |
|---|---|
| balanco_subsistema_h | 3720 |
| carga_h | 17856 |
| clima_agregado_h | 41664 |
| clima_h | 2114448 |
| cmo_h | 2976 |
| curtailment_h | 162936 |
| curva_carga_h | 2976 |
| fator_capacidade_renovavel_h | 163680 |
| geracao_usina_h | 528240 |
| intercambio_h | 2976 |
| pld_h | 2976 |
| preco_h | 2976 |
| termica_motivo_h | 1187424 |


## 2. Fechamento energético por subsistema

Resíduo = Σ geração por usina (ONS) + intercâmbio líquido − carga global (API), em % da carga.
Esperado: resíduo negativo sistemático ≈ −(MMGD + pequenas usinas não medidas + perdas), maior após 2023-04 quando a carga passou a incluir MMGD.

| subsistema | count | mean | 5% | 25% | 50% | 75% | 95% |
|---|---|---|---|---|---|---|---|
| N | 744.0 | 1.0 | -2.7 | -0.3 | 2.0 | 2.4 | 2.8 |
| NE | 744.0 | -2.8 | -7.9 | -4.4 | -2.4 | -1.0 | 1.3 |
| S | 744.0 | 1.2 | -6.5 | -1.7 | 0.5 | 4.6 | 10.0 |
| SE | 744.0 | -2.8 | -5.7 | -3.6 | -2.3 | -1.7 | -0.9 |

Mesmo cálculo usando somente o Balanço do ONS (referência interna do operador):

| subsistema | mean | 5% | 50% | 95% |
|---|---|---|---|---|
| N | -35.26 | -69.77 | -40.18 | 36.54 |
| NE | 136.26 | 43.65 | 145.25 | 194.60 |
| S | -7.63 | -66.79 | -7.27 | 48.97 |
| SE | -29.15 | -49.75 | -31.15 | -0.58 |


## 3. Soma por usina vs balanço do ONS

Σ geração por usina ÷ balanço do ONS (por fonte × subsistema, meses do escopo). Nota: nuclear entra em 'térmica' no balanço.

| fonte | subsistema | soma_usinas_gwh | balanco_gwh | razao_pct |
|---|---|---|---|---|
| hidro | N | 2399.7 | 2398.9 | 100.0 |
| hidro | NE | 2027.9 | 2027.7 | 100.0 |
| hidro | S | 6571.0 | 6571.1 | 100.0 |
| hidro | SE | 15627.6 | 15628.4 | 100.0 |
| eolica | N | 197.5 | 197.5 | 100.0 |
| eolica | NE | 10869.7 | 10712.3 | 101.5 |
| eolica | S | 669.2 | 669.2 | 100.0 |
| eolica | SE | 4.7 | 109.0 | 4.3 |
| solar | N | 488.5 | 488.5 | 100.0 |
| solar | NE | 2222.4 | 2275.5 | 97.7 |
| solar | S | 781.9 | 781.9 | 100.0 |
| solar | SE | 3751.6 | 3751.6 | 100.0 |
| termica_total | N | 2208.2 | 2186.7 | 101.0 |
| termica_total | NE | 580.3 | 580.3 | 100.0 |
| termica_total | S | 884.2 | 884.2 | 100.0 |
| termica_total | SE | 6687.0 | 6687.0 | 100.0 |


## 4. Sanidade (solar noturno, negativos, duplicatas, horas)

- Solar noturno (21h–04h local): 28272 registros; geração média 0.035 MWh; máx 80.65 MWh; 0.89% > 0,5 MWh.
- Valores negativos em geracao_usina_h: 0 (0.000%).
- Duplicatas (id_ons × hora): 0.
- Horas ambíguas/inexistentes (horário de verão): 0.
- 2025-08: 710 usinas; 0 com horas faltantes; 0 com horas a mais que o mês.
- carga_h: 0 horas com n_semihoras ≠ 2 de 17856.
- cmo_h: 0 horas com n_semihoras ≠ 2 de 2976.
- curtailment_h: 0 horas com n_semihoras ≠ 2 de 162936.
- ERA5 GHI noturno (22h–03h local): média 0.00 W/m²; GHI negativo: 0; ghi nulo: 2842.


## 5. Alinhamento temporal geração × clima

Correlação cruzada por UF entre geração agregada e variável ERA5 (lag em horas; lag>0 = clima adiantado). Esperado: pico em 0.

| uf | par | lag_melhor | r_lag0 | r_melhor | gwh |
|---|---|---|---|---|---|
| BA | eolica×ws100³ | -2 | 0.507 | 0.579 | 4326.067 |
| RN | eolica×ws100³ | -1 | 0.329 | 0.333 | 3011.797 |
| PI | eolica×ws100³ | -3 | 0.597 | 0.732 | 2084.408 |
| CE | eolica×ws100³ | -3 | 0.154 | 0.226 | 743.308 |
| RS | eolica×ws100³ | -1 | 0.705 | 0.705 | 609.241 |
| PB | eolica×ws100³ | -1 | 0.474 | 0.479 | 419.929 |
| PE | eolica×ws100³ | -3 | 0.077 | 0.258 | 278.437 |
| MA | eolica×ws100³ | -3 |  |  | 197.508 |
| SC | eolica×ws100³ | -1 | 0.515 | 0.518 | 59.729 |
| SE | eolica×ws100³ | -3 |  |  | 5.710 |
| RJ | eolica×ws100³ | -3 |  |  | 4.666 |
| PR | eolica×ws100³ | -3 | -0.231 | -0.219 | 0.268 |
| MG | solar×ghi | 0 | 0.925 | 0.925 | 1632.660 |
| SP | solar×ghi | 0 | 0.988 | 0.988 | 856.848 |
| BA | solar×ghi | 1 | 0.914 | 0.914 | 515.065 |
| RN | solar×ghi | 0 | 0.912 | 0.912 | 475.856 |
| CE | solar×ghi | 0 | 0.959 | 0.959 | 373.767 |
| PI | solar×ghi | 1 | 0.873 | 0.897 | 372.651 |
| PR | solar×ghi | 0 | 0.990 | 0.990 | 367.440 |
| MT | solar×ghi | 0 | 0.994 | 0.994 | 339.398 |
| GO | solar×ghi | 0 | 0.993 | 0.993 | 301.276 |
| RS | solar×ghi | 0 | 0.981 | 0.981 | 291.416 |
| MS | solar×ghi | 0 | 0.991 | 0.991 | 209.924 |
| PA | solar×ghi | 0 | 0.984 | 0.984 | 197.902 |
| PE | solar×ghi | 0 | 0.907 | 0.907 | 178.768 |
| RJ | solar×ghi | 0 | 0.990 | 0.990 | 168.954 |
| AL | solar×ghi | 0 | 0.972 | 0.972 | 167.067 |
| MA | solar×ghi | 0 | 0.995 | 0.995 | 128.708 |
| SC | solar×ghi | 0 | 0.985 | 0.985 | 123.054 |
| ES | solar×ghi | 0 | 0.987 | 0.987 | 115.433 |
| PB | solar×ghi | 0 | 0.893 | 0.893 | 105.614 |
| TO | solar×ghi | 0 | 0.992 | 0.992 | 79.388 |
| DF | solar×ghi | 0 | 0.991 | 0.991 | 69.425 |
| RO | solar×ghi | 0 | 0.992 | 0.992 | 57.694 |
| SE | solar×ghi | 0 | 0.963 | 0.963 | 33.639 |
| AM | solar×ghi | -1 | 0.961 | 0.969 | 33.580 |
| AP | solar×ghi | 0 | 0.984 | 0.984 | 17.923 |
| AC | solar×ghi | 0 | 0.986 | 0.986 | 17.511 |
| RR | solar×ghi | 0 | 0.968 | 0.968 | 13.522 |


## 6. Curtailment: referência ≥ verificada

| mes | fonte | registros | usinas | pct_ref_menor_verif | corte_gwh | referencia_gwh | pct_horas_com_motivo | corte_pct_ref |
|---|---|---|---|---|---|---|---|---|
| 2025-08 | eolica | 114576 | 154 | 28.75 | 3449.77 | 14065.07 | 58.56 | 24.53 |
| 2025-08 | solar | 48360 | 65 | 16.28 | 1428.60 | 3672.53 | 39.45 | 38.90 |


## 7. Correspondência ONS ↔ ANEEL

| qualidade_match | usinas | mw | pct_usinas | pct_mw |
|---|---|---|---|---|
| aproximado | 269 | 102708.2 | 47.6 | 51.2 |
| exato | 217 | 47357.9 | 38.4 | 23.6 |
| sem_match | 79 | 50521.9 | 14.0 | 25.2 |

Maiores usinas sem coordenada:

| id_ons | nome | grupo | uf | potencia_mw |
|---|---|---|---|---|
| PYIT50 | ITAIPU 50 HZ | hidro | PY | 14000.0 |
| ALUXG | XINGÓ | hidro | AL | 3162.0 |
| MGSSUS | SÃO SIMÃO | hidro | MG | 1710.0 |
| PRGBM | GOV. BENTO MUNHOZ | hidro | PR | 1676.0 |
| RJGNA2 | GNA II | fossil | RJ | 1672.6 |
| SPJUP | JUPIÁ | hidro | SP | 1551.2 |
| SPPPR | PORTO PRIMAVERA | hidro | SP | 1540.0 |
| SCUHIT | ITÁ | hidro | SC | 1450.0 |
| RJUTN2 | ANGRA II | nuclear | RJ | 1350.0 |
| RJGNA1 | GNA I | fossil | RJ | 1338.3 |
| PRGNB | GOV. NEY BRAGA | hidro | PR | 1260.0 |
| PRGJR | GOV. JOSÉ RICHA | hidro | PR | 1240.0 |
| SPUSLB | LUIZ CARLOS BARRETO | hidro | SP | 1050.0 |
| RJUTRI | TERMORIO | fossil | RJ | 989.2 |
| RJUTMA | TERMOMACAÉ | fossil | RJ | 922.6 |


## 8. Intensidade de emissões vs MCTI

| mes | emissoes_ktco2 | geracao_gwh | intensidade_tco2_mwh | fossil_sem_fator_gwh |
|---|---|---|---|---|
| 2025-08 | 4180.5640 | 55971.3585 | 0.0747 | 0.0000 |

Arquivo do MCTI ausente (download manual pendente). Referência pública: fator médio mensal do SIN em 2025 (jan–abr) entre 0,021 e 0,029 tCO₂/MWh; em 2021 (crise hídrica) os valores mensais do MCTI ficaram na faixa de ~0,1 tCO₂/MWh.
