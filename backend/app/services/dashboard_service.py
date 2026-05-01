from app.repositories.interfaces import AnalyticsRepository


class DashboardService:
    def __init__(self, analytics_repository: AnalyticsRepository) -> None:
        self.analytics_repository = analytics_repository

    def get_summary(self) -> dict:
        return self.analytics_repository.get_dashboard_summary()

    def get_charts(self) -> dict:
        return self.analytics_repository.get_dashboard_charts()

    def get_table(self) -> dict:
        return self.analytics_repository.get_dashboard_table()
