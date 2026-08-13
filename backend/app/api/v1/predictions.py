from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import ML_ACCESS_ROLES, require_roles
from app.schemas.predictions import PredictionRequest, PredictionResponse
from app.services.ml_service import MLService, ModelNotAvailableError

router = APIRouter(prefix="/predictions", tags=["Predicciones (ML)"])

_require_ml_access = require_roles(*ML_ACCESS_ROLES)


@router.get("/models")
def list_models(_claims: dict = Depends(_require_ml_access)) -> list[dict[str, Any]]:
    """Catálogo de modelos disponibles + metadatos y campos para el formulario."""
    return MLService().list_models()


@router.get("/models/{cohort}")
def get_model(cohort: str, _claims: dict = Depends(_require_ml_access)) -> dict[str, Any]:
    try:
        return MLService().get_model_meta(cohort)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ModelNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/{cohort}", response_model=PredictionResponse)
def predict(
    cohort: str,
    payload: PredictionRequest,
    _claims: dict = Depends(_require_ml_access),
) -> PredictionResponse:
    """Estima la probabilidad de mortalidad para un caso puntual.

    Herramienta de APOYO / investigación, no un sistema de decisión clínica.
    """
    try:
        result = MLService().predict(cohort, payload.values)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ModelNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return PredictionResponse(**result)
