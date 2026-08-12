"""Smoke de catalogs y dashboard (cubre servicios finos)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.tests.conftest import get_token


def test_catalogs_filters_and_kpis(client: TestClient) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    filters = client.get("/api/v1/catalogs/filters", headers=headers)
    assert filters.status_code == 200
    assert filters.json()["filters"]

    kpis = client.get("/api/v1/catalogs/kpis", headers=headers)
    assert kpis.status_code == 200
    assert kpis.json()["kpis"]


def test_dashboard_endpoints(client: TestClient) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    for path in (
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/charts",
        "/api/v1/dashboard/table",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
