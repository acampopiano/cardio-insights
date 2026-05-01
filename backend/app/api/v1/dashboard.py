"""Endpoints del dashboard para tarjetas resumen, graficos y tabla consolidada."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_dashboard_service
from app.core.security import get_current_claims
from app.schemas.dashboard import (
    DashboardChartsResponse,
    DashboardSummaryResponse,
    DashboardTableResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_summary(
    _: dict = Depends(get_current_claims),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSummaryResponse:
    """Obtiene las metricas de alto nivel mostradas como cards en el dashboard."""
    return DashboardSummaryResponse(**service.get_summary())


@router.get("/charts", response_model=DashboardChartsResponse)
def get_charts(
    _: dict = Depends(get_current_claims),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardChartsResponse:
    """Obtiene series temporales estructuradas para graficos del dashboard."""
    return DashboardChartsResponse(**service.get_charts())


@router.get("/table", response_model=DashboardTableResponse)
def get_table(
    _: dict = Depends(get_current_claims),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardTableResponse:
    """Obtiene el detalle tabular para analisis operativo mensual."""
    return DashboardTableResponse(**service.get_table())
