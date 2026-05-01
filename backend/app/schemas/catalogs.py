from pydantic import BaseModel


class FilterOption(BaseModel):
    value: str
    label: str


class FilterGroup(BaseModel):
    key: str
    label: str
    options: list[FilterOption]


class FiltersResponse(BaseModel):
    filters: list[FilterGroup]


class KpiDefinition(BaseModel):
    key: str
    label: str
    unit: str
    description: str


class KpisCatalogResponse(BaseModel):
    kpis: list[KpiDefinition]
