import sqlite3
import pandas as pd
import pytest

from src.database import init_dw_db, init_oltp_db
from src.etl_pipeline import run_etl
from src.oltp_loader import load_oltp_from_raw_df


@pytest.fixture
def populated_oltp_db(tmp_path):
    oltp_file = tmp_path / "oltp_source.db"
    init_oltp_db(oltp_file)

    sample_data = pd.DataFrame(
        [
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
    )
    load_oltp_from_raw_df(sample_data, oltp_file, geocode=3525904)
    return oltp_file


def test_etl_generates_star_schema_and_csvs(tmp_path, populated_oltp_db):
    dw_file = tmp_path / "dw_test.db"
    csv_dir = tmp_path / "csv_export"
    csv_dir.mkdir()

    init_dw_db(dw_file)

    summary = run_etl(populated_oltp_db, dw_file, export_csv_dir=csv_dir)

    assert summary["fatos_carregados"] == 2
    assert summary["dimensoes_carregadas"]["dim_tempo"] == 2
    assert summary["dimensoes_carregadas"]["dim_municipio"] == 1
    assert summary["dimensoes_carregadas"]["dim_alerta"] >= 4
    assert summary["dimensoes_carregadas"]["dim_clima"] >= 1

    # Valida no banco DW
    conn = sqlite3.connect(dw_file)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM fato_casos_dengue")
    assert cur.fetchone()[0] == 2

    # Verifica cálculo de nowcasting gap (150 - 120 = 30)
    cur.execute("SELECT diferenca_nowcasting FROM fato_casos_dengue WHERE casos_notificados = 120")
    assert cur.fetchone()[0] == 30.0

    conn.close()

    # Valida arquivos CSV gerados para o Power BI
    assert (csv_dir / "dim_tempo.csv").exists()
    assert (csv_dir / "dim_municipio.csv").exists()
    assert (csv_dir / "dim_alerta.csv").exists()
    assert (csv_dir / "dim_clima.csv").exists()
    assert (csv_dir / "fato_casos_dengue.csv").exists()

    df_fato = pd.read_csv(csv_dir / "fato_casos_dengue.csv")
    assert len(df_fato) == 2
    assert "sk_tempo" in df_fato.columns
    assert "sk_municipio" in df_fato.columns
    assert "sk_alerta" in df_fato.columns
    assert "sk_clima" in df_fato.columns
