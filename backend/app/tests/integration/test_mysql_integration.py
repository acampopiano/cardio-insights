"""Integración contra MySQL de docker-compose (opt-in).

Requisitos:
  docker compose up -d mysql
  # Si cambiaste init.sql y el volumen ya existía:
  docker compose down -v && docker compose up -d mysql

  # PowerShell
  $env:RUN_INTEGRATION_DB_TESTS="1"
  pytest -q app/tests/integration
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.dependencies import get_repository
from app.core.kpi_registry import DynamicKpi
from app.main import app
from app.repositories.mysql_repository import MySQLRepository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_DB_TESTS", "0") != "1",
    reason="Set RUN_INTEGRATION_DB_TESTS=1 to run MySQL integration tests.",
)


def _configure_mysql_env() -> None:
    os.environ["REPOSITORY_BACKEND"] = "mysql"
    os.environ.setdefault("MYSQL_HOST", "localhost")
    os.environ.setdefault("MYSQL_PORT", "3306")
    os.environ.setdefault("MYSQL_USER", "cardio")
    os.environ.setdefault("MYSQL_PASSWORD", "cardio")
    os.environ.setdefault("MYSQL_DATABASE", "incc")
    get_settings.cache_clear()
    get_repository.cache_clear()


@pytest.fixture
def mysql_client() -> TestClient:
    _configure_mysql_env()
    return TestClient(app)


@pytest.fixture
def mysql_repo() -> MySQLRepository:
    _configure_mysql_env()
    return MySQLRepository()


def _auth_headers(client: TestClient) -> dict[str, str]:
    username = os.getenv("INCC_TEST_USERNAME", "dcaraballo")
    password = os.getenv("INCC_TEST_PASSWORD", "Demo1234!")
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_mysql_login_and_dashboard(mysql_client: TestClient) -> None:
    headers = _auth_headers(mysql_client)

    summary = mysql_client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200
    assert len(summary.json().get("cards", [])) > 0

    charts = mysql_client.get("/api/v1/dashboard/charts", headers=headers)
    assert charts.status_code == 200
    assert charts.json().get("charts")

    table = mysql_client.get("/api/v1/dashboard/table", headers=headers)
    assert table.status_code == 200
    assert table.json().get("total", 0) >= 0


def test_mysql_kpis_and_analytics(mysql_client: TestClient) -> None:
    headers = _auth_headers(mysql_client)
    filters = [
        {"key": "date_from", "values": ["2025-01-01"]},
        {"key": "date_to", "values": ["2025-12-31"]},
        {"key": "act_type", "values": ["all"]},
    ]
    query = mysql_client.post(
        "/api/v1/kpis/query",
        headers=headers,
        json={
            "kpi_keys": [
                "surgery_volume",
                "ptca_volume",
                "avg_wait_days",
                "volumen_mensual_total",
                "ptca_share_pct",
                "mortality_egreso_pct",
                "icu_los_avg",
            ],
            "granularity": "month",
            "filters": filters,
        },
    )
    assert query.status_code == 200
    assert len(query.json().get("series", [])) == 7

    ranking = mysql_client.post(
        "/api/v1/analytics/query",
        headers=headers,
        json={
            "widget_type": "ranking",
            "metric_key": "surgery_volume",
            "granularity": "month",
            "limit": 3,
            "filters": filters,
        },
    )
    assert ranking.status_code == 200
    assert ranking.json()["widget_type"] == "ranking"

    catalogs = mysql_client.get("/api/v1/catalogs/kpis", headers=headers)
    assert catalogs.status_code == 200
    assert catalogs.json().get("kpis")


def test_mysql_repository_direct(mysql_repo: MySQLRepository) -> None:
    user = mysql_repo.get_user_by_username("dcaraballo")
    assert user is not None
    assert user["username"] == "dcaraballo"
    assert user["role"] == "clinico"

    filters = mysql_repo.get_filters()
    assert filters["filters"]

    summary = mysql_repo.get_dashboard_summary()
    assert summary["cards"]

    series = mysql_repo.query_kpis(
        {
            "kpi_keys": ["surgery_volume", "hemodinamia_volumen_mensual", "centros_que_envian_pacientes"],
            "granularity": "year",
            "filters": [
                {"key": "date_from", "values": ["2024-01-01"]},
                {"key": "date_to", "values": ["2025-12-31"]},
            ],
        }
    )
    assert len(series["series"]) == 3

    mysql_repo.upsert_dynamic_kpi(
        DynamicKpi(
            key="integration_dyn_kpi",
            label="Integration KPI",
            description="KPI dinámico de integración",
            sql_query_template=(
                "SELECT {period_expr} AS period, COUNT(*) AS value "
                "FROM flow_coordina f WHERE f.Realizado = 255 {date_clause} "
                "GROUP BY {period_expr} ORDER BY period"
            ),
        )
    )
    dyn = mysql_repo.query_kpis(
        {
            "kpi_keys": ["integration_dyn_kpi"],
            "granularity": "month",
            "filters": [{"key": "date_from", "values": ["2025-01-01"]}],
        }
    )
    assert dyn["series"]
    mysql_repo.deactivate_dynamic_kpi("integration_dyn_kpi")
