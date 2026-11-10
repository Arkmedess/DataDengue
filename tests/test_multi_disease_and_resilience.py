import sqlite3
import pandas as pd
import pytest

from src.database import init_dw_db, init_oltp_db
from src.etl_pipeline import run_etl
from src.models import RequisitionBody
from src.oltp_loader import load_oltp_from_raw_df


def test_requisition_body_auto_corrects_inverted_years():
    # Testa inversão de anos acidental
    body = RequisitionBody(ey_start=2025, ey_end=2020)
    assert body.ey_start == 2020
    assert body.ey_end == 2025


def test_multi_disease_oltp_and_etl_preserves_both(tmp_path):
    oltp_file = tmp_path / "oltp_multi.db"
    dw_file = tmp_path / "dw_multi.db"
    csv_dir = tmp_path / "dw_csv"
    csv_dir.mkdir()

    init_oltp_db(oltp_file)
    init_dw_db(dw_file)

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

    stats = load_oltp_from_raw_df(sample_data, oltp_file, geocode=3525904)
    assert stats["notificacoes_inseridas"] == 2
    assert stats["erros_ignorados"] == 0

    conn = sqlite3.connect(oltp_file)
    cur = conn.cursor()
    cur.execute("SELECT doenca, casos_notificados FROM tb_notificacao_dengue ORDER BY doenca")
    results = cur.fetchall()
    assert len(results) == 2
    assert results[0] == ("chikungunya", 8)
    assert results[1] == ("dengue", 80)
    conn.close()

    # Roda ETL
    etl_res = run_etl(oltp_file, dw_file, export_csv_dir=csv_dir)
    assert etl_res["fatos_carregados"] == 2
    assert etl_res["dimensoes_carregadas"]["dim_doenca"] == 3

    conn_dw = sqlite3.connect(dw_file)
    cur_dw = conn_dw.cursor()
    cur_dw.execute(
        """
        SELECT d.nome_doenca, f.casos_notificados
        FROM fato_casos_dengue f
        JOIN dim_doenca d ON f.sk_doenca = d.sk_doenca
        ORDER BY d.nome_doenca
        """
    )
    dw_rows = cur_dw.fetchall()
    assert dw_rows[0] == ("Chikungunya", 8)
    assert dw_rows[1] == ("Dengue", 80)
    conn_dw.close()

    assert (csv_dir / "dim_doenca.csv").exists()


def test_oltp_resilience_to_malformed_and_nan_rows(tmp_path):
    oltp_file = tmp_path / "oltp_corrupted.db"
    init_oltp_db(oltp_file)

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

    stats = load_oltp_from_raw_df(dirty_data, oltp_file, geocode=3525904)
    assert stats["notificacoes_inseridas"] == 1
    assert stats["erros_ignorados"] == 1

    conn = sqlite3.connect(oltp_file)
    cur = conn.cursor()
    cur.execute("SELECT casos_notificados, casos_estimados, nivel_alerta FROM tb_notificacao_dengue n JOIN tb_alerta_epidemiologico a ON n.semana_ano = a.semana_ano")
    row = cur.fetchone()
    assert row[0] == 45
    assert row[1] == 45.0  # NaN corrigido
    assert row[2] == 1     # Nível ausente corrigido para 1 (Verde)
    conn.close()
