import math
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import Engine, text

from src.database import get_engine


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
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def load_oltp_from_raw_df(
    df_raw: pd.DataFrame, engine: Engine | None = None, geocode: int = 3525904
) -> dict[str, int]:
    """Carga transacional resiliente e idempotente normalizada em 3FN no PostgreSQL (schema oltp)."""
    if df_raw.empty:
        return {"municipios_inseridos": 0, "notificacoes_inseridas": 0, "erros_ignorados": 0}

    eng = engine or get_engine()

    first_row = df_raw.iloc[0]
    nome_mun = str(first_row.get("municipio_nome", "Jundiaí")) if pd.notna(first_row.get("municipio_nome")) else "Jundiaí"
    populacao = _clean_int(first_row.get("pop", 459789), default=459789)

    erros_ignorados = 0
    notificacoes_rows: list[dict[str, Any]] = []
    clima_rows_dict: dict[tuple[int, int], dict[str, Any]] = {}
    alerta_rows: list[dict[str, Any]] = []

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
                {
                    "id_municipio": geocode,
                    "doenca": doenca,
                    "data_inicio_semana": data_ini,
                    "semana_ano": se_val,
                    "semana_epidem": semana_epidem,
                    "ano_epidem": ano_epidem,
                    "casos_notificados": casos,
                    "casos_estimados": casos_est,
                    "casos_confirmados": casconf,
                    "casos_provaveis": casprov,
                }
            )

            clima_key = (geocode, se_val)
            if clima_key not in clima_rows_dict:
                clima_rows_dict[clima_key] = {
                    "id_municipio": geocode,
                    "data_inicio_semana": data_ini,
                    "semana_ano": se_val,
                    "temp_min": temp_min,
                    "temp_med": temp_med,
                    "temp_max": temp_max,
                    "umid_min": umid_min,
                    "umid_med": umid_med,
                    "umid_max": umid_max,
                    "receptivo_ambiental": receptivo,
                }

            alerta_rows.append(
                {
                    "id_municipio": geocode,
                    "doenca": doenca,
                    "data_inicio_semana": data_ini,
                    "semana_ano": se_val,
                    "nivel_alerta": nivel_alerta,
                    "rt": rt,
                    "p_rt1": p_rt1,
                    "incidencia_100k": inc100k,
                    "transmissao_sustentada": transmissao,
                    "notif_acumuladas_ano": notif_accum,
                }
            )

        except Exception:
            erros_ignorados += 1
            continue

    with eng.begin() as conn:
        # 1. Município
        conn.execute(
            text(
                """
                INSERT INTO oltp.tb_municipio (id_municipio, nome_municipio, uf, populacao)
                VALUES (:id_municipio, :nome_municipio, :uf, :populacao)
                ON CONFLICT (id_municipio) DO UPDATE SET
                    nome_municipio = EXCLUDED.nome_municipio,
                    populacao = EXCLUDED.populacao;
                """
            ),
            {"id_municipio": geocode, "nome_municipio": nome_mun, "uf": "SP", "populacao": populacao},
        )

        # 2. Unidades Notificadoras (se não existirem)
        res = conn.execute(
            text("SELECT COUNT(*) FROM oltp.tb_unidade_notificadora WHERE id_municipio = :id_mun"),
            {"id_mun": geocode},
        )
        if res.scalar() == 0:
            unidades_iniciais = [
                {"id_municipio": geocode, "nome_unidade": "Vigilância Epidemiológica Central", "tipo_unidade": "Vigilância", "bairro": "Centro"},
                {"id_municipio": geocode, "nome_unidade": "Hospital São Vicente de Paulo", "tipo_unidade": "Hospital", "bairro": "Centro"},
                {"id_municipio": geocode, "nome_unidade": "UPA Novo Horizonte", "tipo_unidade": "Pronto Atendimento", "bairro": "Novo Horizonte"},
                {"id_municipio": geocode, "nome_unidade": "UBS Vila Hortolândia", "tipo_unidade": "Unidade Básica", "bairro": "Vila Hortolândia"},
            ]
            conn.execute(
                text(
                    """
                    INSERT INTO oltp.tb_unidade_notificadora (id_municipio, nome_unidade, tipo_unidade, bairro)
                    VALUES (:id_municipio, :nome_unidade, :tipo_unidade, :bairro);
                    """
                ),
                unidades_iniciais,
            )

        # 3. Notificações
        if notificacoes_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO oltp.tb_notificacao_dengue (
                        id_municipio, doenca, data_inicio_semana, semana_ano, semana_epidem, ano_epidem,
                        casos_notificados, casos_estimados, casos_confirmados, casos_provaveis
                    ) VALUES (
                        :id_municipio, :doenca, :data_inicio_semana, :semana_ano, :semana_epidem, :ano_epidem,
                        :casos_notificados, :casos_estimados, :casos_confirmados, :casos_provaveis
                    ) ON CONFLICT (id_municipio, semana_ano, doenca) DO UPDATE SET
                        casos_notificados = EXCLUDED.casos_notificados,
                        casos_estimados = EXCLUDED.casos_estimados,
                        casos_confirmados = EXCLUDED.casos_confirmados,
                        casos_provaveis = EXCLUDED.casos_provaveis;
                    """
                ),
                notificacoes_rows,
            )

        # 4. Monitoramento Climático
        if clima_rows_dict:
            conn.execute(
                text(
                    """
                    INSERT INTO oltp.tb_monitoramento_climatico (
                        id_municipio, data_inicio_semana, semana_ano,
                        temp_min, temp_med, temp_max, umid_min, umid_med, umid_max, receptivo_ambiental
                    ) VALUES (
                        :id_municipio, :data_inicio_semana, :semana_ano,
                        :temp_min, :temp_med, :temp_max, :umid_min, :umid_med, :umid_max, :receptivo_ambiental
                    ) ON CONFLICT (id_municipio, semana_ano) DO UPDATE SET
                        temp_min = EXCLUDED.temp_min,
                        temp_med = EXCLUDED.temp_med,
                        temp_max = EXCLUDED.temp_max,
                        umid_min = EXCLUDED.umid_min,
                        umid_med = EXCLUDED.umid_med,
                        umid_max = EXCLUDED.umid_max,
                        receptivo_ambiental = EXCLUDED.receptivo_ambiental;
                    """
                ),
                list(clima_rows_dict.values()),
            )

        # 5. Alerta Epidemiológico
        if alerta_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO oltp.tb_alerta_epidemiologico (
                        id_municipio, doenca, data_inicio_semana, semana_ano,
                        nivel_alerta, rt, p_rt1, incidencia_100k, transmissao_sustentada, notif_acumuladas_ano
                    ) VALUES (
                        :id_municipio, :doenca, :data_inicio_semana, :semana_ano,
                        :nivel_alerta, :rt, :p_rt1, :incidencia_100k, :transmissao_sustentada, :notif_acumuladas_ano
                    ) ON CONFLICT (id_municipio, semana_ano, doenca) DO UPDATE SET
                        nivel_alerta = EXCLUDED.nivel_alerta,
                        rt = EXCLUDED.rt,
                        p_rt1 = EXCLUDED.p_rt1,
                        incidencia_100k = EXCLUDED.incidencia_100k,
                        transmissao_sustentada = EXCLUDED.transmissao_sustentada,
                        notif_acumuladas_ano = EXCLUDED.notif_acumuladas_ano;
                    """
                ),
                alerta_rows,
            )

    return {
        "municipios_inseridos": 1,
        "notificacoes_inseridas": len(notificacoes_rows),
        "erros_ignorados": erros_ignorados,
    }
