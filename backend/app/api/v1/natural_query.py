from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_analytics_service, get_kpi_service
from app.core.security import get_current_claims
from app.schemas.natural_query import NaturalQueryRequest, NaturalQueryResponse
from app.services.analytics_service import AnalyticsService
from app.services.kpi_service import KpiService
from app.services.natural_query_service import NaturalQueryService

router = APIRouter(prefix="/natural-query", tags=["Natural Query"])


@router.post("/run", response_model=NaturalQueryResponse)
def run_natural_query(
    payload: NaturalQueryRequest,
    _: dict = Depends(get_current_claims),
    kpi_service: KpiService = Depends(get_kpi_service),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> NaturalQueryResponse:
    planner = NaturalQueryService()
    plan = planner.build_query_plan(payload.question)

    endpoint_used = str(plan["endpoint_used"])
    query_payload = dict(plan["payload"])

    try:
        if endpoint_used.endswith("/kpis/query"):
            result = kpi_service.query(query_payload)
        else:
            result = analytics_service.query(query_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo ejecutar la consulta natural: {exc}") from exc

    return NaturalQueryResponse(
        success=True,
        intent=str(plan["intent"]),
        endpoint_used=endpoint_used,
        payload=query_payload,
        assumptions=list(plan["assumptions"]),
        explanation=str(plan["explanation"]),
        result=result,
    )
