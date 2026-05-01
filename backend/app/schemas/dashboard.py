from pydantic import BaseModel, Field


class SummaryCard(BaseModel):
    """Tarjeta de resumen mostrada en la parte superior del dashboard."""

    key: str
    label: str
    value: float | int
    unit: str | None = None
    delta: float | None = None


class DashboardSummaryResponse(BaseModel):
    """Respuesta con todas las cards de resumen."""

    cards: list[SummaryCard]


class ChartSeriesPoint(BaseModel):
    """Punto individual de una serie para graficos."""

    x: str
    y: float


class ChartSeries(BaseModel):
    """Serie etiquetada con sus puntos para una visualizacion."""

    key: str
    label: str
    points: list[ChartSeriesPoint]


class DashboardChart(BaseModel):
    """Estructura completa de un grafico del dashboard."""

    chart_id: str
    title: str
    chart_type: str = Field(examples=["line", "bar", "area"])
    series: list[ChartSeries]


class DashboardChartsResponse(BaseModel):
    """Respuesta con la coleccion de graficos del dashboard."""

    charts: list[DashboardChart]


class TableColumn(BaseModel):
    """Definicion de columna para la tabla analitica."""

    key: str
    label: str


class TableRow(BaseModel):
    """Fila de tabla en formato clave-valor serializable."""

    values: dict[str, str | int | float | None]


class DashboardTableResponse(BaseModel):
    """Respuesta tabular del dashboard con columnas, filas y total."""

    columns: list[TableColumn]
    rows: list[TableRow]
    total: int
