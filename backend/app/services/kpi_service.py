from app.repositories.interfaces import AnalyticsRepository


class KpiService:
    """Servicio de consulta KPI; centraliza el punto de entrada de series analiticas."""

    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        """Inyecta repositorio analitico para consultar desde mock o mysql."""
        self.analytics_repository = analytics_repository

    def query(self, payload: dict) -> dict:
        """Delega consulta KPI al repositorio y devuelve respuesta normalizada."""
        return self.analytics_repository.query_kpis(payload)
