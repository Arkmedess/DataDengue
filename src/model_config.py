from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class RequisitionBody(BaseModel):
    geocode: int
    disease: Literal["dengue", "chikungunya", "zika"]
    format: Literal["json", "csv"]
    ew_start: int = Field(gt=0, lt=54)  # int 1-53
    ew_end: int = Field(gt=0, lt=54)
    ey_start: int = Field(ge=0, lt=10000)  # int 0-9999
    ey_end: int = Field(ge=0, lt=10000)
    url: AnyHttpUrl

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)
