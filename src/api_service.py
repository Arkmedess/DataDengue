import io
from pathlib import Path

import httpx
import pandas as pd

from src.models import PolishedDengueRow, RequisitionBody


def get_data_path(file_name: str) -> Path:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    DATA_FOLDER = PROJECT_ROOT / "data"
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    return DATA_FOLDER / file_name


def get_csv(body: RequisitionBody) -> pd.DataFrame:
    with httpx.Client() as client:
        response = client.get(body.url)

        if response.status_code == 200:
            raw = io.StringIO(response.text)
            df = pd.read_csv(raw)
            return df

        else:
            raise Exception(f"Erro na API: {response.status_code} - {response.text}")


def polish_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    raw_records = df_raw.to_dict(orient="records")

    polished_records = [
        PolishedDengueRow.model_validate(row).model_dump(mode="json")
        for row in raw_records
    ]

    df_polished = pd.DataFrame(polished_records)

    if "data_ini_SE" in df_polished.columns:
        df_polished["data_ini_SE"] = pd.to_datetime(df_polished["data_ini_SE"])
        return df_polished.sort_values("data_ini_SE")

    return df_polished


def export_csv(df: pd.DataFrame, file_name: str = "Dengue_Jundiai.csv"):
    FINAL_PATH = get_data_path(file_name)
    df.to_csv(FINAL_PATH, index=False)
    print(f"Arquivo salvo como: {FINAL_PATH}")
