from pydantic import BaseModel, Field


class NaturalQueryRequest(BaseModel):
    question: str = Field(min_length=3, description="Pregunta en lenguaje natural")


class NaturalQueryResponse(BaseModel):
    success: bool
    intent: str
    endpoint_used: str
    payload: dict[str, object]
    assumptions: list[str]
    explanation: str
    result: dict[str, object]
