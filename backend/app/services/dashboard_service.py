from app.repositories.interfaces import AnalyticsRepository


class DashboardService:
    """Servicio para consolidar datos de resumen, graficos y tabla del dashboard."""

    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        """Inyecta repositorio analitico con fuente mock o mysql."""
        self.analytics_repository = analytics_repository

    def get_summary(self) -> dict:
        """Retorna cards de alto nivel para encabezado del dashboard."""
        return self.analytics_repository.get_dashboard_summary()

    def get_charts(self) -> dict:
        """Retorna series listas para renderizar graficos temporales."""
        return self.analytics_repository.get_dashboard_charts()

    def get_table(self) -> dict:
        """Retorna dataset tabular para analisis detallado en UI."""
        return self.analytics_repository.get_dashboard_table()
