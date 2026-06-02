from fastapi import APIRouter, Depends

from app.core.dependencies import get_analytics_service
from app.core.security import get_current_claims
from app.schemas.analytics import AnalyticsQueryRequest, AnalyticsQueryResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/query", response_model=AnalyticsQueryResponse)
def query_analytics(
    payload: AnalyticsQueryRequest,
    _: dict = Depends(get_current_claims),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsQueryResponse:
    return AnalyticsQueryResponse(**service.query(payload.model_dump()))
