import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _supports_color() -> bool:
    """Verifica se o terminal suporta cores e respeita a variável NO_COLOR."""
    if "NO_COLOR" in os.environ or not sys.stdout.isatty():
        return False
    return True


def _colorize(text: str, color_code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{color_code}m{text}\033[0m"


def clean_storage(data_dir: Path, clean_oltp: bool = False) -> list[str]:
    """Remove arquivos e bases de dados do Data Warehouse e opcionalmente do OLTP."""
    removed = []
    dw_file = data_dir / "dw_dengue.db"
    dw_dir = data_dir / "dw"
    legacy_csv = data_dir / "Dengue_Jundiai.csv"

    if dw_file.exists():
        dw_file.unlink()
        removed.append(str(dw_file.name))

    if dw_dir.exists():
        shutil.rmtree(dw_dir)
        removed.append(str(dw_dir.name) + "/")

    if clean_oltp:
        oltp_file = data_dir / "oltp_dengue.db"
        if oltp_file.exists():
            oltp_file.unlink()
            removed.append(str(oltp_file.name))
        if legacy_csv.exists():
            legacy_csv.unlink()
            removed.append(str(legacy_csv.name))

    return removed


def get_system_status(data_dir: Path) -> dict[str, Any]:
    """Inspeciona o estado atual dos bancos e das tabelas geradas."""
    oltp_file = data_dir / "oltp_dengue.db"
    dw_file = data_dir / "dw_dengue.db"
    dw_dir = data_dir / "dw"

    status: dict[str, Any] = {
        "oltp_existe": oltp_file.exists(),
        "dw_existe": dw_file.exists(),
        "total_registros_oltp": 0,
        "total_registros_dw": 0,
        "periodo_min": None,
        "periodo_max": None,
        "tamanho_oltp_kb": 0.0,
        "tamanho_dw_kb": 0.0,
        "csvs_gerados": [],
    }

    if oltp_file.exists():
        status["tamanho_oltp_kb"] = round(oltp_file.stat().st_size / 1024, 2)
        try:
            conn = sqlite3.connect(oltp_file)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_notificacao_dengue")
            status["total_registros_oltp"] = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass

    if dw_file.exists():
        status["tamanho_dw_kb"] = round(dw_file.stat().st_size / 1024, 2)
        try:
            conn = sqlite3.connect(dw_file)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM fato_casos_dengue")
            status["total_registros_dw"] = cur.fetchone()[0]

            cur.execute(
                """
                SELECT MIN(t.data_inicio_semana), MAX(t.data_inicio_semana)
                FROM fato_casos_dengue f
                JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
                """
            )
            row = cur.fetchone()
            if row and row[0]:
                status["periodo_min"] = row[0]
                status["periodo_max"] = row[1]
            conn.close()
        except Exception:
            pass

    if dw_dir.exists():
        status["csvs_gerados"] = [f.name for f in dw_dir.glob("*.csv")]

    return status


def print_status(data_dir: Path) -> None:
    """Exibe no terminal o status formatado dos bancos e do DW."""
    st = get_system_status(data_dir)
    cyan = "36"
    green = "32"
    yellow = "33"

    print("\n" + _colorize("=== STATUS DO SISTEMA DATADENGUE ===", cyan))
    print(f"Diretório de dados: {data_dir.resolve()}")

    # OLTP
    if st["oltp_existe"]:
        print(
            f"• Banco Transacional (OLTP): {_colorize('ONLINE', green)} "
            f"({st['total_registros_oltp']} semanas | {st['tamanho_oltp_kb']} KB)"
        )
    else:
        print(f"• Banco Transacional (OLTP): {_colorize('NÃO INICIALIZADO', yellow)}")

    # DW
    if st["dw_existe"]:
        print(
            f"• Data Warehouse (DW):       {_colorize('ONLINE', green)} "
            f"({st['total_registros_dw']} fatos | {st['tamanho_dw_kb']} KB)"
        )
        if st["periodo_min"] and st["periodo_max"]:
            print(f"  Período monitorado:        {st['periodo_min']} a {st['periodo_max']}")
    else:
        print(f"• Data Warehouse (DW):       {_colorize('NÃO INICIALIZADO', yellow)}")

    # CSVs
    if st["csvs_gerados"]:
        print(f"• Datasets Power BI (CSV):   {len(st['csvs_gerados'])} arquivos em {data_dir / 'dw'}")
        for csv_name in sorted(st["csvs_gerados"]):
            print(f"    - {csv_name}")
    else:
        print(f"• Datasets Power BI (CSV):   {_colorize('Nenhum CSV gerado', yellow)}")
    print()


def print_summary(
    data_dir: Path, as_json: bool = False, year: int | None = None, limit: int = 15
) -> None:
    """Exibe um resumo epidemiológico consolidado por ano ou últimas semanas."""
    dw_file = data_dir / "dw_dengue.db"
    if not dw_file.exists():
        print("Data Warehouse não encontrado. Execute o pipeline primeiro: python main.py", file=sys.stderr)
        return

    conn = sqlite3.connect(dw_file)
    conn.row_factory = sqlite3.Row

    if year is not None:
        # Detalhe por semana para o ano solicitado
        query = """
            SELECT 
                t.semana_ano,
                t.data_inicio_semana,
                t.nome_mes,
                f.casos_notificados,
                ROUND(f.casos_estimados, 0) AS casos_est,
                ROUND(f.incidencia_por_100k, 1) AS inc_100k,
                ROUND(f.taxa_rt, 2) AS rt,
                a.status_alerta_nome AS alerta
            FROM fato_casos_dengue f
            JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
            JOIN dim_alerta a ON f.sk_alerta = a.sk_alerta
            WHERE t.ano = ?
            ORDER BY t.sk_tempo DESC
            LIMIT ?
        """
        rows = conn.execute(query, (year, limit)).fetchall()
    else:
        # Resumo agregado por ano
        query = """
            SELECT 
                t.ano,
                COUNT(f.sk_fato) AS semanas,
                SUM(f.casos_notificados) AS total_casos,
                ROUND(SUM(f.casos_estimados), 0) AS total_estimado,
                ROUND(AVG(f.incidencia_por_100k), 1) AS inc_media_100k,
                ROUND(AVG(f.taxa_rt), 2) AS rt_medio,
                ROUND(AVG(f.temp_media_semana), 1) AS temp_med
            FROM fato_casos_dengue f
            JOIN dim_tempo t ON f.sk_tempo = t.sk_tempo
            GROUP BY t.ano
            ORDER BY t.ano DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()

    conn.close()

    dict_rows = [dict(r) for r in rows]

    if as_json:
        print(json.dumps(dict_rows, indent=2, ensure_ascii=False))
        return

    if not dict_rows:
        print("Nenhum registro encontrado para o filtro selecionado.")
        return

    # Renderização em tabela ASCII limpa
    headers = list(dict_rows[0].keys())
    col_widths = {h: max(len(h), max(len(str(r[h])) for r in dict_rows)) for h in headers}

    header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
    sep_line = "-+-".join("-" * col_widths[h] for h in headers)

    print("\n" + header_line)
    print(sep_line)
    for r in dict_rows:
        print(" | ".join(str(r[h]).ljust(col_widths[h]) for h in headers))
    print()


def interactive_tui(data_dir: Path, execute_callback) -> None:
    """TUI / Menu interativo no terminal para operações do sistema."""
    cyan = "36"
    yellow = "33"
    green = "32"
    red = "31"

    while True:
        print("\n" + _colorize("===============================================", cyan))
        print(_colorize("        DATADENGUE - PAINEL DE CONTROLE (CLI/TUI)     ", cyan))
        print(_colorize("===============================================", cyan))
        print(" [1] Executar Carga / Pipeline Completo")
        print(" [2] Carga com Período Personalizado (Anos / Doença)")
        print(" [3] Exibir Status dos Bancos (OLTP & DW)")
        print(" [4] Ver Resumo Epidemiológico Consolidado")
        print(" [5] Abrir Dashboard Streamlit no Navegador")
        print(" [6] Limpar Data Warehouse (Resetar Tabelas DW)")
        print(" [7] Limpar Tudo (DW + Banco Transacional OLTP)")
        print(" [0] Sair")
        print(_colorize("-----------------------------------------------", cyan))

        try:
            choice = input("Selecione uma opção [0-7]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando...")
            break

        if choice == "0":
            print("Até logo!")
            break
        elif choice == "1":
            print("\n" + _colorize("Executando pipeline padrão...", green))
            execute_callback()
        elif choice == "2":
            print("\n" + _colorize("Configuração de Carga Personalizada:", yellow))
            try:
                ano_ini = input("Ano inicial [padrão: 2024]: ").strip() or "2024"
                ano_fim = input("Ano final   [padrão: 2025]: ").strip() or "2025"
                doenca = input("Doença (dengue/chikungunya/zika) [dengue]: ").strip() or "dengue"
                open_ui = input("Abrir Streamlit ao final? (s/N): ").strip().lower() == "s"

                execute_callback(
                    start_year=int(ano_ini),
                    end_year=int(ano_fim),
                    disease=doenca,
                    start_streamlit=open_ui,
                )
            except ValueError:
                print(_colorize("Erro: Ano deve ser um número inteiro válido.", red))
        elif choice == "3":
            print_status(data_dir)
        elif choice == "4":
            ano_filtro = input("Filtrar por ano específico (deixe vazio para resumo anual): ").strip()
            y = int(ano_filtro) if ano_filtro.isdigit() else None
            print_summary(data_dir, year=y)
        elif choice == "5":
            execute_callback(only_streamlit=True)
        elif choice == "6":
            confirm = input(_colorize("Confirma a limpeza do Data Warehouse e CSVs? (s/N): ", yellow)).strip().lower()
            if confirm == "s":
                rem = clean_storage(data_dir, clean_oltp=False)
                print(_colorize(f"Limpeza concluída! Removidos: {', '.join(rem) or 'nenhum'}", green))
            else:
                print("Operação cancelada.")
        elif choice == "7":
            confirm = input(_colorize("ATENÇÃO: Confirma reset TOTAL (OLTP + DW)? (s/N): ", red)).strip().lower()
            if confirm == "s":
                rem = clean_storage(data_dir, clean_oltp=True)
                print(_colorize(f"Reset concluído! Removidos: {', '.join(rem) or 'nenhum'}", green))
            else:
                print("Operação cancelada.")
        else:
            print(_colorize("Opção inválida! Digite um número de 0 a 7.", red))
