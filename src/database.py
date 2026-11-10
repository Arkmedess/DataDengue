import os
import socket
from pathlib import Path
from sqlalchemy import create_engine, Engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"


def _resolve_default_db_url() -> str:
    """Detecta automaticamente o melhor host para o PostgreSQL (localhost ou host.docker.internal no WSL)."""
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    for candidate in ["localhost", "host.docker.internal"]:
        try:
            with socket.create_connection((candidate, 5432), timeout=0.5):
                return f"postgresql+psycopg://postgres:postgres@{candidate}:5432/datadengue"
        except Exception:
            continue

    return "postgresql+psycopg://postgres:postgres@localhost:5432/datadengue"


DEFAULT_POSTGRES_URL = _resolve_default_db_url()


def get_engine(db_url: str | None = None) -> Engine:
    """Cria e retorna uma Engine SQLAlchemy conectada ao PostgreSQL."""
    url = db_url or _resolve_default_db_url()
    return create_engine(url, pool_pre_ping=True)


def execute_sql_script(engine: Engine, script_path: Path) -> None:
    """Executa um arquivo de script SQL na Engine informada."""
    if not script_path.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_content = f.read()

    # Separa por comandos e executa dentro de uma transação
    with engine.begin() as conn:
        conn.execute(text(script_content))


def init_oltp_db(engine: Engine | None = None) -> None:
    """Inicializa o schema oltp e as tabelas relacionais em 3FN no PostgreSQL."""
    eng = engine or get_engine()
    execute_sql_script(eng, SQL_DIR / "01_create_transacional_oltp.sql")


def init_dw_db(engine: Engine | None = None) -> None:
    """Inicializa o schema dw, tabelas dimensionais e views analíticas no PostgreSQL."""
    eng = engine or get_engine()
    execute_sql_script(eng, SQL_DIR / "02_create_dw_star_schema.sql")
    execute_sql_script(eng, SQL_DIR / "04_create_views.sql")
