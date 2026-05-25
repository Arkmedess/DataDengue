from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RequisitionBody(BaseModel):
    geocode: int = 3525904  # Geocode Jundiaí
    disease: Literal["dengue", "chikungunya", "zika"] = "dengue"
    format: Literal["json", "csv"] = "csv"
    ew_start: int = Field(default=1, gt=0, lt=54)  # int 1-53
    ew_end: int = Field(default=53, gt=0, lt=54)
    ey_start: int = Field(default=2025, ge=0, lt=10000)  # int 0-9999
    ey_end: int = Field(default=2025, ge=0, lt=10000)

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    @computed_field
    @property
    def url(self) -> str:
        return (
            f"https://info.dengue.mat.br/api/alertcity?"
            f"geocode={self.geocode}&disease={self.disease}&format={self.format}&"
            f"ew_start={self.ew_start}&ew_end={self.ew_end}&"
            f"ey_start={self.ey_start}&ey_end={self.ey_end}"
        )


# dados_teste = RequisitionBody()
# print(dados_teste.url)
