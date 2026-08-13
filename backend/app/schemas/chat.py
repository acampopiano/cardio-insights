from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, description="Pregunta en lenguaje natural sobre los datos clínicos.")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Turnos previos de la conversación, para resolver preguntas de seguimiento.",
    )


class ChatResponse(BaseModel):
    question: str
    answer: str = Field(description="Respuesta en lenguaje natural redactada por el asistente.")
    resolved: bool = Field(description="True si se pudo responder con los datos disponibles.")
    sql: str | None = Field(default=None, description="SQL ejecutado (solo lectura) para obtener la respuesta.")
    rows: list[dict[str, Any]] = Field(default_factory=list, description="Filas devueltas por la consulta.")
    row_count: int = Field(default=0)
    error: str | None = Field(default=None, description="Motivo cuando no se pudo resolver la consulta.")
