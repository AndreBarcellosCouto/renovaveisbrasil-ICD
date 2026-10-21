# Fontes de dados — inventário (Etapa 0)

Data do inventário: 2026-09-11. Nenhum arquivo de dados foi baixado nesta etapa; tamanhos vêm da listagem pública do bucket S3 do ONS (`ons-aws-prod-opendata`) e das páginas dos portais. Colunas e convenções marcadas **(verificar no piloto)** foram lidas de dicionários/páginas, não de dados reais.

Período-alvo: 2019-01-01 → 2026-08-31 (último mês completo). Hora de referência do inventário: horários UTC.

## 0. Convenções gerais observadas

| Fonte | Fuso do carimbo | Início ou fim do intervalo | Observação |
|---|---|---|---|
| ONS arquivos S3 (`din_instante`) | Horário de Brasília, sem indicação de fuso no campo | **Início** da hora (confirmado no dicionário de EVT: "00:00 representa 00:00–00:59:59"; assumido igual para os demais — verificar no piloto) | Horário de verão vigorou até 16/02/2019 → possíveis 23 h e 25 h em dias de transição |
| ONS API Carga Verificada (`din_referenciautc`) | UTC | **Fim** da semi-hora (dicionário v1.1) | `dat_referencia` é o dia local |
| CCEE PLD horário | Horário de Brasília (verificar) | (verificar) | Hora 0–23 ou 1–24 — verificar |
| ERA5 | UTC | Instantâneas (u, v, t2m) válidas no carimbo; acumuladas (ssrd, tp) no intervalo que **termina** no carimbo | ssrd em J/m² por hora → ÷3600 = W/m² médio |
| NASA POWER | UTC (ou LST, opção) | Média da hora | Grade 0,5°×0,625° |

Chave de junção: `ts_utc`. Para o ONS, `ts_utc = ts_local(America/Sao_Paulo) → UTC` usando a regra oficial de horário de verão (pytz/zoneinfo), com tratamento explícito das horas ambíguas/inexistentes de 2019.

## 1. ONS — Portal de Dados Abertos (dados.ons.org.br)

Licença de todos os conjuntos: **CC-BY** (Creative Commons Atribuição). Arquivos servidos em `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/<prefixo>/<ARQUIVO>.{parquet,csv,xlsx}` com dicionário `DicionarioDados_*.{json,pdf}` no mesmo prefixo. Atualização diária (12h e 19h UTC); ONS avisa que dados "podem ser atualizados após a publicação" → guardar `LastModified` e hash no manifesto. Preferir **Parquet** onde existir; CSV onde não.

| # | Conjunto (slug) | Prefixo S3 | Granularidade | Cobertura disponível (parquet) | Unidade | Arquivos / tamanho 2019→2026-08 | Uso no esquema |
|---|---|---|---|---|---|---|---|
| 1 | Geração por Usina em Base Horária (`geracao-usina-2`) | `geracao_usina_2_ho/` | horária, por usina / conjunto (II-C) / grupo de pequenas usinas (III, **previsão**) | 2000→2026-09; anual até 2021, mensal a partir de 2022 | MWmed (= MWh na hora) | 3 anuais (25–47 MB) + 56 mensais (~4,5 MB) ≈ **363 MB** | `geracao_usina_h`, `dim_usina` (campos: `din_instante, id_subsistema, id_estado, cod_modalidadeoperacao, nom_tipousina, nom_tipocombustivel, nom_usina, id_ons, ceg, val_geracao`) |
| 2 | Fator de Capacidade Eólica e Solar (`fator-capacidade-2`) | `fator_capacidade_2_di/` | horária, usinas e conjuntos eólicos/solares despachados | 2009→2026-09; anual até 2021 (`FATOR_CAPACIDADE_AAAA`, sem "-2"), mensal desde 2022 (`FATOR_CAPACIDADE-2_AAAA_MM`) | fator adimensional (geração ÷ capacidade instalada) | ≈ **239 MB** | `fator_capacidade_renovavel_h` — **verificar se o esquema anual (sem -2) é igual ao mensal** |
| 3 | Geração Térmica por Motivo de Despacho (`geracao-termica-despacho-2`) | `geracao_termica_despacho_2_ho/` | horária, por usina térmica; programada e verificada; motivo | anual 2013→2023 (`_AAAA`, sem "-2") **e** mensal 2022→2026-09 (`-2_AAAA_MM`) — há sobreposição 2022–2023 | MWmed | ≈ **63 MB** | `termica_motivo_h` — **decidir qual versão usar em 2022–2023 (proposta: mensal "-2", esquema atual)**; lista de motivos está no dicionário JSON (9 KB) |
| 4 | Constrained-off Eólica — detalhamento por usina (`restricao_coff_eolica_detail`) | `restricao_coff_eolica_detail_tm/` | semi-horária (`_tm`), por usina; geração verificada, referência, limitada, motivo | **2023-01 → 2026-09** (parquet); página cita 2023-02 | MWmed | 45 mensais de 8–15 MB ≈ **482 MB** (maior conjunto do ONS aqui) | complementar (vento medido, geração estimada) — opcional (D12) |
| 5 | Constrained-off Fotovoltaica — detalhamento por usina (`restricao_coff_fotovoltaica_detail`) | `restricao_coff_fotovoltaica_detail_tm/` | semi-horária, por usina | **2024-04 → 2026-09** | MWmed | 30 mensais de 3–5,5 MB ≈ **132 MB** | complementar (irradiância medida) — opcional (D12) |
| 4b | Constrained-off Eólica agregado (`restricao_coff_eolica_usi`) | `restricao_coff_eolica_tm/` | semi-horária, por usina (sem detalhamento) | CSV desde **2022-09**; parquet desde 2023-10 | MWmed | ~3–4,5 MB/mês | **Fonte principal de `curtailment_h`** (D12): tem `val_geracao`, `val_geracaolimitada`, `val_geracaoreferencia`, `val_geracaoreferenciafinal`, `val_geracaonaorealizadaapurada`, `cod_razaorestricao` (REL/CNF/ENE/PAR), `cod_origemrestricao` (LOC/SIS), minutos de restrição |
| 5b | Constrained-off Fotovoltaica agregado (`restricao_coff_fotovoltaica`) | `restricao_coff_fotovoltaica_tm/` | semi-horária | 2024-04 → 2026-07 (parquet) | MWmed | ~1 MB/mês | **Fonte principal de `curtailment_h` (solar)** — mesmos campos do eólico (D12) |
| 4c/5c | Constrained-off intra-semi-hora (eólica e FV) | `coff_*_intrasemihora` | sub-semi-horária | recente | — | — | **Fora de escopo** (granularidade abaixo da horária) |
| 6 | Balanço de Energia nos Subsistemas (`balanco-energia-subsistema`) | `balanco_energia_subsistema_ho/` | horária, por subsistema: carga e geração hidráulica, térmica, eólica, FV | 2000→2026 (anual) | MWmed | 8 anuais de 1,5–2,7 MB ≈ **18 MB** | Validação (fechamento, soma por fonte); `painel_subsistema_h` |
| 7 | Carga de Energia Verificada (`carga-energia-verificada`) | **API**: `https://apicarga.ons.org.br/prd/cargaverificada?dat_inicio=AAAA-MM-DD&dat_fim=AAAA-MM-DD&cod_areacarga=XXXX` | **semi-horária**, por área de carga (submercados `SECO, S, NE, N` **e áreas geoelétricas por UF** — `RJ` confirmado); campos `val_cargaglobal, val_cargaglobalcons, val_cargaglobalsmmgd, val_cargasupervisionada, val_carganaosupervisionada, val_cargammgd, val_consistencia` | API respondeu para 2018-06-01 e 2019-01-01 (48 registros/dia/área). Em 2019: `val_cargammgd` e `val_cargaglobalsmmgd` **nulos**; em 2025-08: preenchidos (NE 15h UTC: global 13 359, MMGD 4 538 MWmed) | MWmed | JSON; ~48 × dias × áreas registros; sem arquivo em lote (S3 só tem o dicionário). Estimativa: 4 submercados + ~27 áreas × 2 800 dias ≈ 4,2 M registros ≈ 30–40 MB parquet | `carga_h` (**fonte principal de carga**, com `area_carga`). **Divergência positiva vs. plano**: existe carga semi-horária por área geoelétrica ≈ UF → `painel_uf_h` pode ter carga observada (a enumerar os códigos no piloto) |
| 8 | Curva de Carga Horária (`curva-carga`) | `curva-carga-ho/` | horária, por subsistema | 2000→2026 (anual) | MWmed (verificar) | ~0,5 MB/ano ≈ **4 MB** | Validação cruzada da carga (7) |
| 9 | Intercâmbios entre Subsistemas (`intercambio-nacional`) | `intercambio_nacional_ho/` | horária, por par origem→destino | 2000→2026; **parquet só 2023+**, CSV 2019–2022 (1,9 MB/ano) | MWmed | ≈ **9 MB** | `intercambio_h` |
| 10 | EAR Diário por Subsistema (`ear-diario-por-subsistema`) | `ear_subsistema_di/` | diária | 2000→2026 | MWmês e % (verificar) | 40 KB/ano | `hidro_d.ear_pct` |
| 11 | ENA Diário por Subsistema (`ena-diario-por-subsistema`) | `ena_subsistema_di/` | diária | 2000→2026; **parquet só 2021+**, CSV 2019–2020 (107 KB/ano) | MWmed e % MLT (verificar) | <1 MB | `hidro_d.ena_mwmed, ena_pct_mlt` |
| 12 | CMO Semi-Horário (`cmo-semi-horario`) | `cmo_tm/` | semi-horária, por subsistema (DESSEM) | **2020→2026** — não existe para 2019 (há `cmo-semanal` desde antes; não usar como horário) | R$/MWh | ~0,4 MB/ano ≈ 3 MB | `preco_h.cmo_rs_mwh` (média das duas semi-horas) |
| 13 | CVU das Usinas Térmicas (`cvu-usitermica`) | `cvu_usitermica_se/` | por usina, por PMO (semanal `_se`) | 2005→2026 | R$/MWh | ~26 KB/ano | `cvu_mensal` (opcional) |
| 14 | Energia Vertida Turbinável (`energia-vertida-turbinavel`) | `energia_vertida_turbinavel_ho/` | horária, por reservatório | 2015→2026; anual até 2023, mensal 2024+ | MWmed (verificar) | ≈ **239 MB** (28 MB/ano) | `hidro_d.evt_mwh` (opcional; agregar a diário × subsistema) — **proposta: coletar só se sobrar tempo** |
| 15 | Capacidade Instalada de Geração (`capacidade-geracao`) | `capacidade-geracao/` | cadastro por unidade geradora, **sem histórico** (foto atual) | atual | MW | 1 arquivo pequeno | `dim_usina`, `capacidade_mensal`: campos `id_ons, ceg, nom_usina, nom_tipousina, nom_combustivel, nom_modalidadeoperacao, id_subsistema, id_estado, dat_entradaoperacao, dat_desativacao, val_potenciaefetiva` por unidade geradora → permite reconstruir capacidade mensal com desativações (D09) |
| 16 | Modalidade de Operação de Usinas (`modalidade-usina`) | `modalidade_usina/` | cadastro, sem histórico | atual | — | pequeno | `dim_usina.modalidade_ons`; UF→subsistema |
| 17 | Relacionamento Conjuntos ↔ Usinas (`usina_conjunto`) | (verificar prefixo) | cadastro | atual | — | pequeno | mapear conjuntos (II-C) → usinas |
| 18 | Relacionamento Grupos de Pequenas Usinas ↔ Usinas (`usina_pqu`) | (verificar prefixo) | cadastro | atual | — | pequeno | mapear grupos (III) → usinas |

Volume total ONS (parquet/CSV, 2019→2026-08): **≈ 1,55 GB**, dos quais 0,72 GB são os dois "detail" de constrained-off e o EVT (0,24 GB, opcional).

Não existe no portal: "carga horária por UF" em arquivo (mas a API de carga verificada tem áreas geoelétricas — item 7); "capacidade instalada mensal histórica" (só foto atual → `capacidade_mensal` terá de ser derivada da `data_inicio_operacao` do SIGA/ONS, com a limitação de não capturar desativações).

## 2. CCEE — PLD horário (dadosabertos.ccee.org.br)

| Item | Valor |
|---|---|
| Conjunto | `pld_horario` — "dados históricos horários do PLD, por submercado e período" |
| Licença | CC-BY 4.0 |
| Cobertura | PLD horário existe desde **2021-01-01** (arquivos `pld_horario_2021 … 2026`). Antes: `pld_historico_semanal_2001_2020` (PLD **semanal por patamar**, não horário) |
| Formato | CSV, um por ano, URLs opacas do tipo `https://pda-download.ccee.org.br/<id>/content` (ids listados na página do conjunto; podem mudar → o script deve ler a página/API CKAN para obter o link atual) |
| Unidade | R$/MWh |
| Carimbo | hora local (Brasília); convenção 0–23 vs 1–24 **a verificar** |
| Tamanho | ~35 k linhas/ano (4 submercados × 8 760 h) → ~1–3 MB/ano |
| Uso | `preco_h.pld_rs_mwh` (2021+); 2019–2020: **nulo com flag** (PLD semanal por patamar poderia ser expandido para horas, mas isso é imputação metodológica → só se o grupo aprovar, e marcado) |

## 3. ANEEL (dadosabertos.aneel.gov.br) — licença ODbL

| Conjunto | URL | Conteúdo | Formato/tamanho | Uso |
|---|---|---|---|---|
| SIGA — Sistema de Informações de Geração | `.../resource/11ec447d-698d-4ab8-977f-b424d5deee6a/download/siga-empreendimentos-geracao.csv` (mensal) e `siga-empreendimentos-geracao-diario.csv`; dicionário `dm-siga-sistema-de-informacoes-de-geracao-da-aneel.pdf` | usinas com CEG, nome, UF, município, latitude/longitude, fonte, combustível, potência outorgada/fiscalizada, fase, datas de operação | CSV (~15–20 k linhas, ~10 MB; latin-1 e `;` — verificar) | `dim_usina` (coordenadas, potência, data de início); chave de junção = **CEG** |
| MMGD — Relação de empreendimentos de geração distribuída | `.../resource/cd29f6eb-e08d-4db7-b6fb-ed6e3b682d27/download/empreendimento-geracao-distribuida.parquet` (também ZIP/CSV); dicionário `dm-geracao-distribuida-relacao-de-empreendimentos.pdf` | uma linha por unidade (distribuidora, código, classe, subgrupo, **data de conexão**, tipo, **fonte**, **potência instalada kW**, **município, UF**) desde dez/2008 | Parquet; >3,5 M linhas (estimativa) → **100–300 MB** | `mmgd_mensal` = soma acumulada de kW por município × mês × fonte (usando data de conexão) |

## 4. Clima

### 4.1 ERA5 (Copernicus CDS) — plano A
- Conjunto: `reanalysis-era5-single-levels`, horário, 0,25°, 1940→presente (latência ~5 dias; ERA5T preliminar nos últimos 2–3 meses → registrar versão).
- Variáveis: `100m_u_component_of_wind`, `100m_v_component_of_wind`, `10m_u_component_of_wind`, `10m_v_component_of_wind`, `surface_solar_radiation_downwards` (J/m², acumulada na hora que termina no carimbo), `2m_temperature` (K). Opcional: `total_precipitation`.
- Licença: **CC-BY 4.0** (ERA5 passou a CC-BY). Exige conta CDS + chave em `~/.cdsapirc` (nunca no repositório).
- Formato: GRIB (nativo) ou NetCDF; a API aceita `area` (N, W, S, E) e `grid` (reamostragem para 0,5°) na própria requisição.
- Área: caixa −74 → −34,5 lon, −34 → 5,5 lat; máscara terrestre aplicada com a malha do IBGE (offshore fora por ora).

Estimativa de volume (6 variáveis, 67 200 h, 2019-01→2026-08):

| Grade | Pontos na caixa | Células em terra (aprox.) | Bruto (GRIB int16) | `clima_h` (linhas / parquet zstd) | Requisições (1 por mês) | Tempo de fila CDS (típico) |
|---|---|---|---|---|---|---|
| 0,25° | 25 281 | ~11 300 | **~20 GB** | 763 M linhas / **~5 GB** | 92 × ~220 MB | 1–3 dias de parede (fila + limites de requisição simultânea) |
| 0,5° | 6 400 | ~2 800 | **~5 GB** | 191 M linhas / **~1,3 GB** | 92 × ~55 MB | ~0,5–1 dia |

**Recomendação: 0,5°.** Motivos: (i) a resolução efetiva do ERA5 para vento é da ordem de 80–100 km, então 0,25° acrescenta pouco sinal para comparar áreas; (ii) a máquina local tem ~3–4 GB de RAM disponíveis no ambiente de processamento, e 763 M linhas exigiriam processamento por partições estritas; (iii) o ERA5 tem viés local e não será corrigido nesta etapa — a grade serve para comparar regiões entre si, não para dimensionar um parque. Se o grupo quiser 0,25°, sugerimos fazê-lo **só para `clima_perfil_mes_hora`** (climatologia), que pode ser calculada em streaming sem guardar `clima_h` a 0,25°.

### 4.2 NASA POWER — plano B
- API sem chave, horária desde 2001, grade 0,5°×0,625°; parâmetros `WS50M`, `WS10M` (vento a 50 m, não 100 m — extrapolar exige lei de potência, o que é uma premissa a documentar), `ALLSKY_SFC_SW_DWN` (W/m²), `T2M`. Endpoint `hourly/point` por ponto (máx. 15 parâmetros/requisição); ~2 800 pontos × 92 meses → muitas requisições, com limitação de taxa. Usar somente se o CDS for inviável; a troca seria documentada em `decisoes.md`.

### 4.3 INMET — opcional, não inventariado (só checagem pontual).

## 5. Geografia — IBGE
- Malhas municipais 2024: `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2024/Brasil/` → `BR_Municipios_2024.zip` (199 MB, shapefile), `BR_UF_2024.zip` (14 MB), `BR_Pais_2024.zip` (6,7 MB). Modificados em 2025-04-29. Licença: dados públicos IBGE (uso livre com citação).
- Uso: `dim_celula` (célula → UF/município por ponto-em-polígono), máscara terrestre, `dim_usina.municipio` a partir de lat/lon quando o SIGA não trouxer o código IBGE.

## 6. Emissões
- **MCTI/SIRENE — fator médio de emissão do SIN** (tCO₂/MWh), mensal e anual, série desde 2006. Página `gov.br/mcti/.../fatores-de-emissao` está atrás de CAPTCHA para acesso automatizado → **download manual** pelo usuário, registrado no manifesto (arquivo XLSX pequeno). Mudança metodológica em 2025: passou a incluir solar, eólica não conectada diretamente à Rede Básica e biomassa na base de cálculo (jan–abr/2025: 0,0237 / 0,0248 / 0,0215 / 0,0289 tCO₂/MWh — confirmados pelo arquivo `Inventario_2026_janago.xlsx`, série 2006 → ago/2026, baixado em 2026-10-08; D31). Uso: validação 8.
- **MCTI — fatores MDL, método Despacho** (`Despacho_<ano>_*.xlsx`, mesma página, baixado em 2026-10-08): margem de operação horária/diária/mensal e margem de construção anual. Fator marginal, não médio. Processado por `02_limpeza_mcti.py` (D29).
- **Fatores por combustível** (tCO₂/MWh gerado): a serem montados a partir de fatores de emissão por conteúdo energético do IPCC 2006 (tCO₂/TJ: gás natural 56,1; óleo diesel 74,1; óleo combustível 77,4; carvão sub-betuminoso 96,1) × premissa de eficiência por tecnologia (documentada em `decisoes.md`, com faixa de incerteza). Biomassa, nuclear, hidro, eólica e solar = 0 tCO₂/MWh (escopo direto). Combustível não classificável → nulo com flag. Fonte alternativa a verificar: fatores do próprio MCTI/SIRENE por tipo de térmica.

## 7. Acesso de rede — situação em 2026-09-11

Teste de conectividade (HTTPS) feito a partir do ambiente de processamento em nuvem e do ambiente local isolado na máquina do usuário:

| Domínio | Nuvem | Local (VM isolada) |
|---|---|---|
| dados.ons.org.br | bloqueado (403 do proxy) | sem rede |
| ons-aws-prod-opendata.s3.amazonaws.com | bloqueado | sem rede |
| apicarga.ons.org.br | não testado no shell (funcionou via ferramenta de leitura de páginas) | sem rede |
| dadosabertos.ccee.org.br, pda-download.ccee.org.br | bloqueado | sem rede |
| dadosabertos.aneel.gov.br | bloqueado | sem rede |
| cds.climate.copernicus.eu | bloqueado | sem rede |
| power.larc.nasa.gov | bloqueado | sem rede |
| geoftp.ibge.gov.br | bloqueado | sem rede |
| gov.br (MCTI) | bloqueado + CAPTCHA | sem rede |
| pypi.org / files.pythonhosted.org | **bloqueados** (403 host_not_allowed) — impede instalar pyarrow, geopandas, xarray, cdsapi | — |
| github.com | liberado | — |

Consequência: **nenhum download de dados pode ser executado pelos scripts a partir dos ambientes atuais**. Ver STATUS.md → "Bloqueios".
