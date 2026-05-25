from src.api_service import export_csv, get_csv
from src.models import RequisitionBody

if __name__ == "__main__":
    csv_api = RequisitionBody()

    try:
        print("Buscando dados na API...")
        dataframe = get_csv(csv_api)
        export_csv(dataframe, file_name="Dengue_Jundiai.csv")

    except Exception as e:
        print(f"Ocorreu um problema: {e}")
