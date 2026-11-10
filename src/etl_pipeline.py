from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.database import get_db_connection


def _determinar_estacao(mes: int) -> str:
    if mes in (12, 1, 2):
        return "Verão"
    elif mes in (3, 4, 5):
        return "Outono"
    elif mes in (6, 7, 8):
        return "Inverno"
    else:
        return "Primavera"


def _determinar_faixa_temp(temp: float | None) -> str:
    if temp is None:
        return "Não Informada"
    if temp < 18.0:
        return "Fria (<18°C)"
    elif temp < 24.0:
        return "Agradável (18-24°C)"
    elif temp < 28.0:
        return "Favorável ao Vetor (24-28°C)"
    else:
        return "Alta (>28°C)"


def _determinar_faixa_umid(umid: float | None) -> str:
    if umid is None:
        return "Não Informada"
    if umid < 60.0:
        return "Baixa (<60%)"
    elif umid <= 80.0:
        return "Ideal ao Vetor (60-80%)"
    else:
        return "Muito Alta (>80%)"


def _determinar_risco_climatico(temp: float | None, umid: float | None) -> tuple[str, str]:
    if temp is None or umid is None:
        return "Desfavorável", "Baixo"

    # Aedes aegypti prolifera com temperatura entre 22°C e 30°C e umidade acima de 60%
    if temp >= 22.0 and umid >= 60.0:
        return "Surto Sustentado", "Crítico"
    elif temp >= 20.0 and umid >= 50.0:
        return "Transmissão Inicial", "Moderado"
    else:
        return "Desfavorável", "Baixo"


def run_etl(
    oltp_db_path: Path | str,
    dw_db_path: Path | str,
    export_csv_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Executa o pipeline ETL extraindo do OLTP e carregando no Star Schema."""
    oltp_conn = get_db_connection(oltp_db_path)

    # 1. Extração das tabelas do OLTP
    df_mun = pd.read_sql_query("SELECT * FROM tb_municipio", oltp_conn)
    df_notif = pd.read_sql_query("SELECT * FROM tb_notificacao_dengue", oltp_conn)
    df_clima = pd.read_sql_query("SELECT * FROM tb_monitoramento_climatico", oltp_conn)
    df_alerta = pd.read_sql_query("SELECT * FROM tb_alerta_epidemiologico", oltp_conn)
    oltp_conn.close()

    if df_notif.empty:
        return {"fatos_carregados": 0, "dimensoes_carregadas": {}}

    # Mescla os dados do OLTP pela chave natural (id_municipio, semana_ano)
    df_base = df_notif.merge(
        df_clima, on=["id_municipio", "semana_ano"], suffixes=("", "_clima")
    ).merge(
        df_alerta, on=["id_municipio", "semana_ano"], suffixes=("", "_alerta")
    )

    dw_conn = get_db_connection(dw_db_path)

    # 2. Carga da Dimensão Município
    dim_municipio_records = []
    for _, row in df_mun.iterrows():
        pop = int(row["populacao"])
        faixa = "Médio-Grande Porte (100k a 500k)" if pop < 500000 else "Metrópole (>500k)"
        dim_municipio_records.append(
            {
                "sk_municipio": int(row["id_municipio"]),
                "geocode": int(row["id_municipio"]),
                "nome_municipio": str(row["nome_municipio"]),
                "uf": str(row["uf"]),
                "populacao": pop,
                "faixa_populacional": faixa,
            }
        )
    df_dim_municipio = pd.DataFrame(dim_municipio_records)

    # 3. Carga da Dimensão Nível de Alerta (Padrão Infodengue)
    df_dim_alerta = pd.DataFrame(
        [
            {
                "sk_alerta": 1,
                "nivel_alerta": 1,
                "status_alerta_nome": "Verde",
                "cor_indicativa": "#2CA02C",
                "descricao_risco": "Baixo Risco - Condições climáticas e incidência dentro da normalidade.",
                "acao_preventiva_recomendada": "Monitoramento epidemiológico regular e ações de rotina.",
            },
            {
                "sk_alerta": 2,
                "nivel_alerta": 2,
                "status_alerta_nome": "Amarelo",
                "cor_indicativa": "#FFD700",
                "descricao_risco": "Atenção - Condições climáticas favoráveis à proliferação vetorial.",
                "acao_preventiva_recomendada": "Intensificação de vistorias residenciais e eliminação de criadouros.",
            },
            {
                "sk_alerta": 3,
                "nivel_alerta": 3,
                "status_alerta_nome": "Laranja",
                "cor_indicativa": "#FFA500",
                "descricao_risco": "Alerta de Transmissão - Ritmo de contágio acelerado (Rt > 1 persistente).",
                "acao_preventiva_recomendada": "Mobilização de agentes comunitários, nebulização focal e alerta às UBSs.",
            },
            {
                "sk_alerta": 4,
                "nivel_alerta": 4,
                "status_alerta_nome": "Vermelho",
                "cor_indicativa": "#FF4B4B",
                "descricao_risco": "Emergência Epidêmica - Alta taxa de incidência com sobrecarga no sistema de saúde.",
                "acao_preventiva_recomendada": "Abertura de polos de hidratação, fumacê veicular e ampliação de leitos.",
            },
        ]
    )

    # 4. Carga da Dimensão Clima
    # Mapeamos combinações únicas de faixas observadas
    clima_combos = {}
    clima_records = []
    sk_clima_counter = 1

    for _, row in df_base.iterrows():
        temp = row["temp_med"]
        umid = row["umid_med"]
        faixa_t = _determinar_faixa_temp(temp)
        faixa_u = _determinar_faixa_umid(umid)
        recept, risco = _determinar_risco_climatico(temp, umid)

        combo_key = (faixa_t, faixa_u, recept, risco)
        if combo_key not in clima_combos:
            clima_combos[combo_key] = sk_clima_counter
            clima_records.append(
                {
                    "sk_clima": sk_clima_counter,
                    "faixa_temperatura": faixa_t,
                    "faixa_umidade": faixa_u,
                    "condicao_receptividade": recept,
                    "risco_clima_proliferacao": risco,
                }
            )
            sk_clima_counter += 1

    df_dim_clima = pd.DataFrame(clima_records)

    # 5. Carga da Dimensão Tempo e Tabela Fato
    dim_tempo_dict = {}
    fato_records = []

    for _, row in df_base.iterrows():
        data_str = str(row["data_inicio_semana"])
        dt = datetime.strptime(data_str[:10], "%Y-%m-%d")
        sk_tempo = int(dt.strftime("%Y%m%d"))

        if sk_tempo not in dim_tempo_dict:
            se_val = int(row["semana_ano"])
            se_str = str(se_val)
            semana_epidem = int(se_str[-2:]) if len(se_str) >= 6 else se_val
            ano_epidem = int(se_str[:4]) if len(se_str) >= 6 else dt.year

            nomes_meses = [
                "",
                "Janeiro",
                "Fevereiro",
                "Março",
                "Abril",
                "Maio",
                "Junho",
                "Julho",
                "Agosto",
                "Setembro",
                "Outubro",
                "Novembro",
                "Dezembro",
            ]
            dim_tempo_dict[sk_tempo] = {
                "sk_tempo": sk_tempo,
                "data_inicio_semana": dt.strftime("%Y-%m-%d"),
                "semana_epidem": semana_epidem,
                "ano_epidem": ano_epidem,
                "semana_ano": se_val,
                "mes": dt.month,
                "nome_mes": nomes_meses[dt.month],
                "ano": dt.year,
                "trimestre": (dt.month - 1) // 3 + 1,
                "ano_mes": dt.strftime("%Y-%m"),
                "quinzena": 1 if dt.day <= 15 else 2,
                "estacao_ano": _determinar_estacao(dt.month),
            }

        # Identifica chaves estrangeiras
        sk_mun = int(row["id_municipio"])
        sk_al = int(row["nivel_alerta"]) if 1 <= int(row["nivel_alerta"]) <= 4 else 1

        temp = row["temp_med"]
        umid = row["umid_med"]
        faixa_t = _determinar_faixa_temp(temp)
        faixa_u = _determinar_faixa_umid(umid)
        recept, risco = _determinar_risco_climatico(temp, umid)
        sk_cl = clima_combos.get((faixa_t, faixa_u, recept, risco), 1)

        casos_notif = int(row["casos_notificados"])
        casos_est = float(row["casos_estimados"])
        diff_nowcast = round(casos_est - casos_notif, 2)

        fato_records.append(
            {
                "sk_tempo": sk_tempo,
                "sk_municipio": sk_mun,
                "sk_alerta": sk_al,
                "sk_clima": sk_cl,
                "casos_notificados": casos_notif,
                "casos_estimados": casos_est,
                "diferenca_nowcasting": diff_nowcast,
                "casos_confirmados": int(row.get("casos_confirmados", 0)),
                "casos_provaveis": int(row.get("casos_provaveis", 0)),
                "incidencia_por_100k": float(row.get("incidencia_100k", 0.0) or 0.0),
                "taxa_rt": float(row["rt"]) if pd.notna(row["rt"]) else None,
                "probabilidade_rt_maior_1": (
                    float(row["p_rt1"]) if pd.notna(row["p_rt1"]) else None
                ),
                "temp_media_semana": float(temp) if pd.notna(temp) else None,
                "umid_media_semana": float(umid) if pd.notna(umid) else None,
                "notif_acumuladas_ano": int(row.get("notif_acumuladas_ano", 0)),
            }
        )

    df_dim_tempo = pd.DataFrame(list(dim_tempo_dict.values()))
    df_fato = pd.DataFrame(fato_records)

    # 6. Gravação idempotente no banco analítico (DW)
    with dw_conn:
        dw_conn.execute("DELETE FROM fato_casos_dengue;")
        dw_conn.execute("DELETE FROM dim_tempo;")
        dw_conn.execute("DELETE FROM dim_municipio;")
        dw_conn.execute("DELETE FROM dim_alerta;")
        dw_conn.execute("DELETE FROM dim_clima;")

        df_dim_municipio.to_sql("dim_municipio", dw_conn, if_exists="append", index=False)
        df_dim_alerta.to_sql("dim_alerta", dw_conn, if_exists="append", index=False)
        df_dim_clima.to_sql("dim_clima", dw_conn, if_exists="append", index=False)
        df_dim_tempo.to_sql("dim_tempo", dw_conn, if_exists="append", index=False)
        df_fato.to_sql("fato_casos_dengue", dw_conn, if_exists="append", index=False)

    dw_conn.close()

    # 7. Exportação de CSVs prontos para o Power BI
    if export_csv_dir is not None:
        p_dir = Path(export_csv_dir)
        p_dir.mkdir(parents=True, exist_ok=True)

        df_dim_tempo.to_csv(p_dir / "dim_tempo.csv", index=False, encoding="utf-8-sig")
        df_dim_municipio.to_csv(p_dir / "dim_municipio.csv", index=False, encoding="utf-8-sig")
        df_dim_alerta.to_csv(p_dir / "dim_alerta.csv", index=False, encoding="utf-8-sig")
        df_dim_clima.to_csv(p_dir / "dim_clima.csv", index=False, encoding="utf-8-sig")
        df_fato.to_csv(p_dir / "fato_casos_dengue.csv", index=False, encoding="utf-8-sig")

    return {
        "fatos_carregados": len(df_fato),
        "dimensoes_carregadas": {
            "dim_municipio": len(df_dim_municipio),
            "dim_alerta": len(df_dim_alerta),
            "dim_clima": len(df_dim_clima),
            "dim_tempo": len(df_dim_tempo),
        },
    }
