import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.database import get_db_connection


def _clean_float(val: Any) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None


def _clean_int(val: Any, default: int = 0) -> int:
    if val is None or pd.isna(val):
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return max(0, int(f))
    except (ValueError, TypeError):
        return default


def _clean_date_str(val: Any) -> str | None:
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    try:
        # Tenta interpretar data YYYY-MM-DD
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def load_oltp_from_raw_df(
    df_raw: pd.DataFrame, db_path: Path | str, geocode: int = 3525904
) -> dict[str, int]:
    """Carga transacional resiliente e idempotente normalizada em 3FN para o banco OLTP."""
    if df_raw.empty:
        return {"municipios_inseridos": 0, "notificacoes_inseridas": 0, "erros_ignorados": 0}

    conn = get_db_connection(db_path)

    # Identifica nome do município e população de forma defensiva
    first_row = df_raw.iloc[0]
    nome_mun = str(first_row.get("municipio_nome", "Jundiaí")) if pd.notna(first_row.get("municipio_nome")) else "Jundiaí"
    populacao = _clean_int(first_row.get("pop", 459789), default=459789)

    erros_ignorados = 0
    notificacoes_rows = []
    clima_rows_dict: dict[tuple[int, int], tuple] = {}
    alerta_rows = []

    for _, row in df_raw.iterrows():
        try:
            data_ini = _clean_date_str(row.get("data_iniSE"))
            if not data_ini:
                erros_ignorados += 1
                continue

            se_val = _clean_int(row.get("SE"))
            if se_val == 0:
                erros_ignorados += 1
                continue

            se_str = str(se_val)
            ano_epidem = int(se_str[:4]) if len(se_str) >= 6 else int(data_ini[:4])
            semana_epidem = int(se_str[-2:]) if len(se_str) >= 6 else 1
            doenca = str(row.get("doenca", "dengue")).strip().lower()

            casos = _clean_int(row.get("casos", 0))
            casos_est = _clean_float(row.get("casos_est", casos))
            if casos_est is None or casos_est < 0:
                casos_est = float(casos)
            casconf = _clean_int(row.get("casconf", 0))
            casprov = _clean_int(row.get("casprov", 0))

            temp_min = _clean_float(row.get("tempmin"))
            temp_med = _clean_float(row.get("tempmed"))
            temp_max = _clean_float(row.get("tempmax"))
            umid_min = _clean_float(row.get("umidmin"))
            umid_med = _clean_float(row.get("umidmed"))
            umid_max = _clean_float(row.get("umidmax"))
            receptivo = _clean_int(row.get("receptivo", 0))

            nivel_raw = _clean_int(row.get("nivel", 1), default=1)
            nivel_alerta = nivel_raw if 1 <= nivel_raw <= 4 else 1

            rt = _clean_float(row.get("Rt"))
            p_rt1 = _clean_float(row.get("p_rt1"))
            inc100k = _clean_float(row.get("p_inc100k")) or 0.0
            transmissao = _clean_int(row.get("transmissao", 0))
            notif_accum = _clean_int(row.get("notif_accum_year", 0))

            notificacoes_rows.append(
                (
                    geocode,
                    doenca,
                    data_ini,
                    se_val,
                    semana_epidem,
                    ano_epidem,
                    casos,
                    casos_est,
                    casconf,
                    casprov,
                )
            )

            # Clima é único por município e semana_ano (desduplica entre doenças)
            clima_key = (geocode, se_val)
            if clima_key not in clima_rows_dict:
                clima_rows_dict[clima_key] = (
                    geocode,
                    data_ini,
                    se_val,
                    temp_min,
                    temp_med,
                    temp_max,
                    umid_min,
                    umid_med,
                    umid_max,
                    receptivo,
                )

            alerta_rows.append(
                (
                    geocode,
                    doenca,
                    data_ini,
                    se_val,
                    nivel_alerta,
                    rt,
                    p_rt1,
                    inc100k,
                    transmissao,
                    notif_accum,
                )
            )

        except Exception:
            erros_ignorados += 1
            continue

    with conn:
        # 1. Município
        conn.execute(
            """
            INSERT INTO tb_municipio (id_municipio, nome_municipio, uf, populacao)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id_municipio) DO UPDATE SET
                nome_municipio = excluded.nome_municipio,
                populacao = excluded.populacao;
            """,
            (geocode, nome_mun, "SP", populacao),
        )

        # 2. Unidades Notificadoras (se não existirem)
        cur = conn.execute(
            "SELECT COUNT(*) FROM tb_unidade_notificadora WHERE id_municipio = ?",
            (geocode,),
        )
        if cur.fetchone()[0] == 0:
            unidades_iniciais = [
                (geocode, "Vigilância Epidemiológica Central", "Vigilância", "Centro"),
                (geocode, "Hospital São Vicente de Paulo", "Hospital", "Centro"),
                (geocode, "UPA Novo Horizonte", "Pronto Atendimento", "Novo Horizonte"),
                (geocode, "UBS Vila Hortolândia", "Unidade Básica", "Vila Hortolândia"),
            ]
            conn.executemany(
                """
                INSERT INTO tb_unidade_notificadora (id_municipio, nome_unidade, tipo_unidade, bairro)
                VALUES (?, ?, ?, ?);
                """,
                unidades_iniciais,
            )

        # 3. Inserções transacionais idempotentes com ON CONFLICT
        conn.executemany(
            """
            INSERT INTO tb_notificacao_dengue (
                id_municipio, doenca, data_inicio_semana, semana_ano, semana_epidem, ano_epidem,
                casos_notificados, casos_estimados, casos_confirmados, casos_provaveis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_municipio, semana_ano, doenca) DO UPDATE SET
                casos_notificados = excluded.casos_notificados,
                casos_estimados = excluded.casos_estimados,
                casos_confirmados = excluded.casos_confirmados,
                casos_provaveis = excluded.casos_provaveis;
            """,
            notificacoes_rows,
        )

        conn.executemany(
            """
            INSERT INTO tb_monitoramento_climatico (
                id_municipio, data_inicio_semana, semana_ano,
                temp_min, temp_med, temp_max, umid_min, umid_med, umid_max, receptivo_ambiental
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_municipio, semana_ano) DO UPDATE SET
                temp_min = excluded.temp_min,
                temp_med = excluded.temp_med,
                temp_max = excluded.temp_max,
                umid_min = excluded.umid_min,
                umid_med = excluded.umid_med,
                umid_max = excluded.umid_max,
                receptivo_ambiental = excluded.receptivo_ambiental;
            """,
            list(clima_rows_dict.values()),
        )

        conn.executemany(
            """
            INSERT INTO tb_alerta_epidemiologico (
                id_municipio, doenca, data_inicio_semana, semana_ano,
                nivel_alerta, rt, p_rt1, incidencia_100k, transmissao_sustentada, notif_acumuladas_ano
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_municipio, semana_ano, doenca) DO UPDATE SET
                nivel_alerta = excluded.nivel_alerta,
                rt = excluded.rt,
                p_rt1 = excluded.p_rt1,
                incidencia_100k = excluded.incidencia_100k,
                transmissao_sustentada = excluded.transmissao_sustentada,
                notif_acumuladas_ano = excluded.notif_acumuladas_ano;
            """,
            alerta_rows,
        )

    conn.close()

    return {
        "municipios_inseridos": 1,
        "notificacoes_inseridas": len(notificacoes_rows),
        "erros_ignorados": erros_ignorados,
    }
