from pathlib import Path
import pytest
from src.cli.service import clean_storage, get_system_status
from src.database import get_engine, init_oltp_db, init_dw_db


def test_clean_storage_removes_dw_files(tmp_path):
    # Cria estrutura simulada
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dw_dir = data_dir / "dw"
    dw_dir.mkdir()

    legacy_csv = data_dir / "Dengue_Jundiai.csv"
    csv_file = dw_dir / "fato_casos_dengue.csv"

    legacy_csv.write_text("dummy legacy")
    csv_file.write_text("dummy csv")

    engine = get_engine()

    # Limpa apenas DW
    removed = clean_storage(data_dir=data_dir, engine=engine, clean_oltp=False)

    assert not (dw_dir / "fato_casos_dengue.csv").exists()
    assert legacy_csv.exists()

    # Limpa tudo (incluindo oltp e arquivo legado)
    removed_all = clean_storage(data_dir=data_dir, engine=engine, clean_oltp=True)
    assert not legacy_csv.exists()


def test_get_system_status_empty_or_populated(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    engine = get_engine()
    status = get_system_status(data_dir=data_dir, engine=engine)

    assert "postgres_online" in status
    assert status["postgres_online"] is True
    assert "total_registros_oltp" in status
    assert "total_registros_dw" in status
    assert "doencas_carregadas" in status
    assert "csvs_gerados" in status
