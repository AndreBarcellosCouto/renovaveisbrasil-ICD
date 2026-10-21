"""Configuração central do pipeline (caminhos, fontes, período).

Nenhuma credencial aqui. A chave do CDS fica em ~/.cdsapirc.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ANALYTIC = ROOT / "data" / "analytic"
DOCS = ROOT / "docs"
MANIFEST = RAW / "manifest.csv"

TZ_LOCAL = "America/Sao_Paulo"

# Período-alvo completo (Etapa 2). O piloto usa PILOTO_MESES.
PERIODO_INICIO = "2019-01"
PERIODO_FIM = "2026-08"
PILOTO_MESES = ["2021-08", "2025-08"]

# ---------------------------------------------------------------- ONS (S3)
ONS_S3 = "https://ons-aws-prod-opendata.s3.amazonaws.com"
ONS_API_CARGA = "https://apicarga.ons.org.br/prd/cargaverificada"

# Cada conjunto: prefixo no bucket, padrão de nome anual e mensal,
# ano a partir do qual os arquivos são mensais (None = sempre anual),
# primeiro período disponível (para não tentar baixar o que não existe).
ONS_DATASETS: dict[str, dict] = {
    "geracao_usina": dict(
        prefix="dataset/geracao_usina_2_ho",
        annual="GERACAO_USINA-2_{y}", monthly="GERACAO_USINA-2_{y}_{m:02d}",
        monthly_from=2022, first="2000-01"),
    "fator_capacidade": dict(
        prefix="dataset/fator_capacidade_2_di",
        annual="FATOR_CAPACIDADE_{y}", monthly="FATOR_CAPACIDADE-2_{y}_{m:02d}",
        monthly_from=2022, first="2009-01"),
    "termica_motivo": dict(
        prefix="dataset/geracao_termica_despacho_2_ho",
        annual="GERACAO_TERMICA_DESPACHO_{y}", monthly="GERACAO_TERMICA_DESPACHO-2_{y}_{m:02d}",
        monthly_from=2022, first="2013-01"),
    # Constrained-off "por usina" (sem sufixo detail): tem geração verificada, limitada,
    # referência, referência final, GNRa e códigos de razão/origem → fonte principal de curtailment_h.
    "coff_eolica": dict(
        prefix="dataset/restricao_coff_eolica_tm",
        annual=None, monthly="RESTRICAO_COFF_EOLICA_{y}_{m:02d}",
        monthly_from=2022, first="2022-09"),
    "coff_fv": dict(
        prefix="dataset/restricao_coff_fotovoltaica_tm",
        annual=None, monthly="RESTRICAO_COFF_FOTOVOLTAICA_{y}_{m:02d}",
        monthly_from=2024, first="2024-04"),
    # "detail": vento/irradiância verificados e geração estimada por usina (complementar, opcional)
    "coff_eolica_detail": dict(
        prefix="dataset/restricao_coff_eolica_detail_tm",
        annual=None, monthly="RESTRICAO_COFF_EOLICA_DETAIL_{y}_{m:02d}",
        monthly_from=2023, first="2023-01", optional=True),
    "coff_fv_detail": dict(
        prefix="dataset/restricao_coff_fotovoltaica_detail_tm",
        annual=None, monthly="RESTRICAO_COFF_FOTOVOLTAICA_DETAIL_{y}_{m:02d}",
        monthly_from=2024, first="2024-04", optional=True),
    "balanco": dict(
        prefix="dataset/balanco_energia_subsistema_ho",
        annual="BALANCO_ENERGIA_SUBSISTEMA_{y}", monthly=None, monthly_from=None, first="2000-01"),
    "curva_carga": dict(
        prefix="dataset/curva-carga-ho",
        annual="CURVA_CARGA_{y}", monthly=None, monthly_from=None, first="2000-01"),
    "intercambio": dict(
        prefix="dataset/intercambio_nacional_ho",
        annual="INTERCAMBIO_NACIONAL_{y}", monthly=None, monthly_from=None, first="2000-01"),
    "ear": dict(
        prefix="dataset/ear_subsistema_di",
        annual="EAR_DIARIO_SUBSISTEMA_{y}", monthly=None, monthly_from=None, first="2000-01"),
    "ena": dict(
        prefix="dataset/ena_subsistema_di",
        annual="ENA_DIARIO_SUBSISTEMA_{y}", monthly=None, monthly_from=None, first="2000-01"),
    "cmo": dict(
        prefix="dataset/cmo_tm",
        annual="CMO_SEMIHORARIO_{y}", monthly=None, monthly_from=None, first="2020-01"),
    "cvu": dict(
        prefix="dataset/cvu_usitermica_se",
        annual="CVU_USINA_TERMICA_{y}", monthly=None, monthly_from=None, first="2005-01"),
    # opcional (D10): energia vertida turbinável
    "evt": dict(
        prefix="dataset/energia_vertida_turbinavel_ho",
        annual="ENERGIA_VERTIDA_TURBINAVEL_{y}", monthly="ENERGIA_VERTIDA_TURBINAVEL_{y}_{m:02d}",
        monthly_from=2024, first="2015-01", optional=True),
}

# Cadastros (sem histórico): baixados inteiros, sempre.
ONS_CADASTROS: dict[str, str] = {
    "capacidade_geracao": "dataset/capacidade-geracao",
    "modalidade_usina": "dataset/modalidade_usina",
    "usina_conjunto": "dataset/usina_conjunto",
    "usina_pqu": "dataset/usina_pqu",
}

# Códigos candidatos de área de carga na API (validados por sondagem em 01_download_ons.py)
ONS_AREAS_CANDIDATAS = [
    "SECO", "S", "NE", "N",
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]

# ---------------------------------------------------------------- CCEE
CCEE_CKAN = "https://dadosabertos.ccee.org.br/api/3/action/package_show?id=pld_horario"

# ---------------------------------------------------------------- ANEEL
ANEEL_SIGA_CSV = ("https://dadosabertos.aneel.gov.br/dataset/6d90b77c-c5f5-4d81-bdec-7bc619494bb9/"
                  "resource/11ec447d-698d-4ab8-977f-b424d5deee6a/download/siga-empreendimentos-geracao.csv")
ANEEL_SIGA_DIC = ("https://dadosabertos.aneel.gov.br/dataset/6d90b77c-c5f5-4d81-bdec-7bc619494bb9/"
                  "resource/25722a60-194d-4234-ab3b-b71354078402/download/dm-siga-sistema-de-informacoes-de-geracao-da-aneel.pdf")
ANEEL_MMGD_PARQUET = ("https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-b622-40438d40aba2/"
                      "resource/cd29f6eb-e08d-4db7-b6fb-ed6e3b682d27/download/empreendimento-geracao-distribuida.parquet")
ANEEL_MMGD_DIC = ("https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-b622-40438d40aba2/"
                  "resource/3fabb9e8-668a-4f94-8f0e-ed9cd2682979/download/dm-geracao-distribuida-relacao-de-empreendimentos.pdf")

# ---------------------------------------------------------------- IBGE
IBGE_BASE = ("https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
             "malhas_municipais/municipio_2024/Brasil/")
IBGE_FILES = ["BR_UF_2024.zip", "BR_Municipios_2024.zip"]

# ---------------------------------------------------------------- ERA5 (D01: 0,5°)
ERA5_DATASET = "reanalysis-era5-single-levels"
ERA5_VARS = [
    "100m_u_component_of_wind", "100m_v_component_of_wind",
    "10m_u_component_of_wind", "10m_v_component_of_wind",
    "surface_solar_radiation_downwards", "2m_temperature",
]
ERA5_AREA = [6.0, -74.0, -34.0, -34.5]   # N, W, S, E (território terrestre + margem)
ERA5_GRID = [0.5, 0.5]

# ---------------------------------------------------------------- sistemas isolados (D27)
# Geração publicada em geracao_usina mas fora do balanço do SIN (identificada hora a hora contra
# balanco_subsistema). Roraima: térmicas isoladas até a interligação em 15/07/2025; depois dela,
# cinco usinas seguem fora. Intervalos em horário local, [desde, ate).
FORA_BALANCO_SIN = [
    dict(uf="RR", tipo="TÉRMICA", desde=None, ate="2025-07-15"),
    dict(ids=["RRUTBB", "RRUTFT", "RRUTMC", "RRUTPL", "RRUTMS"], desde="2025-07-15", ate=None),
]
