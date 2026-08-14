"""Endpoints del KPI designer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.repositories.mysql_repository import MySQLRepository
from app.tests.conftest import get_token


def _valid_payload() -> dict:
    return {
        "kpi_name": "KPI unit designer",
        "description": "KPI de prueba unitaria",
        "granularity": "month",
        "sql_query": (
            "SELECT {period_expr} AS period, COUNT(*) AS value "
            "FROM flow_coordina f WHERE f.Realizado = 255 {date_clause} "
            "GROUP BY {period_expr} ORDER BY period"
        ),
    }


def test_ui_available_without_auth(client: TestClient) -> None:
    response = client.get("/api/v1/kpi-designer/ui")
    assert response.status_code == 200
    assert "KPI Designer" in response.text


def test_generate_ok_and_bad_sql(client: TestClient) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    ok = client.post("/api/v1/kpi-designer/generate", headers=headers, json=_valid_payload())
    assert ok.status_code == 200
    assert ok.json()["generated_kpi_key"] == "kpi_unit_designer"

    bad = client.post(
        "/api/v1/kpi-designer/generate",
        headers=headers,
        json={**_valid_payload(), "sql_query": "DELETE FROM flow_coordina"},
    )
    assert bad.status_code == 400


def test_register_ok_and_bad_granularity(client: TestClient) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "key": "reg_kpi_unit",
        "label": "Reg KPI",
        "description": "Descripcion valida del KPI",
        "sql_query_template": _valid_payload()["sql_query"],
        "default_granularity": "month",
    }
    ok = client.post("/api/v1/kpi-designer/register", headers=headers, json=payload)
    assert ok.status_code == 200
    assert ok.json()["success"] is True
    assert ok.json()["persisted_in_db"] is False  # mock backend

    bad = client.post(
        "/api/v1/kpi-designer/register",
        headers=headers,
        json={**payload, "default_granularity": "hora"},
    )
    assert bad.status_code == 400


def test_register_persists_in_mysql(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    fake_repo = MagicMock(spec=MySQLRepository)
    monkeypatch.setattr("app.api.v1.kpi_designer.get_repository", lambda: fake_repo)

    payload = {
        "key": "reg_kpi_mysql",
        "label": "Reg KPI MySQL",
        "description": "Descripcion valida del KPI",
        "sql_query_template": _valid_payload()["sql_query"],
        "default_granularity": "week",
    }
    response = client.post("/api/v1/kpi-designer/register", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["persisted_in_db"] is True
    fake_repo.upsert_dynamic_kpi.assert_called_once()


def test_register_persist_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    def _boom(item, repository):
        raise RuntimeError("disk full")

    monkeypatch.setattr("app.api.v1.kpi_designer._persist_dynamic_kpi", _boom)
    response = client.post(
        "/api/v1/kpi-designer/register",
        headers=headers,
            json={
                "key": "reg_fail",
                "label": "Reg Fail",
                "description": "Descripcion valida del KPI",
                "sql_query_template": _valid_payload()["sql_query"],
                "default_granularity": "day",
            },
    )
    assert response.status_code == 500


def test_create_validation_failure_rolls_back(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.services.kpi_service import KpiService

    def _fail(self, payload):
        raise RuntimeError("query failed")

    monkeypatch.setattr(KpiService, "query", _fail)
    response = client.post(
        "/api/v1/kpi-designer/create",
        headers=headers,
        json=_valid_payload(),
    )
    assert response.status_code == 400
    assert "validacion" in response.json()["detail"].lower()


def test_create_bad_design(client: TestClient) -> None:
    token = get_token(client)
    response = client.post(
        "/api/v1/kpi-designer/create",
        headers={"Authorization": f"Bearer {token}"},
        json={**_valid_payload(), "sql_query": "INSERT INTO x VALUES (1)"},
    )
    assert response.status_code == 400


def test_rollback_dynamic_kpi_mysql(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import kpi_designer as mod

    fake = MagicMock(spec=MySQLRepository)
    fake.deactivate_dynamic_kpi.side_effect = RuntimeError("ignore")
    kpi_registry.upsert(
        DynamicKpi(
            key="tmp_rollback",
            label="t",
            description="d",
            sql_query_template="SELECT 1",
        )
    )
    mod._rollback_dynamic_kpi("tmp_rollback", fake)
    assert kpi_registry.get("tmp_rollback") is None
