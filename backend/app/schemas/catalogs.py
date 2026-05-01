from pydantic import BaseModel


class FilterOption(BaseModel):
    """Opcion individual de un filtro mostrado en frontend."""

    value: str
    label: str


class FilterGroup(BaseModel):
    """Grupo de filtro con clave funcional, etiqueta y lista de opciones."""

    key: str
    label: str
    options: list[FilterOption]


class FiltersResponse(BaseModel):
    """Contrato de salida del endpoint de catalogo de filtros."""

    filters: list[FilterGroup]


class KpiDefinition(BaseModel):
    """Definicion funcional de un KPI disponible para consulta."""

    key: str
    label: str
    unit: str
    description: str


class KpisCatalogResponse(BaseModel):
    """Contrato de salida del endpoint de catalogo de KPIs."""

    kpis: list[KpiDefinition]
