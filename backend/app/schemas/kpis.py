from pydantic import BaseModel, Field


class QueryFilter(BaseModel):
    """Filtro dinamico enviado por cliente con clave y lista de valores."""

    key: str
    values: list[str]


class KpiQueryRequest(BaseModel):
    """Payload para solicitar una o mas series KPI con filtros opcionales."""

    kpi_keys: list[str] = Field(min_length=1)
    filters: list[QueryFilter] = Field(default_factory=list)
    granularity: str = Field(default="month", examples=["day", "week", "month"])


class KpiQuerySeriesPoint(BaseModel):
    """Punto temporal de una serie KPI en formato periodo/valor."""

    period: str
    value: float


class KpiQuerySeries(BaseModel):
    """Serie completa asociada a una clave KPI."""

    kpi_key: str
    points: list[KpiQuerySeriesPoint]


class KpiQueryResponse(BaseModel):
    """Respuesta global de consulta KPI con todas las series solicitadas."""

    series: list[KpiQuerySeries]
