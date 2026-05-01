from fastapi import APIRouter, Depends

from app.core.dependencies import get_catalog_service
from app.core.security import get_current_claims
from app.schemas.catalogs import FiltersResponse, KpisCatalogResponse
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/catalogs", tags=["Catalogs"])


@router.get("/filters", response_model=FiltersResponse)
def get_filters(
    _: dict = Depends(get_current_claims),
    service: CatalogService = Depends(get_catalog_service),
) -> FiltersResponse:
    return FiltersResponse(**service.get_filters())


@router.get("/kpis", response_model=KpisCatalogResponse)
def get_kpis_catalog(
    _: dict = Depends(get_current_claims),
    service: CatalogService = Depends(get_catalog_service),
) -> KpisCatalogResponse:
    return KpisCatalogResponse(**service.get_kpis_catalog())
