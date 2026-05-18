from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.kpis import QueryFilter


class AnalyticsQueryRequest(BaseModel):
    widget_type: Literal["table", "ranking", "cube"] = Field(
        description="Tipo de visualizacion enriquecida",
    )
    metric_key: str = Field(
        default="surgery_volume",
        description="Metrica para ranking (surgery_volume, ptca_volume, mortality_egreso_pct)",
    )
    filters: list[QueryFilter] = Field(default_factory=list)
    granularity: str = Field(default="month", examples=["day", "week", "month"])
    limit: int = Field(default=10, ge=1, le=100)
    row_dimension: str = Field(
        default="period",
        description="Dimension de filas para cubo (period, year, quarter, month, granularity)",
    )
    column_dimension: str = Field(
        default="quarter",
        description="Dimension de columnas para cubo (period, year, quarter, month, granularity)",
    )
    aggregation: Literal["sum", "avg", "min", "max"] = Field(
        default="sum",
        description="Agregacion para cubo",
    )


class AnalyticsColumn(BaseModel):
    key: str
    label: str


class AnalyticsQueryResponse(BaseModel):
    widget_type: str
    title: str
    columns: list[AnalyticsColumn]
    rows: list[dict[str, Any]]
    meta: dict[str, Any] = Field(default_factory=dict)
