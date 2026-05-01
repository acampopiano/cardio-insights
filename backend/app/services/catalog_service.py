from app.repositories.interfaces import AnalyticsRepository


class CatalogService:
    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        self.analytics_repository = analytics_repository

    def get_filters(self) -> dict:
        return self.analytics_repository.get_filters()

    def get_kpis_catalog(self) -> dict:
        return self.analytics_repository.get_kpis_catalog()
