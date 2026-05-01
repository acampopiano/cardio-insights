from pydantic import BaseModel, Field


class QueryFilter(BaseModel):
    key: str
    values: list[str]


class KpiQueryRequest(BaseModel):
    kpi_keys: list[str] = Field(min_length=1)
    filters: list[QueryFilter] = Field(default_factory=list)
    granularity: str = Field(default="month", examples=["day", "week", "month"])


class KpiQuerySeriesPoint(BaseModel):
    period: str
    value: float


class KpiQuerySeries(BaseModel):
    kpi_key: str
    points: list[KpiQuerySeriesPoint]


class KpiQueryResponse(BaseModel):
    series: list[KpiQuerySeries]
