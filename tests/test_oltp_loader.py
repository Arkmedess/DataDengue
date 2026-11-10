import pandas as pd
import pytest
from sqlalchemy import text

from src.database import get_engine, init_oltp_db
from src.oltp_loader import load_oltp_from_raw_df


@pytest.fixture(autouse=True)
def clean_oltp_schema():
    engine = get_engine()
    init_oltp_db(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                TRUNCATE TABLE 
                    oltp.tb_notificacao_dengue, 
                    oltp.tb_monitoramento_climatico, 
                    oltp.tb_alerta_epidemiologico, 
                    oltp.tb_unidade_notificadora, 
                    oltp.tb_municipio 
                CASCADE;
                """
            )
        )
    yield


@pytest.fixture
def sample_raw_df():
    data = [
        {
            "data_iniSE": "2025-01-05",
            "SE": 202502,
            "casos_est": 150.0,
            "casos": 120,
            "casconf": 80,
            "casprov": 40,
            "p_rt1": 0.98,
            "p_inc100k": 26.1,
            "Localidade_id": 0,
            "nivel": 3,
            "id": 1001,
            "versao_modelo": "2026-01-01",
            "municipio_nome": "Jundiaí",
            "Rt": 1.45,
            "pop": 459789,
            "tempmin": 18.0,
            "tempmed": 23.5,
            "tempmax": 28.0,
            "umidmin": 60.0,
            "umidmed": 78.0,
            "umidmax": 95.0,
            "receptivo": 1,
            "transmissao": 2,
            "nivel_inc": 1,
            "notif_accum_year": 200,
        },
        {
            "data_iniSE": "2025-01-12",
            "SE": 202503,
            "casos_est": 190.0,
            "casos": 160,
            "casconf": 110,
            "casprov": 50,
            "p_rt1": 0.99,
            "p_inc100k": 34.8,
            "Localidade_id": 0,
            "nivel": 4,
            "id": 1002,
            "versao_modelo": "2026-01-01",
            "municipio_nome": "Jundiaí",
            "Rt": 1.82,
            "pop": 459789,
            "tempmin": 19.0,
            "tempmed": 24.5,
            "tempmax": 29.5,
            "umidmin": 62.0,
            "umidmed": 81.0,
            "umidmax": 98.0,
            "receptivo": 2,
            "transmissao": 3,
            "nivel_inc": 2,
            "notif_accum_year": 360,
        },
    ]
    return pd.DataFrame(data)


def test_oltp_loader_creates_tables_and_inserts_data(sample_raw_df):
    engine = get_engine()

    stats = load_oltp_from_raw_df(sample_raw_df, engine, geocode=3525904)

    assert stats["notificacoes_inseridas"] == 2
    assert stats["municipios_inseridos"] == 1

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM oltp.tb_municipio")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM oltp.tb_notificacao_dengue")).scalar() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM oltp.tb_monitoramento_climatico")).scalar() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM oltp.tb_alerta_epidemiologico")).scalar() == 2


def test_oltp_loader_is_idempotent(sample_raw_df):
    engine = get_engine()

    # Executa a primeira carga
    load_oltp_from_raw_df(sample_raw_df, engine, geocode=3525904)
    # Executa a segunda carga com os mesmos dados (deve atualizar ou manter sem duplicar)
    load_oltp_from_raw_df(sample_raw_df, engine, geocode=3525904)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM oltp.tb_notificacao_dengue")).scalar() == 2
