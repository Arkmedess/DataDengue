from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


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


class PolishedDengueRow(BaseModel):
    data_ini_Se: date = Field(alias="data_iniSE")
    casos: int = 0
    casos_est: int = Field(default=0, alias="casos_est")
    notif_accum_year: int = 0
    tempmed: Optional[float] = None
    umidmed: Optional[float] = None
    nivel: int

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    @computed_field
    @property
    def alerta_status(self) -> str:
        map_warns = {
            1: "🟢 Verde",
            2: "🟡 Amarelo",
            3: "🟠 Laranja",
            4: "🔴 Vermelho",
        }
        return map_warns.get(self.nivel, "⚪ Desconhecido")

    # Validador para garantir que valores nulos (NaN) viram 0 nos casos
    @field_validator("casos", "casos_est", mode="before")
    @classmethod
    def substitute_nans(cls, value):
        import math

        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0
        return int(value)
