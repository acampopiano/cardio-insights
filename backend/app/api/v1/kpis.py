"""Endpoint de consulta dinamica de series KPI con filtros y granularidad."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_kpi_service
from app.core.security import get_current_claims
from app.schemas.kpis import KpiQueryRequest, KpiQueryResponse
from app.services.kpi_service import KpiService

router = APIRouter(prefix="/kpis", tags=["KPIs"])


@router.post("/query", response_model=KpiQueryResponse)
def query_kpis(
    payload: KpiQueryRequest,
    _: dict = Depends(get_current_claims),
    service: KpiService = Depends(get_kpi_service),
) -> KpiQueryResponse:
    """Ejecuta la consulta de KPIs solicitada y devuelve series normalizadas."""
    return KpiQueryResponse(**service.query(payload.model_dump()))
