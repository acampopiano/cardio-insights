from functools import lru_cache

from app.core.config import get_settings
from app.repositories.interfaces import AnalyticsRepository, AuthRepository
from app.repositories.mock_repository import MockRepository
from app.repositories.mysql_repository import MySQLRepository
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.dashboard_service import DashboardService
from app.services.kpi_service import KpiService


@lru_cache
def get_repository() -> AuthRepository | AnalyticsRepository:
    settings = get_settings()
    if settings.repository_backend.lower() == "mysql":
        return MySQLRepository()
    return MockRepository()


def get_auth_service() -> AuthService:
    repository = get_repository()
    return AuthService(auth_repository=repository)


def get_catalog_service() -> CatalogService:
    repository = get_repository()
    return CatalogService(analytics_repository=repository)


def get_dashboard_service() -> DashboardService:
    repository = get_repository()
    return DashboardService(analytics_repository=repository)


def get_kpi_service() -> KpiService:
    repository = get_repository()
    return KpiService(analytics_repository=repository)
