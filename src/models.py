import math
from datetime import date
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

DiseaseType = Literal["dengue", "chikungunya", "zika"]


class RequisitionBody(BaseModel):
    geocode: int = 3525904  # Geocode Jundiaí
    disease: DiseaseType = "dengue"
    format: Literal["json", "csv"] = "csv"
    ew_start: int = Field(default=1, ge=1, le=53)
    ew_end: int = Field(default=53, ge=1, le=53)
    ey_start: int = Field(default=2025, ge=2010, le=2030)
    ey_end: int = Field(default=2025, ge=2010, le=2030)

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    @model_validator(mode="after")
    def auto_correct_ranges(self) -> "RequisitionBody":
        """Previne erros de inversão de datas e semanas de forma defensiva."""
        if self.ey_start > self.ey_end:
            # Troca silenciosamente em vez de quebrar a requisição
            self.ey_start, self.ey_end = self.ey_end, self.ey_start
        if self.ey_start == self.ey_end and self.ew_start > self.ew_end:
            self.ew_start, self.ew_end = self.ew_end, self.ew_start
        return self

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
    data_ini_SE: date = Field(alias="data_iniSE")
    SE: int
    doenca: str = "dengue"
    casos: int = 0
    casos_est: int = Field(default=0, alias="casos_est")
    notif_accum_year: int = 0
    tempmed: Optional[float] = None
    umidmed: Optional[float] = None
    nivel: int = 1

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

    @field_validator("casos", "casos_est", "notif_accum_year", mode="before")
    @classmethod
    def substitute_nans(cls, value):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0
        try:
            return max(0, int(float(value)))
        except (ValueError, TypeError):
            return 0

    @field_validator("tempmed", "umidmed", mode="before")
    @classmethod
    def clean_floats(cls, value):
        if value is None:
            return None
        try:
            f = float(value)
            return None if math.isnan(f) else f
        except (ValueError, TypeError):
            return None

    @field_validator("nivel", mode="before")
    @classmethod
    def clean_nivel(cls, value):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 1
        try:
            n = int(float(value))
            return n if 1 <= n <= 4 else 1
        except (ValueError, TypeError):
            return 1
