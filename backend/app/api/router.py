"""Exporta el router versionado para simplificar imports del paquete API."""

from app.api.v1.api import api_router

__all__ = ["api_router"]
