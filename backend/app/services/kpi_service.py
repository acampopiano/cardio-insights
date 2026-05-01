from app.repositories.interfaces import AnalyticsRepository


class KpiService:
    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        self.analytics_repository = analytics_repository

    def query(self, payload: dict) -> dict:
        return self.analytics_repository.query_kpis(payload)
