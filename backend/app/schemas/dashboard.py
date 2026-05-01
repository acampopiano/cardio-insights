from pydantic import BaseModel, Field


class SummaryCard(BaseModel):
    key: str
    label: str
    value: float | int
    unit: str | None = None
    delta: float | None = None


class DashboardSummaryResponse(BaseModel):
    cards: list[SummaryCard]


class ChartSeriesPoint(BaseModel):
    x: str
    y: float


class ChartSeries(BaseModel):
    key: str
    label: str
    points: list[ChartSeriesPoint]


class DashboardChart(BaseModel):
    chart_id: str
    title: str
    chart_type: str = Field(examples=["line", "bar", "area"])
    series: list[ChartSeries]


class DashboardChartsResponse(BaseModel):
    charts: list[DashboardChart]


class TableColumn(BaseModel):
    key: str
    label: str


class TableRow(BaseModel):
    values: dict[str, str | int | float | None]


class DashboardTableResponse(BaseModel):
    columns: list[TableColumn]
    rows: list[TableRow]
    total: int
