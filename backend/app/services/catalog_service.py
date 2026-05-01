from app.repositories.interfaces import AnalyticsRepository


class CatalogService:
    """Servicio para exponer catalogos de filtros y definiciones de KPIs."""

    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        """Inyecta repositorio analitico configurable por entorno."""
        self.analytics_repository = analytics_repository

    def get_filters(self) -> dict:
        """Obtiene filtros disponibles para construir consultas desde frontend."""
        return self.analytics_repository.get_filters()

    def get_kpis_catalog(self) -> dict:
        """Obtiene catalogo de KPIs con etiqueta, unidad y descripcion."""
        return self.analytics_repository.get_kpis_catalog()
