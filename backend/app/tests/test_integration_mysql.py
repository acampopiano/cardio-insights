"""Prueba de integracion opcional para validar endpoints contra MySQL real."""

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_DB_TESTS", "0") != "1",
    reason="Set RUN_INTEGRATION_DB_TESTS=1 to run MySQL integration tests.",
)
def test_mysql_dashboard_and_kpis_query() -> None:
    """Ejecuta login, dashboard y query KPI usando backend mysql configurado por entorno."""
    os.environ["REPOSITORY_BACKEND"] = "mysql"
    os.environ.setdefault("MYSQL_HOST", "localhost")
    os.environ.setdefault("MYSQL_PORT", "3306")
    os.environ.setdefault("MYSQL_USER", "root")
    os.environ.setdefault("MYSQL_PASSWORD", "")
    os.environ.setdefault("MYSQL_DATABASE", "incc")

    get_settings.cache_clear()

    client = TestClient(app)
    username = os.getenv("INCC_TEST_USERNAME", "clinician")
    password = os.getenv("INCC_TEST_PASSWORD", "Demo1234!")

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    summary_response = client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary_response.status_code == 200
    assert len(summary_response.json().get("cards", [])) > 0

    query_response = client.post(
        "/api/v1/kpis/query",
        json={
            "kpi_keys": ["surgery_volume", "ptca_volume", "avg_wait_days"],
            "granularity": "month",
            "filters": [
                {"key": "date_from", "values": ["2025-01-01"]},
                {"key": "date_to", "values": ["2026-12-31"]},
                {"key": "act_type", "values": ["all"]},
            ],
        },
        headers=headers,
    )
    assert query_response.status_code == 200
    assert len(query_response.json().get("series", [])) == 3
