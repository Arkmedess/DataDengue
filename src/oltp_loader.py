import math
from pathlib import Path
from typing import Any

import pandas as pd

from src.database import get_db_connection


def _clean_float(val: Any) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _clean_int(val: Any, default: int = 0) -> int:
    if val is None or pd.isna(val):
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else int(f)
    except (ValueError, TypeError):
        return default


def load_oltp_from_raw_df(
    df_raw: pd.DataFrame, db_path: Path | str, geocode: int = 3525904
) -> dict[str, int]:
    """Carga transacional idempotente normalizada em 3FN para o banco OLTP."""
    if df_raw.empty:
        return {"municipios_inseridos": 0, "notificacoes_inseridas": 0}

    conn = get_db_connection(db_path)

    # Coleta metadados do município da primeira linha
    first_row = df_raw.iloc[0]
    nome_mun = str(first_row.get("municipio_nome", "Jundiaí"))
    populacao = _clean_int(first_row.get("pop", 459789), default=459789)

    with conn:
        # 1. Município (Idempotente)
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

        # 2. Unidades Notificadoras de Exemplo (se não existirem)
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

        # 3. Inserção em Lote nas Tabelas Transacionais
        notificacoes_rows = []
        clima_rows = []
        alerta_rows = []

        for _, row in df_raw.iterrows():
            data_ini = str(row["data_iniSE"])
            se_val = _clean_int(row["SE"])
            se_str = str(se_val)
            ano_epidem = int(se_str[:4]) if len(se_str) >= 6 else 2025
            semana_epidem = int(se_str[-2:]) if len(se_str) >= 6 else se_val

            casos = _clean_int(row.get("casos", 0))
            casos_est = _clean_float(row.get("casos_est", casos)) or float(casos)
            casconf = _clean_int(row.get("casconf", 0))
            casprov = _clean_int(row.get("casprov", 0))

            temp_min = _clean_float(row.get("tempmin"))
            temp_med = _clean_float(row.get("tempmed"))
            temp_max = _clean_float(row.get("tempmax"))
            umid_min = _clean_float(row.get("umidmin"))
            umid_med = _clean_float(row.get("umidmed"))
            umid_max = _clean_float(row.get("umidmax"))
            receptivo = _clean_int(row.get("receptivo", 0))

            nivel_alerta = _clean_int(row.get("nivel", 1), default=1)
            rt = _clean_float(row.get("Rt"))
            p_rt1 = _clean_float(row.get("p_rt1"))
            inc100k = _clean_float(row.get("p_inc100k")) or 0.0
            transmissao = _clean_int(row.get("transmissao", 0))
            notif_accum = _clean_int(row.get("notif_accum_year", 0))

            notificacoes_rows.append(
                (
                    geocode,
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

            clima_rows.append(
                (
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
            )

            alerta_rows.append(
                (
                    geocode,
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

        # Execução das inserções/atualizações idempotentes
        conn.executemany(
            """
            INSERT INTO tb_notificacao_dengue (
                id_municipio, data_inicio_semana, semana_ano, semana_epidem, ano_epidem,
                casos_notificados, casos_estimados, casos_confirmados, casos_provaveis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_municipio, semana_ano) DO UPDATE SET
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
            clima_rows,
        )

        conn.executemany(
            """
            INSERT INTO tb_alerta_epidemiologico (
                id_municipio, data_inicio_semana, semana_ano,
                nivel_alerta, rt, p_rt1, incidencia_100k, transmissao_sustentada, notif_acumuladas_ano
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_municipio, semana_ano) DO UPDATE SET
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
    }
