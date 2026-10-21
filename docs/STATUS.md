# STATUS — base de dados "Onde novos MW eólicos/solares evitam mais térmica fóssil"

Última atualização: 2026-10-09 08:30 (hora local) — Etapa 3 concluída (D24–D32); revisão manual de coordenadas feita; pasta para o Drive do grupo em `data/export/drive_projeto_energia_2025/`.

## Onde estamos
- [x] **Etapa 0 — Inventário** concluída e aprovada.
- [x] **Etapa 1 — Piloto** (ago/2021 + ago/2025) concluída; scripts corrigidos contra dados reais (D15–D22).
- [x] **Etapa 2 — Ano de 2025** (decisão do usuário em 2026-09-11: só 2025). 8 760 horas × 4 subsistemas em `painel_subsistema_h`; 245 280 linhas em `painel_uf_h`. Relatório: `docs/relatorio_qualidade_2025.md`. Pacotes CSV (regerados em 2026-10-08 23:40): `data/export/projeto_energia_csv_2025.zip` (leve horário, 88 MB), `..._2025_3h.zip` (leve em 3 h, 60 MB) e `..._2025_completo_3h.zip` (com tabelas por usina, 3 h, 172 MB). O completo horário (398 MB) não foi regerado — `05_exportar_csv.py --ano 2025 --completo`.
- [x] **Etapa 3 — Validação final e documentação** (2026-10-08): todas as pendências técnicas resolvidas (D24–D30); Σ usinas = balanço em 100,0–100,1 % para toda fonte × subsistema. Validação 8 fechada contra o fator médio do MCTI (D31).
- [x] Pacote para o Drive do grupo: `python scripts/06_pacote_drive.py --ano 2025` → `data/export/drive_projeto_energia_2025/` (o usuário faz o upload).
- [ ] **Etapa 4 — Análise no Colab (grupo + Gemini):** clustering/ranking de locais por tCO₂ evitada/MW; notebook pronto em `notebooks/analise_locais_2025.ipynb` (2026-10-09); o roteiro antigo para o Gemini fica em `docs/HANDOFF_colab_gemini.md`.
- [ ] (Opcional) estender para 2022–2024 e 2026 — custo medido abaixo.

## Bloqueio restante (ação do usuário)
Nenhum. MCTI recebido e processado: fator médio (série 2006 → ago/2026) e fatores MDL/Despacho de 2025 (D29, D31).

## O que 2025 mostra (resumo do relatório)
- Cobertura 100 % em todas as séries e meses (CMO 96,8 % em maio — lacuna na fonte).
- Balanço do ONS fecha em 0,00 % em todos os subsistemas (D22). Σ usinas vs balanço: 100,0–100,1 % em toda fonte × subsistema (D24, D26, D27). Fechamento com a carga da API (inclui intercâmbio internacional): N −0,8 %, NE −2,5 %, S −2,1 %, SE −2,5 % (média) — coerente com MMGD/perdas.
- Clima: solar × GHI r = 0,89–0,99 no lag 0 em todas as UFs; eólica × vento³ r = 0,45–0,80 com geração verificada (lag −1/−2 h); com geração + corte e pesos das usinas que geram (D28) o lag vai a 0 e r = 0,69–0,88 (BA 0,87, PI 0,88, RN 0,87, CE 0,86, RS 0,81, PB 0,77, PE 0,69).
- Curtailment 2025: eólica 31,4 TWh de corte / 134,9 TWh de referência (23 %), pico em outubro (32,7 %); solar 12,0 / 40,7 TWh (29 %).
- Intensidade de emissões estimada: 0,022 (jan) → 0,079 (nov) tCO₂/MWh, acompanhando a seca e o PLD (R$ 59 → 280/MWh). Fator médio do MCTI: 0,0461 no ano — nossa estimativa 0,0494 (+7 %), correlação mensal 0,98, maior desvio em maio (+28 %). Margem de operação do MCTI (marginal): 0,21 (mar) → 0,58 (nov); correlação horária 0,92 com a nossa intensidade.
- Volume: bruto 1,5 GB (ERA5 720 MB, ONS ~500 MB, IBGE 223 MB); processado 461 MB (clima_h 30 MB/mês); analítico 25 MB.
- Tempo de parede para o ano: download ONS+API ~20 min, ERA5 ~65 min (3 paralelos, fila do CDS), limpeza ~6 min, integração ~1 min, validação ~5 min, exportação leve ~1 min / completa ~10 min.

## Pendências técnicas (Etapa 3)
Resolvidas em 2026-10-08:
- ~~Eólica SE vs NE~~ → `CJU_BASDA1` (Serra das Almas II 500 kV, BA; 547 GWh) estava no NE só na geração horária e no fator de capacidade; subsistema dos conjuntos passa a seguir o cadastro (D24). Eólica SE: 9 % → 100 %.
- ~~Solar noturno~~ → `flag_solar_noturno` em `geracao_usina_h`: 4 174 registros, 49 usinas, 19 GWh (`PQU_SCSC_F` 2 123 h ≈ 1 MW fixo; picos em `CJU_MGUFPU`, `CJU_RNSDMC`).
- ~~Usinas com horas faltantes~~ → classificadas por usina × mês em `docs/usinas_horas_faltantes_2025-01_2025-12.csv` (entrada/saída/lacuna interna); a maior parte é térmica com lacuna interna (114 usina-mês, 375 GWh) e os "entrada_e_saida" de jan/dez quase não geram.
- ~~Lag eólica × vento~~ → efeito do curtailment, não de carimbo (relatório, seção 5). Clima não alterado.

Resolvidas em 2026-10-08 (segunda rodada):
- ~~Intercâmbio do S~~ → é o intercâmbio internacional; nova coluna `intercambio_internacional_mwh`.
- ~~Eólica NE 100,7 %~~ → conjunto solar classificado como eólico (D26). ~~Térmica N 104,5 %~~ → Roraima isolada (D27).
- ~~PE eólica × vento r = 0,35~~ → pesos de clima pelas usinas que geram (D28): r = 0,69.
- ~~Coordenadas (25 % sem) e `municipio_aneel` vazio~~ → núcleo do CEG (D30): 0,0 % sem coordenada; 33 casos de UF divergente em `docs/revisao_uf_coordenada.csv`.
- ~~ERA5 `.nc`~~ → downloads novos como `.zip`; ~~`run_piloto.sh`~~ marcado obsoleto.

Revisão manual (2026-10-09, D32): 31 divisas conferidas, 4 coordenadas corrigidas, 2 casamentos por nome rejeitados — nenhuma pendência.

Abertas (não bloqueiam): avaliar recalibrar as eficiências de D08 (estimativa +7 % acima do MCTI); a regra de Roraima (D27) é empírica para 2025 — reconferir em outros anos.

## Ambiente e reprodução
- Python 3.9.6 em `.venv`; `requirements.txt` fixado. Chave do CDS em `~/.cdsapirc` (licença aceita).
- Ano inteiro: `bash scripts/run_ano.sh 2025` (inclui `02_limpeza_mcti.py` se houver `data/raw/mcti/Despacho_<ano>_*.xlsx`) (PLD do ano precisa estar em `data/raw/ccee/pld_horario/` e registrado — D15). Exportação: `05_exportar_csv.py --ano 2025 [--completo] [--horas 3]`.
- Estender para outro ano custa ≈ 1,5 GB brutos e ~1,5 h de parede (fila do CDS domina), mais o PLD manual.

## Como retomar
Ler `docs/HANDOFF.md` → este arquivo → `docs/decisoes.md` (D15–D32) → `docs/dicionario_dados.md` → `docs/relatorio_qualidade_2025.md`.
