import sqlite3
import pandas as pd
import pytest

from src.database import init_oltp_db
from src.oltp_loader import load_oltp_from_raw_df


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


def test_oltp_loader_creates_tables_and_inserts_data(tmp_path, sample_raw_df):
    db_file = tmp_path / "test_oltp.db"
    init_oltp_db(db_file)

    stats = load_oltp_from_raw_df(sample_raw_df, db_file, geocode=3525904)

    assert stats["notificacoes_inseridas"] == 2
    assert stats["municipios_inseridos"] == 1

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM tb_municipio")
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT COUNT(*) FROM tb_notificacao_dengue")
    assert cur.fetchone()[0] == 2

    cur.execute("SELECT COUNT(*) FROM tb_monitoramento_climatico")
    assert cur.fetchone()[0] == 2

    cur.execute("SELECT COUNT(*) FROM tb_alerta_epidemiologico")
    assert cur.fetchone()[0] == 2

    conn.close()


def test_oltp_loader_is_idempotent(tmp_path, sample_raw_df):
    db_file = tmp_path / "test_oltp_idempotent.db"
    init_oltp_db(db_file)

    # Executa a primeira carga
    load_oltp_from_raw_df(sample_raw_df, db_file, geocode=3525904)
    # Executa a segunda carga com os mesmos dados (deve atualizar ou manter sem duplicar)
    load_oltp_from_raw_df(sample_raw_df, db_file, geocode=3525904)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tb_notificacao_dengue")
    assert cur.fetchone()[0] == 2
    conn.close()
