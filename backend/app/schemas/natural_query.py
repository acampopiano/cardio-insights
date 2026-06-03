from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AllowedIntent = Literal["trend", "ranking", "comparison", "alert"]
AllowedEndpoint = Literal["/api/v1/kpis/query", "/api/v1/analytics/query"]
AllowedSource = Literal["rules", "llm", "memory"]


class NaturalQueryRequest(BaseModel):
    question: str = Field(min_length=3, description="Pregunta en lenguaje natural")
    use_llm_fallback: bool = Field(
        default=True,
        description="Si es true, habilita fallback LLM en gateway cuando sus reglas no alcanzan.",
    )
    approve_auto_kpi: bool = Field(
        default=False,
        description="Permite auto-creacion de KPI en modo human_approve (flujo local).",
    )


class TranslatedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    intent: str | None = None
    metric: str | None = None
    granularity: str | None = None
    period: dict[str, Any] | None = None
    filters: list[dict[str, Any]] | None = None
    limit: int | None = None


class NaturalQueryGatewayResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    resolved: bool
    source: str = "rules"
    intent: str | None = None
    metric: str | None = None
    metric_name: str | None = None
    endpoint: str | None = None
    translated_payload: TranslatedPayload | None = None
    confidence: float | None = None
    assumptions: list[str] = Field(default_factory=list)


class NaturalQueryRunResponse(BaseModel):
    interaction_id: str | None = None
    question: str
    resolved: bool
    source: AllowedSource
    intent: str
    metric: str
    endpoint: AllowedEndpoint
    translated_payload: dict[str, Any]
    assumptions: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    # Campos de compatibilidad para clientes existentes.
    success: bool
    endpoint_used: AllowedEndpoint
    payload: dict[str, Any]
    explanation: str
    auto_kpi: dict[str, Any] | None = None


class NaturalQueryFeedbackRequest(BaseModel):
    interaction_id: str | None = Field(default=None)
    question: str | None = Field(default=None)
    accepted: bool = Field(
        description="True si la interpretación fue correcta; False si requiere corrección.",
    )
    corrected_intent: str | None = Field(default=None)
    corrected_metric: str | None = Field(default=None)
    corrected_endpoint: str | None = Field(default=None)
    corrected_translated_payload: dict[str, Any] | None = Field(default=None)
    notes: str | None = Field(default=None)


class NaturalQueryFeedbackResponse(BaseModel):
    feedback_id: str
    recorded: bool


class NaturalQueryTrainingExportResponse(BaseModel):
    total_samples: int
    export_path: str
