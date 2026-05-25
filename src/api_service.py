import io
from pathlib import Path

import httpx
import pandas as pd

from src.models import RequisitionBody


def get_csv(body: RequisitionBody) -> pd.DataFrame:
    with httpx.Client() as client:
        response = client.get(body.url)

        if response.status_code == 200:
            raw = io.StringIO(response.text)
            df = pd.read_csv(raw)
            return df

        else:
            raise Exception(f"Erro na API: {response.status_code} - {response.text}")


def export_csv(df_raw: pd.DataFrame, file_name: str = "Dengue_Jundiai.csv"):
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    DATA_FOLDER = PROJECT_ROOT / "data"
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    FINAL_PATH = DATA_FOLDER / file_name
    df_raw.to_csv(FINAL_PATH, index=False)
    print(f"Arquivo salvo como: {FINAL_PATH}")
