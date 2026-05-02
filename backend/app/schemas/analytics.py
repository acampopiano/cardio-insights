from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.kpis import QueryFilter


class AnalyticsQueryRequest(BaseModel):
    widget_type: Literal["table", "ranking"] = Field(
        description="Tipo de visualizacion enriquecida",
    )
    metric_key: str = Field(
        default="surgery_volume",
        description="Metrica para ranking (surgery_volume, ptca_volume, mortality_egreso_pct)",
    )
    filters: list[QueryFilter] = Field(default_factory=list)
    granularity: str = Field(default="month", examples=["day", "week", "month"])
    limit: int = Field(default=10, ge=1, le=100)


class AnalyticsColumn(BaseModel):
    key: str
    label: str


class AnalyticsQueryResponse(BaseModel):
    widget_type: str
    title: str
    columns: list[AnalyticsColumn]
    rows: list[dict[str, Any]]
    meta: dict[str, Any] = Field(default_factory=dict)
