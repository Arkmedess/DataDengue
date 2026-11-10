import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"


def get_db_connection(db_path: Path | str) -> sqlite3.Connection:
    """Cria e retorna uma conexão SQLite com suporte a Foreign Keys."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def execute_sql_script(conn: sqlite3.Connection, script_path: Path) -> None:
    """Executa um arquivo de script SQL inteiro na conexão informada."""
    if not script_path.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_content = f.read()

    with conn:
        conn.executescript(script_content)


def init_oltp_db(db_path: Path | str) -> None:
    """Inicializa as tabelas do banco transacional relacional (OLTP)."""
    conn = get_db_connection(db_path)
    try:
        execute_sql_script(conn, SQL_DIR / "01_create_transacional_oltp.sql")
    finally:
        conn.close()


def init_dw_db(db_path: Path | str) -> None:
    """Inicializa as tabelas dimensionais e views analíticas do Data Warehouse (Star Schema)."""
    conn = get_db_connection(db_path)
    try:
        execute_sql_script(conn, SQL_DIR / "02_create_dw_star_schema.sql")
        execute_sql_script(conn, SQL_DIR / "04_create_views.sql")
    finally:
        conn.close()
