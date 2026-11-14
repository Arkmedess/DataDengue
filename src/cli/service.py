import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

from src.database import get_engine


def _supports_color() -> bool:
    """Verifica se o terminal suporta cores e respeita a variável NO_COLOR."""
    if "NO_COLOR" in os.environ or not sys.stdout.isatty():
        return False
    return True


def _colorize(text_str: str, color_code: str) -> str:
    if not _supports_color():
        return text_str
    return f"\033[{color_code}m{text_str}\033[0m"


def clean_storage(
    data_dir: Path, engine: Engine | None = None, clean_oltp: bool = False
) -> list[str]:
    """Limpa tabelas no PostgreSQL e remove arquivos CSV gerados."""
    eng = engine or get_engine()
    removed = []
    dw_dir = data_dir / "dw"
    legacy_csv = data_dir / "Dengue_Jundiai.csv"

    try:
        with eng.begin() as conn:
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
                    """
                )
            )
            removed.append("schema dw (PostgreSQL)")

            if clean_oltp:
                conn.execute(
                    text(
                        """
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
                removed.append("schema oltp (PostgreSQL)")
    except Exception as e:
        removed.append(f"erro ao truncar banco: {e}")

    if dw_dir.exists():
        shutil.rmtree(dw_dir)
        removed.append(str(dw_dir.name) + "/")

    if clean_oltp and legacy_csv.exists():
        legacy_csv.unlink()
        removed.append(str(legacy_csv.name))

    return removed


def get_system_status(data_dir: Path, engine: Engine | None = None) -> dict[str, Any]:
    """Inspeciona o estado atual do banco PostgreSQL e das tabelas geradas."""
    dw_dir = data_dir / "dw"
    eng = engine or get_engine()

    status: dict[str, Any] = {
        "postgres_online": False,
        "total_registros_oltp": 0,
        "total_registros_dw": 0,
        "periodo_min": None,
        "periodo_max": None,
        "doencas_carregadas": [],
        "csvs_gerados": [],
    }

    try:
        with eng.connect() as conn:
            status["postgres_online"] = True
            try:
                res_oltp = conn.execute(text("SELECT COUNT(*) FROM oltp.tb_notificacao_dengue"))
                status["total_registros_oltp"] = res_oltp.scalar() or 0

                res_doencas = conn.execute(text("SELECT DISTINCT doenca FROM oltp.tb_notificacao_dengue"))
                status["doencas_carregadas"] = [r[0] for r in res_doencas.fetchall()]
            except Exception:
                pass

            try:
                res_dw = conn.execute(text("SELECT COUNT(*) FROM dw.fato_casos_dengue"))
                status["total_registros_dw"] = res_dw.scalar() or 0

                res_periodo = conn.execute(
                    text(
                        """
                        SELECT MIN(t.data_inicio_semana), MAX(t.data_inicio_semana)
                        FROM dw.fato_casos_dengue f
                        JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
                        """
                    )
                )
                row = res_periodo.fetchone()
                if row and row[0]:
                    status["periodo_min"] = str(row[0])
                    status["periodo_max"] = str(row[1])
            except Exception:
                pass
    except Exception:
        status["postgres_online"] = False

    if dw_dir.exists():
        status["csvs_gerados"] = [f.name for f in dw_dir.glob("*.csv")]

    return status


def print_status(data_dir: Path, engine: Engine | None = None) -> None:
    """Exibe no terminal o status formatado do PostgreSQL e das tabelas."""
    st = get_system_status(data_dir, engine)
    cyan = "36"
    green = "32"
    yellow = "33"
    red = "31"

    print("\n" + _colorize("=== STATUS DO SISTEMA DATADENGUE (POSTGRESQL) ===", cyan))

    if st["postgres_online"]:
        print(f"• Banco de Dados PostgreSQL: {_colorize('ONLINE', green)} (localhost:5432/datadengue)")
        doencas_str = ", ".join(st["doencas_carregadas"]) if st["doencas_carregadas"] else "nenhuma"
        print(f"• Schema Transacional (oltp): {st['total_registros_oltp']} semanas | Doenças: {doencas_str}")
        print(f"• Schema Data Warehouse (dw): {st['total_registros_dw']} fatos carregados")
        if st["periodo_min"] and st["periodo_max"]:
            print(f"  Período monitorado:         {st['periodo_min']} a {st['periodo_max']}")
    else:
        print(f"• Banco de Dados PostgreSQL: {_colorize('OFFLINE / NÃO CONECTADO', red)}")
        print("  Execute: docker compose up -d")

    if st["csvs_gerados"]:
        print(f"• Datasets Power BI (CSV):    {len(st['csvs_gerados'])} arquivos em {data_dir / 'dw'}")
        for csv_name in sorted(st["csvs_gerados"]):
            print(f"    - {csv_name}")
    else:
        print(f"• Datasets Power BI (CSV):    {_colorize('Nenhum CSV gerado', yellow)}")
    print()


def print_summary(
    data_dir: Path,
    engine: Engine | None = None,
    as_json: bool = False,
    year: int | None = None,
    limit: int = 20,
) -> None:
    """Exibe um resumo epidemiológico consolidado por ano, doença ou últimas semanas a partir do PostgreSQL."""
    eng = engine or get_engine()

    try:
        with eng.connect() as conn:
            if year is not None:
                query = text(
                    """
                    SELECT 
                        t.semana_ano,
                        d.nome_doenca AS doenca,
                        t.data_inicio_semana,
                        t.nome_mes,
                        f.casos_notificados,
                        ROUND(CAST(f.casos_estimados AS NUMERIC), 0) AS casos_est,
                        ROUND(CAST(f.incidencia_por_100k AS NUMERIC), 1) AS inc_100k,
                        ROUND(CAST(f.taxa_rt AS NUMERIC), 2) AS rt,
                        a.status_alerta_nome AS alerta
                    FROM dw.fato_casos_dengue f
                    JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
                    JOIN dw.dim_alerta a ON f.sk_alerta = a.sk_alerta
                    JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
                    WHERE t.ano = :ano
                    ORDER BY t.sk_tempo DESC, d.sk_doenca ASC
                    LIMIT :lim
                    """
                )
                rows = conn.execute(query, {"ano": year, "lim": limit}).mappings().all()
            else:
                query = text(
                    """
                    SELECT 
                        t.ano,
                        d.nome_doenca AS doenca,
                        COUNT(f.sk_fato) AS semanas,
                        SUM(f.casos_notificados) AS total_casos,
                        ROUND(CAST(SUM(f.casos_estimados) AS NUMERIC), 0) AS total_estimado,
                        ROUND(CAST(AVG(f.incidencia_por_100k) AS NUMERIC), 1) AS inc_media_100k,
                        ROUND(CAST(AVG(f.taxa_rt) AS NUMERIC), 2) AS rt_medio,
                        ROUND(CAST(AVG(f.temp_media_semana) AS NUMERIC), 1) AS temp_med
                    FROM dw.fato_casos_dengue f
                    JOIN dw.dim_tempo t ON f.sk_tempo = t.sk_tempo
                    JOIN dw.dim_doenca d ON f.sk_doenca = d.sk_doenca
                    GROUP BY t.ano, d.sk_doenca, d.nome_doenca
                    ORDER BY t.ano DESC, d.sk_doenca ASC
                    LIMIT :lim
                    """
                )
                rows = conn.execute(query, {"lim": limit}).mappings().all()

        dict_rows = [dict(r) for r in rows]

        if as_json:
            print(json.dumps(dict_rows, indent=2, ensure_ascii=False, default=str))
            return

        if not dict_rows:
            print("Nenhum registro encontrado no Data Warehouse. Execute o pipeline primeiro.")
            return

        headers = list(dict_rows[0].keys())
        col_widths = {h: max(len(h), max(len(str(r[h])) for r in dict_rows)) for h in headers}

        header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
        sep_line = "-+-".join("-" * col_widths[h] for h in headers)

        print("\n" + header_line)
        print(sep_line)
        for r in dict_rows:
            print(" | ".join(str(r[h]).ljust(col_widths[h]) for h in headers))
        print()

    except Exception as e:
        print(f"Erro ao consultar resumo no PostgreSQL: {e}", file=sys.stderr)


def interactive_tui(data_dir: Path, execute_callback) -> None:
    """TUI / Menu interativo no terminal para operações do sistema."""
    cyan = "36"
    yellow = "33"
    green = "32"
    red = "31"

    while True:
        print("\n" + _colorize("===============================================", cyan))
        print(_colorize("   DATADENGUE - PAINEL POSTGRESQL (CLI/TUI)    ", cyan))
        print(_colorize("===============================================", cyan))
        print(" [1] Executar Carga Padrão (Dengue)")
        print(" [2] Carga com Período & Doenças Selecionadas")
        print(" [3] Carga Completa de Todas as Doenças (Dengue + Chikungunya + Zika)")
        print(" [4] Exibir Status do Banco PostgreSQL (oltp & dw)")
        print(" [5] Ver Resumo Epidemiológico Consolidado")
        print(" [6] Abrir Dashboard Streamlit no Navegador")
        print(" [7] Limpar Data Warehouse (Resetar dw)")
        print(" [8] Limpar Tudo (dw + oltp no PostgreSQL)")
        print(" [0] Sair")
        print(_colorize("-----------------------------------------------", cyan))

        try:
            choice = input("Selecione uma opção [0-8]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando...")
            break

        if choice == "0":
            print("Até logo!")
            break
        elif choice == "1":
            print("\n" + _colorize("Executando pipeline padrão para Dengue no PostgreSQL...", green))
            execute_callback(diseases=["dengue"])
        elif choice == "2":
            print("\n" + _colorize("Configuração de Carga Personalizada:", yellow))
            try:
                ano_ini = input("Ano inicial [padrão: 2024]: ").strip() or "2024"
                ano_fim = input("Ano final   [padrão: 2025]: ").strip() or "2025"
                print("\nEscolha as doenças:")
                print("  [1] Apenas Dengue")
                print("  [2] Apenas Chikungunya")
                print("  [3] Apenas Zika")
                print("  [4] Dengue + Chikungunya")
                print("  [5] Dengue + Zika")
                print("  [6] Chikungunya + Zika")
                print("  [7] Todas (Dengue + Chikungunya + Zika)")
                d_opt = input("Opção de arboviroses [1-7, padrão 1]: ").strip() or "1"

                mapping = {
                    "1": ["dengue"],
                    "2": ["chikungunya"],
                    "3": ["zika"],
                    "4": ["dengue", "chikungunya"],
                    "5": ["dengue", "zika"],
                    "6": ["chikungunya", "zika"],
                    "7": ["dengue", "chikungunya", "zika"],
                }
                selected_diseases = mapping.get(d_opt, ["dengue"])
                open_ui = input("Abrir Streamlit ao final? (s/N): ").strip().lower() == "s"

                execute_callback(
                    start_year=int(ano_ini),
                    end_year=int(ano_fim),
                    diseases=selected_diseases,
                    start_streamlit=open_ui,
                )
            except ValueError:
                print(_colorize("Erro: Ano deve ser um número inteiro válido.", red))
        elif choice == "3":
            print("\n" + _colorize("Iniciando coleta integrada das 3 arboviroses...", green))
            ano_ini = input("Ano inicial [padrão: 2024]: ").strip() or "2024"
            ano_fim = input("Ano final   [padrão: 2025]: ").strip() or "2025"
            execute_callback(
                start_year=int(ano_ini),
                end_year=int(ano_fim),
                diseases=["dengue", "chikungunya", "zika"],
            )
        elif choice == "4":
            print_status(data_dir)
        elif choice == "5":
            ano_filtro = input("Filtrar por ano específico (deixe vazio para resumo anual): ").strip()
            y = int(ano_filtro) if ano_filtro.isdigit() else None
            print_summary(data_dir, year=y)
        elif choice == "6":
            execute_callback(only_streamlit=True)
        elif choice == "7":
            confirm = input(_colorize("Confirma a limpeza do Data Warehouse no PostgreSQL? (s/N): ", yellow)).strip().lower()
            if confirm == "s":
                rem = clean_storage(data_dir, clean_oltp=False)
                print(_colorize(f"Limpeza concluída! Removidos: {', '.join(rem) or 'nenhum'}", green))
            else:
                print("Operação cancelada.")
        elif choice == "8":
            confirm = input(_colorize("ATENÇÃO: Confirma reset TOTAL no PostgreSQL (oltp + dw)? (s/N): ", red)).strip().lower()
            if confirm == "s":
                rem = clean_storage(data_dir, clean_oltp=True)
                print(_colorize(f"Reset concluído! Removidos: {', '.join(rem) or 'nenhum'}", green))
            else:
                print("Operação cancelada.")
        else:
            print(_colorize("Opção inválida! Digite um número de 0 a 8.", red))
