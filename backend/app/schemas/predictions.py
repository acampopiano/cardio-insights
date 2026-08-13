from typing import Any

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    values: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Valores de entrada del caso, indexados por la clave del campo "
            "(ver `features` en el catálogo de modelos). Los flags aceptan booleanos; "
            "las numéricas, números; las categóricas, el código como string."
        ),
    )


class ContributingFactor(BaseModel):
    factor: str
    odds_ratio: float


class ExplanationItem(BaseModel):
    label: str = Field(description="Variable y su valor en el caso.")
    effect: float = Field(description="Contribución en log-odds (signo = dirección).")
    direction: str = Field(description="'up' si aumenta el riesgo, 'down' si lo reduce.")


class PredictionResponse(BaseModel):
    cohort: str
    probability: float = Field(description="Probabilidad estimada de mortalidad (0-1).")
    probability_pct: float = Field(description="Probabilidad en porcentaje.")
    risk_level: str = Field(description="Categoría de riesgo: bajo | moderado | alto.")
    threshold: float = Field(description="Umbral (Youden) para clasificar 'alto riesgo'.")
    base_rate: float = Field(description="Tasa base de mortalidad de la cohorte.")
    risk_ratio: float | None = Field(default=None, description="Probabilidad / tasa base (cuántas veces el promedio).")
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    explanation: list[ExplanationItem] = Field(default_factory=list)
    model_version: str | None = None
