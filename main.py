import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from src.api_service import export_csv, fetch_multiple_diseases, polish_data
from src.cli import (
    clean_storage,
    interactive_tui,
    print_status,
    print_summary,
)
from src.database import get_engine, init_dw_db, init_oltp_db
from src.etl_pipeline import run_etl
from src.oltp_loader import load_oltp_from_raw_df

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DW_CSV_DIR = DATA_DIR / "dw"


def execute_pipeline(
    start_year: int = 2025,
    end_year: int = 2025,
    diseases: Sequence[str] = ("dengue",),
    geocode: int = 3525904,
    start_streamlit: bool = False,
    only_streamlit: bool = False,
) -> None:
    """Executa o pipeline completo no PostgreSQL ou inicia o Streamlit."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DW_CSV_DIR.mkdir(parents=True, exist_ok=True)

    if only_streamlit:
        print("\nIniciando interface analítica Streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/dashboard.py"])
        return

    if start_year > end_year:
        print(f"[AVISO] Anos invertidos ({start_year} > {end_year}). Ajustando automaticamente...")
        start_year, end_year = end_year, start_year

    valid_diseases = {"dengue", "chikungunya", "zika"}
    sanitized_diseases = [d.strip().lower() for d in diseases if d.strip().lower() in valid_diseases]
    if not sanitized_diseases:
        sanitized_diseases = ["dengue"]

    print("=" * 70)
    print("PROJETO INTEGRADOR FATEC - DATA-TO-INSIGHT JOURNEY (POSTGRESQL)")
    print("=" * 70)

    # Conexão com PostgreSQL
    engine = get_engine()

    # 1. Coleta na API InfoDengue
    print(
        f"1. Coletando dados da API InfoDengue...\n"
        f"   • Município (Geocode): {geocode}\n"
        f"   • Arboviroses:         {', '.join(sanitized_diseases)}\n"
        f"   • Período:             {start_year} a {end_year}"
    )

    df_raw = fetch_multiple_diseases(
        diseases=sanitized_diseases,
        geocode=geocode,
        start_year=start_year,
        end_year=end_year,
    )

    if df_raw.empty:
        print("\n[AVISO]: Nenhum dado retornado para os parâmetros informados.")
        return

    print(f"   -> Total de {len(df_raw)} registros epidemiológicos brutos obtidos.")

    # 2. Compatibilidade legada
    df_polish = polish_data(df_raw)
    if not df_polish.empty:
        export_csv(df_polish, file_name="Dengue_Jundiai.csv")

    # 3. Inicialização e Carga no Banco Transacional PostgreSQL (Schema oltp)
    print("\n2. Inicializando Banco de Dados Transacional (PostgreSQL schema: oltp)...")
    init_oltp_db(engine)
    oltp_stats = load_oltp_from_raw_df(df_raw, engine=engine, geocode=geocode)
    print("   -> Schema oltp populado com sucesso no PostgreSQL.")
    print(f"   -> {oltp_stats['notificacoes_inseridas']} notificações registradas em 3FN.")
    if oltp_stats.get("erros_ignorados", 0) > 0:
        print(f"   -> {oltp_stats['erros_ignorados']} registros corrompidos prevenidos e ignorados.")

    # 4. Pipeline de ETL Dimensional no PostgreSQL (Schema dw)
    print("\n3. Executando Pipeline de ETL Dimensional (PostgreSQL schema: dw)...")
    init_dw_db(engine)
    etl_summary = run_etl(engine=engine, export_csv_dir=DW_CSV_DIR)
    print("   -> Schema dw atualizado com Star Schema e Views no PostgreSQL.")
    print(f"   -> Fatos carregados: {etl_summary['fatos_carregados']}")
    print(f"   -> Dimensões geradas: {etl_summary['dimensoes_carregadas']}")
    print(f"   -> Arquivos CSV para Power BI exportados em: {DW_CSV_DIR}/")

    print("\n" + "=" * 70)
    print("POSTGRESQL POPULADO COM SUCESSO!")
    print("Host: localhost:5432 | Database: datadengue | User: postgres")
    print("Schemas: oltp (3FN) e dw (Star Schema + Views)")
    print("=" * 70)

    # 5. Opcional: Abertura do Dashboard Streamlit
    if start_streamlit:
        print("\nIniciando interface analítica Streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/dashboard.py"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DataDengue - Pipeline de Dados Epidemiológicos no PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--ui",
        action="store_true",
        help="Inicia o Streamlit após a execução do pipeline",
    )
    parser.add_argument(
        "--tui",
        "-i",
        action="store_true",
        help="Abre o menu interativo (TUI) no terminal",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2025,
        help="Ano inicial da consulta (padrão: 2025; disponível desde 2010)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2025,
        help="Ano final da consulta (padrão: 2025; até 2026)",
    )
    parser.add_argument(
        "--disease",
        choices=["dengue", "chikungunya", "zika"],
        default="dengue",
        help="Arbovirose única (dengue, chikungunya ou zika)",
    )
    parser.add_argument(
        "--diseases",
        nargs="+",
        choices=["dengue", "chikungunya", "zika"],
        help="Permite selecionar duas ou as três doenças (ex: --diseases dengue chikungunya)",
    )
    parser.add_argument(
        "--all-diseases",
        action="store_true",
        help="Coleta e carrega as 3 arboviroses (dengue, chikungunya e zika) simultaneamente",
    )
    parser.add_argument(
        "--geocode",
        type=int,
        default=3525904,
        help="Código IBGE do município (padrão: 3525904 - Jundiaí)",
    )

    # Subcomandos
    subparsers = parser.add_subparsers(dest="command", help="Comandos utilitários")
    subparsers.add_parser("status", help="Exibe status do banco PostgreSQL, tabelas e CSVs")

    summary_parser = subparsers.add_parser(
        "summary", help="Exibe resumo epidemiológico por ano ou semanas"
    )
    summary_parser.add_argument(
        "--year", type=int, help="Filtrar por um ano específico"
    )
    summary_parser.add_argument(
        "--limit", type=int, default=20, help="Limite de registros a exibir"
    )
    summary_parser.add_argument(
        "--json", action="store_true", help="Exporta o resumo no formato JSON"
    )

    clean_parser = subparsers.add_parser(
        "clean", help="Limpa o schema dw ou todo o banco PostgreSQL"
    )
    clean_parser.add_argument(
        "--all",
        action="store_true",
        help="Limpa também o schema transacional oltp",
    )
    clean_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Confirma a limpeza sem pedir confirmação interativa",
    )

    subparsers.add_parser("tui", help="Abre o menu interativo (TUI)")

    args = parser.parse_args()

    # Roteamento dos comandos
    if args.tui or args.command == "tui":
        interactive_tui(DATA_DIR, execute_pipeline)
    elif args.command == "status":
        print_status(DATA_DIR)
    elif args.command == "summary":
        print_summary(DATA_DIR, as_json=args.json, year=args.year, limit=args.limit)
    elif args.command == "clean":
        if not args.yes:
            tipo = "TOTAL (oltp + dw no PostgreSQL)" if args.all else "do Data Warehouse (schema dw no PostgreSQL)"
            confirm = input(f"Confirma a limpeza {tipo}? (s/N): ").strip().lower()
            if confirm != "s":
                print("Operação cancelada.")
                return
        rem = clean_storage(DATA_DIR, clean_oltp=args.all)
        print(f"Limpeza concluída! Removidos: {', '.join(rem) or 'nenhum'}")
    else:
        if args.all_diseases:
            selected_diseases = ["dengue", "chikungunya", "zika"]
        elif args.diseases:
            selected_diseases = args.diseases
        else:
            selected_diseases = [args.disease]

        execute_pipeline(
            start_year=args.start_year,
            end_year=args.end_year,
            diseases=selected_diseases,
            geocode=args.geocode,
            start_streamlit=args.ui,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERRO CRÍTICO]: {e}", file=sys.stderr)
        sys.exit(1)
