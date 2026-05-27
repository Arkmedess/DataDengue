from src.api_service import export_csv, get_csv, polish_data
from src.models import RequisitionBody

if __name__ == "__main__":
    csv_api = RequisitionBody()

    try:
        print("Buscando dados na API...")
        df_raw = get_csv(csv_api)

        df_polish = polish_data(df_raw)

        export_csv(df_polish, file_name="Dengue_Jundiai.csv")

    except Exception as e:
        print(f"Ocorreu um problema: {e}")
