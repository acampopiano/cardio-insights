from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalogs import router as catalogs_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.kpis import router as kpis_router
from app.api.v1.natural_query import router as natural_query_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(catalogs_router)
api_router.include_router(dashboard_router)
api_router.include_router(kpis_router)
api_router.include_router(analytics_router)
api_router.include_router(natural_query_router)
