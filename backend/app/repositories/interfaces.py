from abc import ABC, abstractmethod
from typing import Any


class AuthRepository(ABC):
    """Contrato para cualquier fuente de datos que provea autenticacion de usuarios."""

    @abstractmethod
    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Busca y retorna usuario por username o None si no existe."""
        raise NotImplementedError


class AnalyticsRepository(ABC):
    """Contrato para acceso a catalogos, dashboard y consultas KPI."""

    @abstractmethod
    def get_filters(self) -> dict[str, Any]:
        """Retorna filtros disponibles para construir consultas analiticas."""
        raise NotImplementedError

    @abstractmethod
    def get_kpis_catalog(self) -> dict[str, Any]:
        """Retorna definiciones de KPIs disponibles para consulta."""
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_summary(self) -> dict[str, Any]:
        """Retorna metricas de resumen para cards del dashboard."""
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_charts(self) -> dict[str, Any]:
        """Retorna series de datos para visualizaciones del dashboard."""
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_table(self) -> dict[str, Any]:
        """Retorna datos tabulares del dashboard."""
        raise NotImplementedError

    @abstractmethod
    def query_kpis(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta consulta KPI dinamica a partir de un payload de filtros."""
        raise NotImplementedError
