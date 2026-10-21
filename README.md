# Where should Brazil build new wind and solar? A data pipeline for the national grid

**Question:** in which locations would a new MW of wind or solar generate the most energy in the hours and seasons when Brazil's grid (the SIN) relies on fossil thermal plants, after discounting the risk of curtailment?

Academic data science project at PUC-Rio, linked to UN Sustainable Development Goal 13 (climate action). Author: André Barcellos Couto Silva.

## Why this question
Brazil's grid is mostly hydro. In dry periods, the operator (ONS) dispatches fossil thermal plants as backup, which is expensive and emission-intensive. At the same time, wind and solar plants, especially in the Northeast, are increasingly curtailed: they are ordered to cut generation the grid cannot absorb. So the windiest or sunniest site is not necessarily the best one. The value of a new MW depends on *when* it produces and *how often* it would be curtailed.

## What was built
A reproducible, hourly database of the Brazilian power sector for **all of 2025** (8,760 hours × 4 grid subsystems; 245,280 rows at state level), integrating seven public sources:

| Source | Data |
|---|---|
| ONS | Hourly generation per plant, capacity factors, curtailment (constrained-off), thermal dispatch by reason, subsystem balance, interchange, marginal cost, reservoirs |
| ONS load API | Half-hourly verified load, with distributed generation separated |
| CCEE | Hourly spot price (PLD) |
| ANEEL | Plant registry (coordinates, municipality) and distributed generation |
| ERA5 (Copernicus) | Hourly climate reanalysis at 0.5°: wind at 100 m, solar irradiance, temperature |
| IBGE | State and municipality boundaries (point-in-polygon matching) |
| MCTI | Official grid emission factors (average and marginal) |

## Pipeline
Numbered Python scripts (~2,700 lines), run end to end with `bash scripts/run_ano.sh 2025`:

1. **Download** (`01_*`): fetches each source and records URL, date and SHA-256 hash in a manifest, so every raw file is traceable.
2. **Cleaning** (`02_*`): standardizes names, types, units and timestamps; half-hourly → hourly; gaps stay null with a flag (nothing is imputed).
3. **Integration** (`03_integracao.py`): star schema with time, plant and climate-cell dimensions; maps each plant to its ERA5 grid cell; builds analysis-ready panels.
4. **Validation** (`04_validacao.py`): eight automated checks that generate a quality report.
5. **Export** (`05_*`, `06_*`): CSV packages (hourly and 3-hour) for the team's analysis in Google Colab.

Design choices: all timestamps stored in UTC plus local time; Parquet (zstd) for storage, monthly partitions; raw data is never edited. Every decision is logged in `docs/decisoes.md` (D01–D32).

## Validation highlights
- Sum of individual plant generation matches ONS's official subsystem balance at **100.0–100.1%** for every source × subsystem.
- Estimated grid emission intensity: **0.0494 tCO₂/MWh vs. 0.0461** from the official MCTI factor (+7%), with a **0.98 monthly correlation**.
- Solar generation vs. irradiance: correlation 0.89–0.99 in every state.
- A puzzling 1–2 hour lag between wind speed and wind generation turned out to be caused by curtailment, not a timestamp error: once curtailed energy is added back, the lag disappears (r = 0.69–0.88).

## Findings so far (preliminary)
- In 2025, about **23% of potential wind** and **29% of potential solar** generation was curtailed; wind curtailment peaked in October (~33%).
- Emission intensity rose from 0.022 (January) to 0.079 tCO₂/MWh (November), tracking the dry season and spot prices (R$ 59 → 280/MWh).
- Top candidate wind regions: the RN–PB–CE coast and highlands, the BA–PE semi-arid interior, and the RS coast. The solar ranking is not yet robust (missing curtailment data in some regions).

## Status
- [x] Inventory, pilot (Aug 2021 / Aug 2025), full 2025 processing, validation and documentation
- [ ] Site ranking and clustering by avoided tCO₂ per MW (`notebooks/analise_locais_2025.ipynb`, in progress)
- [ ] Extend to 2022–2024

## Reproducing
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# needs a Copernicus CDS key in ~/.cdsapirc; the CCEE price file is downloaded manually (see docs)
bash scripts/run_ano.sh 2025
```
Data is not included in this repository (~1.5 GB raw); the pipeline regenerates it.

## Repository layout
```
scripts/    numbered pipeline 01 → 06, config.py, common.py
notebooks/  site analysis (runs in Google Colab)
docs/       decisions log, data dictionary, sources, quality report (in Portuguese)
```

Stack: Python, pandas, NumPy, PyArrow, xarray, GeoPandas, Shapely. Developed with AI-assisted coding (Claude); the design decisions and their reasoning are documented in `docs/decisoes.md`.
