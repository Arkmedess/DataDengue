import argparse
import subprocess
import sys
from pathlib import Path

from src.api_service import export_csv, get_csv, polish_data
from src.database import init_dw_db, init_oltp_db
from src.etl_pipeline import run_etl
from src.models import RequisitionBody
from src.oltp_loader import load_oltp_from_raw_df

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OLTP_DB = DATA_DIR / "oltp_dengue.db"
DW_DB = DATA_DIR / "dw_dengue.db"
DW_CSV_DIR = DATA_DIR / "dw"


def execute_pipeline(start_streamlit: bool = False) -> None:
    """Executa o pipeline completo: Coleta API -> Carga OLTP -> ETL Star Schema -> Exportação DW."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DW_CSV_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("PROJETO INTEGRADOR FATEC - DATA-TO-INSIGHT JOURNEY (DATADENGUE)")
    print("=" * 70)

    # 1. Coleta na API InfoDengue
    csv_api = RequisitionBody()
    print(f"1. Coletando dados da API InfoDengue (Geocode: {csv_api.geocode}, Doença: {csv_api.disease})...")
    df_raw = get_csv(csv_api)
    print(f"   -> {len(df_raw)} registros epidemiológicos brutos obtidos.")

    # 2. Compatibilidade legada (CSV consolidado)
    df_polish = polish_data(df_raw)
    export_csv(df_polish, file_name="Dengue_Jundiai.csv")

    # 3. Inicialização e Carga no Banco Transacional (OLTP)
    print("\n2. Inicializando Banco de Dados Transacional (OLTP)...")
    init_oltp_db(OLTP_DB)
    oltp_stats = load_oltp_from_raw_df(df_raw, OLTP_DB, geocode=csv_api.geocode)
    print(f"   -> Banco OLTP populado em: {OLTP_DB.name}")
    print(f"   -> {oltp_stats['notificacoes_inseridas']} semanas transacionais registradas em 3FN.")

    # 4. Pipeline de ETL Dimensional (Star Schema)
    print("\n3. Executando Pipeline de ETL Dimensional (Star Schema)...")
    init_dw_db(DW_DB)
    etl_summary = run_etl(OLTP_DB, DW_DB, export_csv_dir=DW_CSV_DIR)
    print(f"   -> Data Warehouse atualizado em: {DW_DB.name}")
    print(f"   -> Fatos carregados: {etl_summary['fatos_carregados']}")
    print(f"   -> Dimensões geradas: {etl_summary['dimensoes_carregadas']}")
    print(f"   -> Arquivos CSV para Power BI exportados em: {DW_CSV_DIR}/")

    print("\n" + "=" * 70)
    print("BACKEND EXECUTADO COM SUCESSO!")
    print("Tabelas prontas para conexão no Power BI Desktop e modelagem DAX.")
    print("=" * 70)

    # 5. Opcional: Abertura do Dashboard Streamlit
    if start_streamlit:
        print("\nIniciando interface analítica Streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/dashboard.py"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orquestrador do Pipeline DataDengue")
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Inicia o Streamlit após a execução do pipeline de dados",
    )
    args = parser.parse_args()

    try:
        execute_pipeline(start_streamlit=args.ui)
    except Exception as e:
        print(f"\n[ERRO CRÍTICO NO PIPELINE]: {e}")
        sys.exit(1)
