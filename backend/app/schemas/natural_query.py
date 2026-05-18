from pydantic import BaseModel, Field


class NaturalQueryRequest(BaseModel):
    question: str = Field(min_length=3, description="Pregunta en lenguaje natural")
    approve_auto_kpi: bool = Field(
        default=False,
        description="Permite auto-creacion de KPI en modo human_approve.",
    )


class NaturalQueryResponse(BaseModel):
    success: bool
    intent: str
    endpoint_used: str
    payload: dict[str, object]
    assumptions: list[str]
    explanation: str
    auto_kpi: dict[str, object] | None = None
    result: dict[str, object]
