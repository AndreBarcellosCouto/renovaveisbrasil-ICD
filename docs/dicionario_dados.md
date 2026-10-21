# Dicionário de dados — tabelas geradas (base 2025)

Gerado a partir dos esquemas reais em `data/processed/` e `data/analytic/` (2026-09-11; atualizado na Etapa 3 em 2026-10-08). Cobertura atual: 2025-01 a 2025-12 (todas as tabelas), mais ago/2021 do piloto (sem PLD/clima).
Convenções gerais:
- `ts_utc` = início da hora em UTC; `ts_local` = mesmo instante em horário de Brasília, sem fuso (naive). Semi-horas do ONS (MWmed) viram hora pela **média** das duas (D07); `n_semihoras` registra quantas entraram e `flag_hora_incompleta=1` quando ≠ 2.
- Colunas `*_mwh` em séries horárias equivalem a MWmed da hora (MW médio = MWh na hora).
- `flag_*` são `int8` 0/1. Nada é imputado: lacuna = nulo + flag.
- Tabelas mensais ficam em `data/processed/<tabela>/<tabela>_<AAAA-MM>.parquet` (zstd). Tabelas "inteiras" ficam em `data/processed/<tabela>.parquet`.
- Subsistemas: `N`, `NE`, `S`, `SE` (a API de carga usa `SECO` para SE; convertido no painel).

## Tabelas horárias (processed)

### geracao_usina_h — geração verificada por usina (ONS `geracao_usina_2_ho`)
| coluna | tipo | descrição |
|---|---|---|
| ts_utc, ts_local | datetime | início da hora |
| id_ons | str | identificador ONS da usina, do **conjunto** (usinas Tipo II-C) ou do agrupamento de **pequenas usinas** (Tipo III) — chave para `dim_usina` |
| ceg | str | código CEG da ANEEL; nulo (~43 % das linhas) para conjuntos e pequenas usinas |
| nom_usina, id_subsistema, id_estado | str | nome e localização segundo o ONS; `id_estado='I'` = Itaipu 50 Hz (Paraguai) |
| cod_modalidadeoperacao | str | TIPO I / II-A / II-B / II-C / III, "Conjunto de Usinas", "Pequenas Usinas (Tipo III / MMGD)" |
| nom_tipousina, nom_tipocombustivel | str | tipo e combustível declarados pelo ONS (base da classificação em `dim_usina`) |
| geracao_mwh | float | geração verificada na hora |
| flag_ts_ambiguo, flag_negativo, flag_duplicata | int8 | hora ambígua de horário de verão; valor < 0; mesma usina × hora repetida |
| id_subsistema_origem, flag_subsistema_reatribuido | str / int8 | subsistema publicado na geração horária; 1 quando `id_subsistema` foi substituído pelo do cadastro de conjuntos (D24 — em 2025: `CJU_BASDA1` NE→SE, `CJU_MTCFAZ` N→SE) |
| flag_fora_balanco_sin | int8 | 1 = sistema isolado fora do balanço do SIN (Roraima; D27) — excluído do painel por subsistema |
| flag_solar_noturno | int8 | solar > 0,5 MWh entre 21h e 04h local (valor da fonte mantido; 4 174 registros / 19 GWh em 2025, quase todos de agregados de pequenas usinas) |

### fator_capacidade_renovavel_h — eólica e solar por usina/conjunto (ONS `fator_capacidade_2_di`)
| coluna | tipo | descrição |
|---|---|---|
| id_ons, ceg, nom_usina, id_subsistema, id_estado, nom_modalidadeoperacao, nom_tipousina | str | identificação |
| val_latitudesecoletora, val_longitudesecoletora | float | coordenadas da subestação coletora (usadas em `dim_usina`) |
| fator_capacidade | float | geração verificada ÷ capacidade instalada (0–1) |
| geracao_verificada_mwh, geracao_programada_mwh, capacidade_instalada_mw | float | valores ONS |
| flag_fc_fora_faixa | int8 | fator < 0 ou > 1,05 |
| id_subsistema_origem, flag_subsistema_reatribuido | str / int8 | como em `geracao_usina_h` (D24) |

### termica_motivo_h — térmica por motivo de despacho, formato longo (ONS `geracao_termica_despacho_2_ho`)
| coluna | tipo | descrição |
|---|---|---|
| ceg, cod_usinaplanejamento, nom_usina, id_subsistema | str / Int64 | identificação da usina térmica |
| motivo | str | `total` ou um de: ordemmerito, inflexibilidade, razaoeletrica, garantiaenergetica, gfom, reposicaoperdas, exportacao, reservapotencia, gsub, unitcommitment, constrainedoff |
| geracao_programada_mwh, geracao_verificada_mwh | float | programado (PDP) e verificado para aquele motivo |
Observação: colunas de detalhe do ONS (`*ordemdemeritoref`, `*inflexembutmerito`, `*inflexpura`, `*inflexibilidadedessem`, `val_fdexp`, `val_atendsatisfatoriorpo`) não são despivotadas.

### curtailment_h — constrained-off eólico/solar por usina (ONS `restricao_coff_*_tm`; D12)
Cobertura: eólica desde 2022-09, solar desde 2024-04 (D03) — vazio em ago/2021.
| coluna | tipo | descrição |
|---|---|---|
| id_ons, ceg, nom_usina, id_subsistema, id_estado | str | identificação |
| fonte | str | `eolica` / `solar` |
| geracao_verificada_mwh | float | geração medida |
| geracao_limitada_mwh | float | geração sob restrição (nulo quando não houve restrição) |
| geracao_referencia_mwh | float | quanto a usina geraria sem restrição (estimativa do ONS) |
| geracao_referencia_final_mwh | float | referência revisada (raramente preenchida) |
| disponibilidade_mw | float | disponibilidade declarada |
| motivo | str | razão/origem (`REL`, `CNF`, `ENE`, `PAR` / `LOC`, `SIS`); códigos distintos das duas semi-horas unidos por `\|`; nulo sem restrição |
| flag_ref_menor_que_verif | int8 | referência < verificada (inconsistência; ~29 % eólica, ~16 % solar em ago/2025) |
Corte na hora = `max(referência − verificada, 0)` (calculado nos painéis).

### carga_h — carga verificada por área (API `apicarga.ons.org.br`; D02)
| coluna | tipo | descrição |
|---|---|---|
| area_carga | str | `SECO`, `S`, `NE`, `N` (subsistemas) ou sigla de UF. Áreas que **não respondem** na API: AL, BA, PB, PE, RN, SE, TO |
| subsistema | str | preenchido só quando a área é um subsistema |
| carga_global_mwh | float | carga global (inclui MMGD a partir de 2023-04) |
| carga_global_consistida_mwh, carga_global_sem_mmgd_mwh, carga_supervisionada_mwh, carga_nao_supervisionada_mwh, parcela_mmgd_mwh, consistencia_mwh | float | componentes publicados pela API |
| regime_metodologico | str | `pre_2021_03` / `2021_03_a_2023_04` / `pos_2023_04_mmgd` |
| flag_mmgd_nulo | int8 | parcela MMGD ausente |

### cmo_h — custo marginal de operação (ONS `cmo_tm`, semi-horário → hora)
`submercado`, `cmo_rs_mwh` (R$/MWh), `n_semihoras`, flags. Ago/2021 tem 93,5 % das horas (lacunas na fonte).

### balanco_subsistema_h — balanço do ONS (referência de validação)
`subsistema`, `ger_hidraulica_mwh`, `ger_termica_mwh` (inclui nuclear e biomassa), `ger_eolica_mwh`, `ger_solar_mwh`, `carga_mwh`, `intercambio_liquido_mwh` (positivo = importação; o ONS publica `val_intercambio` como exportação líquida e o sinal é invertido na limpeza — D22). Com essa convenção, geração + intercâmbio − carga = 0 exatamente. A antiga divergência de eólica no SE (Serra das Almas, 547 GWh/ano) foi resolvida pela D24: Σ usinas = balanço em 100 % nos quatro subsistemas.

### curva_carga_h — curva de carga horária por subsistema (ONS)
`subsistema`, `carga_mwh`.

### intercambio_h — fluxos entre subsistemas (ONS `intercambio_nacional_ho`)
`origem`, `destino`, `fluxo_mwh` (negativo = sentido inverso). Nos painéis: `intercambio_liquido_mwh` = Σ entradas − Σ saídas.

### pld_h — PLD horário (CCEE, download manual; D15/D20)
`ts_utc`, `ts_local`, `submercado` (N/NE/S/SE), `pld_rs_mwh` (R$/MWh), `flag_ts_ambiguo`, `convencao_hora_origem` (`0-23`). Só 2025 disponível.

### preco_h — preços por submercado
`submercado`, `cmo_rs_mwh`, `pld_rs_mwh` (nulo fora de 2025), `flag_pld_nulo`, `flag_cmo_nulo`.

## Clima (ERA5 single levels, grade 0,5°; D01, D13, D21)

### dim_celula — grade ERA5 (inteira)
`id_celula` (ex.: `cm02.50_m042.50` = lat −2,5, lon −42,5), `lat`, `lon`, `uf`, `cod_municipio_ibge`, `municipio` (ponto-em-polígono IBGE 2024), `terrestre` (1 = dentro de alguma UF), `subsistema` (via `uf_subsistema`). 6 480 células, 2 842 terrestres.

### clima_h — horário por célula terrestre (mensal; ~2,1 M linhas/mês)
`ts_utc` (carimbo ERA5, instantâneo), `id_celula`, `ws100_ms` (vento a 100 m, √(u²+v²)), `ws10_ms`, `ghi_wm2` (ssrd/3600, deslocado −1 h para "início da hora"; D13), `t2m_c` (°C), `flag_ghi_nulo` (última hora do mês). Não entra no pacote CSV padrão (169 MB/mês); `05_exportar_csv.py --com-clima-celula` inclui.

### clima_agregado_h — por UF e por subsistema (mensal)
`ts_utc`, `unidade_tipo` (`uf` / `subsistema`), `unidade`, `metodo` (`media_area` = média das células; `ponderada_cap_eolica` / `ponderada_cap_solar` = média ponderada pela capacidade de `dim_usina` na célula), `ws100_ms`, `ghi_wm2`, `t2m_c`, `n_celulas`. Nos painéis, os três métodos viram sufixos ``, `_pe`, `_ps` (nulos onde não há capacidade eólica/solar com coordenada — ex.: N para eólica).

### clima_perfil_mes_hora — climatologia por célula (inteira; recalculada com tudo que existe em `clima_h`)
`id_celula`, `mes`, `hora_local`, `n_horas`, `{ws100_ms,ghi_wm2,t2m_c}_media`, `{...}_dp`.

## Tabelas diárias / semanais / mensais (processed)

### hidro_d — armazenamento e afluência por subsistema (ONS EAR/ENA diários)
`data`, `subsistema`, `ear_pct`, `ear_mwmes`, `ear_max_mwmes`, `ena_mwmed`, `ena_pct_mlt`, `ena_armazenavel_mwmed`, `ena_armazenavel_pct_mlt`.

### cvu_semanal — custo variável unitário por térmica (ONS)
`mes`, `dat_iniciosemana`, `dat_fimsemana`, `num_revisao`, `cod_usinaplanejamento`, `nom_usina`, `subsistema`, `cvu_rs_mwh`.

### capacidade_mensal — capacidade instalada no despacho ONS (D09)
`mes`, `uf`, `subsistema`, `grupo`, `potencia_mw` (soma das unidades em operação no mês), `flag_sem_data_operacao_excluida`.

### mmgd_mensal — micro/minigeração distribuída acumulada (ANEEL)
`mes`, `uf`, `municipio`, `cod_municipio_ibge`, `fonte`, `potencia_acumulada_mw` (unidades conectadas até o fim do mês).

## Dimensões e cadastros (processed, inteiras)

### dim_usina — uma linha por `id_ons` (ou por CEG quando não há id)
| coluna | descrição |
|---|---|
| chave | `id_ons` ou, na falta, `ceg_ons` |
| id_ons, ceg_ons, nome, tipo_usina, combustivel_ons, modalidade_ons, subsistema, uf | do cadastro ONS `CAPACIDADE_GERACAO` (unidades geradoras agregadas por usina/conjunto) ou, se a usina só aparece na geração horária, de `geracao_usina_h` (`origem_cadastro`) |
| grupo | `hidro` / `eolica` / `solar` / `nuclear` / `fossil` / `biomassa` / `outro` (função `classificar`) |
| combustivel | padronizado para fóssil: gas_natural, gnl, oleo_diesel, oleo_combustivel, carvao, gas_processo (base do fator de emissão, D08) |
| fonte | agregação: hidro / eolica / solar / nuclear / termica / outro |
| data_inicio_operacao, potencia_total_mw, potencia_mw | potência total cadastrada e potência das unidades ainda ativas |
| lat, lon, fonte_coord, qualidade_match | coordenadas: `ons_fator_capacidade_coletora` (exato), `siga_ceg` (exato), `siga_nome` (aproximado, difflib ≥ 0,85 na mesma UF — revisar em `docs/revisao_match_usinas.csv`), ou nulo (`sem_match`) |
| ceg_aneel | CEG do SIGA correspondente |
| cod_municipio_ibge, municipio, uf_geo, flag_uf_diverge | ponto-em-polígono na malha IBGE 2024; flag quando a UF geográfica difere da UF do ONS |
Piloto: 834 usinas; 25 % da potência sem coordenada (grandes hidrelétricas e térmicas do SE sem CEG no cadastro/SIGA).

### dim_tempo — calendário horário
`ts_utc`, `ts_local`, `data_local`, `hora_local`, `dia_semana` (0 = segunda), `mes`, `ano`, `feriado_nacional`, `fim_de_semana_ou_feriado`.

### siga_usinas — empreendimentos de geração (ANEEL SIGA)
`ceg_aneel`, `nome_aneel`, `uf`, `tipo_geracao` (UHE/UTE/EOL/UFV/PCH/CGH/UTN), `fase`, `origem_combustivel`, `fonte_combustivel`, `nome_combustivel`, `potencia_outorgada_kw`, `potencia_fiscalizada_kw`, `potencia_mw`, `data_inicio_operacao`, `lat`, `lon`, `flag_coord_invalida`. `municipio_aneel` vem vazio (coluna `DscMuninicpios` não é lida — pendente).

### uf_subsistema — UF → subsistema predominante (do cadastro ONS)
28 linhas (inclui `PY` para Itaipu).

## Painéis analíticos (analytic)

### painel_subsistema_h — 4 subsistemas × hora
| grupo de colunas | descrição |
|---|---|
| ger_{hidro,fossil,biomassa,nuclear,eolica,solar,outro}_mwh | soma de `geracao_usina_h` por `grupo` de `dim_usina` |
| emissoes_estimadas_tco2, ger_fossil_sem_fator_mwh | D08: geração fóssil × fator por combustível; parcela sem fator |
| carga_global_mwh, parcela_mmgd_mwh, regime_metodologico, flag_mmgd_nulo | da API de carga (área = subsistema) |
| term_fossil_{motivo}_mwh, term_fossil_total_mwh | térmica fóssil verificada por motivo de despacho (D14: térmica sem CEG no cadastro é assumida fóssil) |
| curtail_corte_mwh_{eolica,solar}, ref_{eolica,solar}_mwh | corte estimado e geração de referência (nulos antes da cobertura) |
| intercambio_liquido_mwh | de `intercambio_h` |
| pld_rs_mwh, cmo_rs_mwh | preços |
| data_local, ear_pct, ena_mwmed, ena_pct_mlt | hidrologia diária |
| bal_* | colunas do balanço oficial do ONS, para conferência |
| carga_liquida_mwh, flag_carga_liquida_sem_mmgd | carga − eólica − solar − MMGD |
| ws100_ms, ghi_wm2, t2m_c (+ `_pe`, `_ps`) | clima agregado (média de área; ponderado por capacidade eólica/solar) |

### painel_uf_h — UF × hora
`uf`, `ger_*_mwh`, `emissoes_estimadas_tco2`, `carga_global_mwh`, `parcela_mmgd_mwh`, `regime_metodologico` (só UFs que respondem na API), `curtail_{eolica,solar}_mwh`, `cap_{grupo}_mw` (de `capacidade_mensal`), clima (`ws100_ms`, `ghi_wm2`, `t2m_c` + `_pe`/`_ps`), `subsistema`.

## Cobertura e pacotes
Todas as tabelas acima estão geradas para 2025-01..2025-12. Pendente apenas o arquivo do MCTI (validação 8). Pacote CSV leve (`05_exportar_csv.py --ano 2025`): painéis, séries agregadas, dimensões, cadastros, `clima_agregado_h`, `clima_perfil_mes_hora`. Pacote completo (`--completo`): + `geracao_usina_h`, `fator_capacidade_renovavel_h`, `termica_motivo_h`, `curtailment_h`. `clima_h` só em parquet.

**Pacotes em blocos de 3 h (`--horas 3`, D25).** Todas as tabelas `*_h` saem como `*_3h` (ex.: `painel_subsistema_3h.csv`): `ts_utc`/`ts_local` = início do bloco (00h, 03h, 06h… local); colunas numéricas = **média** das horas presentes no bloco (logo `*_mwh` continua sendo MWmed; energia do bloco = 3 × valor; preços e clima = média simples); `flag_*` = máximo; `n_semihoras`/`num_*` = soma; `n_horas` = horas presentes e `flag_bloco_incompleto=1` quando < 3; `motivo` do curtailment = união dos códigos. Tabelas diárias/semanais, dimensões e cadastros vão sem alteração. A base em parquet continua horária.

## Acréscimos da Etapa 3 (2026-10-08)
- `painel_subsistema_h`: `ger_fora_sin_mwh` (geração de sistemas isolados, fora das colunas `ger_*` e das emissões; D27), `intercambio_internacional_mwh` (balanço − intercâmbio nacional; positivo = importação; ≠ 0 só no S), `fator_om_mcti_tco2_mwh` (margem de operação horária do MCTI/MDL, igual nos 4 subsistemas; D29).
- `painel_uf_h`: `ger_fora_sin_mwh` (parcela isolada, já incluída nas colunas `ger_*` da UF).
- `ws100_ms_pe`, `ghi_wm2_ps` e afins (`clima_agregado_h`, métodos `ponderada_cap_*`): pesos = capacidade das usinas que geram no mês, pela UF/subsistema da usina (D28).
- `mcti_margem_operacao_h` (mensal): `ts_utc`, `ts_local`, `fator_om_tco2_mwh`, `convencao_hora_origem='1-24'` (hora que termina), `arquivo_origem`.
- `mcti_fator_medio` (inteira): `ano`, `mes` (nulo na linha anual), `periodo` (`anual` | `mensal`), `fator_medio_tco2_mwh` (fator médio do SIN, inventários corporativos; 2006 → ago/2026), `arquivo_origem` (D31).
- `mcti_fatores_mdl` (inteira): `ano`, `mes`, `dia`, `tipo` (`margem_construcao` | `margem_operacao_mensal` | `margem_operacao_diaria`), `fator_tco2_mwh`.
- `dim_usina`: casamento com o SIGA pelo núcleo do CEG (D30); `flag_uf_diverge` listado em `docs/revisao_uf_coordenada.csv`; `revisao_coordenada` (`divisa_conferida` | `corrigida` | `removida` | `aproximado_aceito`; nulo = não revisada) e `qualidade_match='centroide_municipio'` / `fonte_coord='revisao_manual'` para as corrigidas (D32). `siga_usinas.municipio_aneel` preenchido ("Município - UF", pode listar vários).
