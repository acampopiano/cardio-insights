from abc import ABC, abstractmethod
from typing import Any


class AuthRepository(ABC):
    @abstractmethod
    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        raise NotImplementedError


class AnalyticsRepository(ABC):
    @abstractmethod
    def get_filters(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_kpis_catalog(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_summary(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_charts(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_table(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def query_kpis(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
