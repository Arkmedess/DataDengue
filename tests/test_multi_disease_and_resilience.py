import pandas as pd
import pytest
from sqlalchemy import text

from src.database import get_engine, init_dw_db, init_oltp_db
from src.etl_pipeline import run_etl
from src.models import RequisitionBody
from src.oltp_loader import load_oltp_from_raw_df


@pytest.fixture(autouse=True)
def clean_database():
    engine = get_engine()
    init_oltp_db(engine)
    init_dw_db(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                TRUNCATE TABLE 
                    dw.fato_casos_dengue, 
                    dw.dim_tempo, 
                    dw.dim_municipio, 
                    dw.dim_alerta, 
                    dw.dim_clima, 
                    dw.dim_doenca 
                CASCADE;
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


def test_requisition_body_auto_corrects_inverted_years():
    # Testa inversão de anos acidental
    body = RequisitionBody(ey_start=2025, ey_end=2020)
    assert body.ey_start == 2020
    assert body.ey_end == 2025


def test_multi_disease_oltp_and_etl_preserves_both(tmp_path):
    engine = get_engine()
    csv_dir = tmp_path / "dw_csv"
    csv_dir.mkdir()

    # Cria dados simulados com Dengue e Chikungunya na mesma semana
    sample_data = pd.DataFrame(
        [
            {
                "doenca": "dengue",
                "data_iniSE": "2025-01-05",
                "SE": 202502,
                "casos_est": 100.0,
                "casos": 80,
                "casconf": 50,
                "casprov": 30,
                "p_rt1": 0.95,
                "p_inc100k": 20.0,
                "Localidade_id": 0,
                "nivel": 2,
                "municipio_nome": "Jundiaí",
                "Rt": 1.2,
                "pop": 459789,
                "tempmin": 20.0,
                "tempmed": 24.0,
                "tempmax": 28.0,
                "umidmin": 60.0,
                "umidmed": 75.0,
                "umidmax": 90.0,
                "receptivo": 1,
                "transmissao": 1,
                "nivel_inc": 1,
                "notif_accum_year": 150,
            },
            {
                "doenca": "chikungunya",
                "data_iniSE": "2025-01-05",
                "SE": 202502,
                "casos_est": 10.0,
                "casos": 8,
                "casconf": 6,
                "casprov": 2,
                "p_rt1": 0.3,
                "p_inc100k": 1.7,
                "Localidade_id": 0,
                "nivel": 1,
                "municipio_nome": "Jundiaí",
                "Rt": 0.8,
                "pop": 459789,
                "tempmin": 20.0,
                "tempmed": 24.0,
                "tempmax": 28.0,
                "umidmin": 60.0,
                "umidmed": 75.0,
                "umidmax": 90.0,
                "receptivo": 1,
                "transmissao": 0,
                "nivel_inc": 0,
                "notif_accum_year": 12,
            },
        ]
    )

    stats = load_oltp_from_raw_df(sample_data, engine, geocode=3525904)
    assert stats["notificacoes_inseridas"] == 2
    assert stats["erros_ignorados"] == 0

    with engine.connect() as conn:
        res = conn.execute(text("SELECT doenca, casos_notificados FROM oltp.tb_notificacao_dengue ORDER BY doenca"))
        results = res.fetchall()
        assert len(results) == 2
        assert results[0] == ("chikungunya", 8)
        assert results[1] == ("dengue", 80)

    # Roda ETL
    etl_res = run_etl(engine, export_csv_dir=csv_dir)
    assert etl_res["fatos_carregados"] == 2
    assert etl_res["dimensoes_carregadas"]["dim_doenca"] == 3

    with engine.connect() as conn:
        res_dw = conn.execute(
            text(
                """
                SELECT d.nome_doenca, f.casos_notificados
                FROM dw.fato_casos_dengue f
                JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
                ORDER BY d.nome_doenca
                """
            )
        )
        dw_rows = res_dw.fetchall()
        assert dw_rows[0] == ("Chikungunya", 8)
        assert dw_rows[1] == ("Dengue", 80)

    assert (csv_dir / "dim_doenca.csv").exists()


def test_oltp_resilience_to_malformed_and_nan_rows():
    engine = get_engine()

    dirty_data = pd.DataFrame(
        [
            # Linha válida
            {
                "doenca": "dengue",
                "data_iniSE": "2025-01-05",
                "SE": 202502,
                "casos": "45",
                "casos_est": float("nan"),  # NaN deve virar 45
                "tempmed": None,           # None deve virar None
                "nivel": None,             # None deve virar 1
                "municipio_nome": "Jundiaí",
                "pop": 459789,
            },
            # Linha corrompida (data inválida / poison pill)
            {
                "doenca": "dengue",
                "data_iniSE": "data-completamente-invalida",
                "SE": "semana-invalida",
                "casos": "abc",
            },
        ]
    )

    stats = load_oltp_from_raw_df(dirty_data, engine, geocode=3525904)
    assert stats["notificacoes_inseridas"] == 1
    assert stats["erros_ignorados"] == 1

    with engine.connect() as conn:
        res = conn.execute(
            text(
                """
                SELECT n.casos_notificados, n.casos_estimados, a.nivel_alerta 
                FROM oltp.tb_notificacao_dengue n 
                JOIN oltp.tb_alerta_epidemiologico a 
                  ON n.semana_ano = a.semana_ano 
                 AND n.doenca = a.doenca
                """
            )
        )
        row = res.fetchone()
        assert row[0] == 45
        assert float(row[1]) == 45.0  # NaN corrigido
        assert row[2] == 1            # Nível ausente corrigido para 1 (Verde)
