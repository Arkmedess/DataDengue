from pathlib import Path
import pytest
from src.cli import clean_storage, get_system_status


def test_clean_storage_removes_dw_files(tmp_path):
    # Cria estrutura simulada
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dw_dir = data_dir / "dw"
    dw_dir.mkdir()

    oltp_file = data_dir / "oltp_dengue.db"
    dw_file = data_dir / "dw_dengue.db"
    csv_file = dw_dir / "fato_casos_dengue.csv"

    oltp_file.write_text("dummy oltp")
    dw_file.write_text("dummy dw")
    csv_file.write_text("dummy csv")

    # Limpa apenas DW
    clean_storage(data_dir=data_dir, clean_oltp=False)

    assert oltp_file.exists()
    assert not dw_file.exists()
    assert not csv_file.exists()

    # Limpa tudo
    clean_storage(data_dir=data_dir, clean_oltp=True)
    assert not oltp_file.exists()


def test_get_system_status_empty_or_populated(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    status = get_system_status(data_dir=data_dir)
    assert status["oltp_existe"] is False
    assert status["dw_existe"] is False
    assert status["total_registros_dw"] == 0
