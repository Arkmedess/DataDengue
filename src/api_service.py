import io
import logging
import time
from pathlib import Path
from typing import Sequence

import httpx
import pandas as pd

from src.models import DiseaseType, PolishedDengueRow, RequisitionBody

logger = logging.getLogger(__name__)


def get_data_path(file_name: str) -> Path:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    DATA_FOLDER = PROJECT_ROOT / "data"
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    return DATA_FOLDER / file_name


def get_csv(body: RequisitionBody, max_retries: int = 3, timeout_seconds: float = 30.0) -> pd.DataFrame:
    """Busca dados na API InfoDengue com retry automático e tratamento de indisponibilidade."""
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(body.url)

                if response.status_code == 200:
                    text = response.text.strip()
                    if not text or len(text.splitlines()) <= 1:
                        # Resposta vazia ou apenas cabeçalho (comum quando não há casos daquela doença)
                        return pd.DataFrame()

                    raw = io.StringIO(text)
                    df = pd.read_csv(raw)
                    # Adiciona a tag explícita da doença
                    df["doenca"] = body.disease
                    return df
                elif response.status_code in (429, 500, 502, 503, 504):
                    # Erros transientes de servidor ou rate limit: espera com backoff
                    wait_time = 2 ** (attempt - 1)
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"Erro na API InfoDengue: HTTP {response.status_code} - {response.text[:200]}")

        except httpx.RequestError as exc:
            last_exception = exc
            wait_time = 2 ** (attempt - 1)
            time.sleep(wait_time)

    if last_exception:
        raise RuntimeError(f"Falha de conexão com a API após {max_retries} tentativas: {last_exception}")

    return pd.DataFrame()


def fetch_multiple_diseases(
    diseases: Sequence[DiseaseType],
    geocode: int = 3525904,
    start_year: int = 2025,
    end_year: int = 2025,
    ew_start: int = 1,
    ew_end: int = 53,
) -> pd.DataFrame:
    """Coleta dados para uma lista de doenças (ex: Dengue, Chikungunya, Zika) e unifica em um DataFrame."""
    collected_dfs: list[pd.DataFrame] = []

    for disease in diseases:
        body = RequisitionBody(
            geocode=geocode,
            disease=disease,
            ey_start=start_year,
            ey_end=end_year,
            ew_start=ew_start,
            ew_end=ew_end,
        )
        try:
            df_disease = get_csv(body)
            if not df_disease.empty:
                collected_dfs.append(df_disease)
            else:
                logger.warning("Nenhum registro retornado para '%s' no período selecionado.", disease)
        except Exception as e:
            logger.error("Falha ao coletar '%s': %s. Continuando com as demais...", disease, e)

    if not collected_dfs:
        return pd.DataFrame()

    return pd.concat(collected_dfs, ignore_index=True)


def polish_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Higieniza os registros brutos convertendo NaNs e tipagens defensivas."""
    if df_raw.empty:
        return pd.DataFrame()

    raw_records = df_raw.to_dict(orient="records")

    polished_records = []
    for row in raw_records:
        try:
            # Preserva ou adiciona a doença na linha
            doenca = str(row.get("doenca", "dengue"))
            p_row = PolishedDengueRow.model_validate(row)
            d = p_row.model_dump(mode="json")
            d["doenca"] = doenca
            polished_records.append(d)
        except Exception:
            # Ignora linha corrompida (poison pill) sem abortar as demais
            continue

    if not polished_records:
        return pd.DataFrame()

    df_polished = pd.DataFrame(polished_records)

    if "data_ini_SE" in df_polished.columns:
        df_polished["data_ini_SE"] = pd.to_datetime(df_polished["data_ini_SE"])
        return df_polished.sort_values(["data_ini_SE", "doenca"])

    return df_polished


def export_csv(df: pd.DataFrame, file_name: str = "Dengue_Jundiai.csv"):
    FINAL_PATH = get_data_path(file_name)
    df.to_csv(FINAL_PATH, index=False)
    logger.info("Arquivo salvo como: %s", FINAL_PATH)
