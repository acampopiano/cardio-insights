"""Cobertura de MySQLRepository sin BD real (mock de _execute / pymysql)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.repositories import mysql_repository as mysql_module
from app.repositories.mysql_repository import MySQLRepository


@pytest.fixture
def repo() -> MySQLRepository:
    return MySQLRepository()


def _period_rows(n: int = 2) -> list[dict[str, Any]]:
    return [{"period": f"2025-0{i}", "value": float(10 * i)} for i in range(1, n + 1)]


@pytest.fixture
def stub_execute(repo: MySQLRepository, monkeypatch: pytest.MonkeyPatch):
    """Stub genérico: CREATE/UPDATE vacíos; SELECTs clínicos -> filas period/value."""

    def _execute(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        q = " ".join(query.split()).lower()
        if q.startswith("create") or q.startswith("insert") or q.startswith("update"):
            return []
        if "from cardio_dynamic_kpis" in q:
            return []
        if "from use_usuarios" in q:
            return []
        if "from use_permiso" in q:
            return []
        if "avg(d.poestadiauci)" in q and "group by" not in q:
            return [{"value": 3.5}]
        if "count(distinct d.k_id) as surgeries" in q:
            return [
                {
                    "period": "2025-01",
                    "surgeries": 5,
                    "ptca": 3,
                    "icu_los_avg": 2.5,
                    "avg_wait_days": 7.0,
                }
            ]
        return _period_rows(2)

    monkeypatch.setattr(repo, "_execute", _execute)
    return repo


def test_execute_with_and_without_params(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"ok": 1}]
    monkeypatch.setattr(mysql_module.pymysql, "connect", lambda **kwargs: conn)

    repo = MySQLRepository()
    assert repo._execute("SELECT 1") == [{"ok": 1}]
    cursor.execute.assert_called_with("SELECT 1")

    cursor.reset_mock()
    cursor.fetchall.return_value = [{"ok": 2}]
    assert repo._execute("SELECT %s", ("x",)) == [{"ok": 2}]
    cursor.execute.assert_called_with("SELECT %s", ("x",))
    conn.close.assert_called()


def test_helpers_date_act_period_quarter(repo: MySQLRepository) -> None:
    assert repo._valid_iso_date("2025-01-15") is True
    assert repo._valid_iso_date("2025/01/15") is False
    assert repo._valid_iso_date(None) is False

    filters = [
        {"key": "date_from", "values": ["2025-01-01"]},
        {"key": "date_to", "values": ["2025-12-31"]},
        {"key": "act_type", "values": ["surgery"]},
    ]
    clause = repo._date_clause("f.FechaRealizado", filters)
    assert ">= '2025-01-01'" in clause
    assert "<= '2025-12-31'" in clause
    assert repo._normalize_act_type(filters) == "surgery"
    assert repo._normalize_act_type([{"key": "act_type", "values": ["nope"]}]) == "all"
    assert repo._normalize_act_type([]) == "all"

    assert "DATE_FORMAT" in repo._period_expr("f.FechaRealizado", "day")
    assert "%x-W%v" in repo._period_expr("f.FechaRealizado", "week")
    assert "%Y'" in repo._period_expr("f.FechaRealizado", "year") or "%Y" in repo._period_expr(
        "f.FechaRealizado", "year"
    )
    assert repo._period_expr("f.FechaRealizado", "month")

    assert repo._quarter_from_period("2025-01") == "Q1"
    assert repo._quarter_from_period("2025-04") == "Q2"
    assert repo._quarter_from_period("2025-13") == "N/A"
    assert repo._quarter_from_period("bad") == "N/A"
    assert repo._quarter_from_period("2025-xx") == "N/A"

    assert repo._latest_value([]) == 0.0
    assert repo._latest_value([{"value": 3}]) == 3.0
    assert repo._first_filter_value([{"key": "from", "values": ["a"]}], ["from"]) == "a"
    assert repo._first_filter_value([{"key": "x", "values": []}], ["x"]) is None


def test_dynamic_kpi_lifecycle(stub_execute: MySQLRepository) -> None:
    item = DynamicKpi(
        key="kpi_test_mysql_unit",
        label="KPI test",
        description="desc",
        sql_query_template="SELECT {period_expr} AS period, 1 AS value FROM flow_coordina f WHERE 1=1 {date_clause}",
        default_granularity="month",
    )
    stub_execute.upsert_dynamic_kpi(item)
    stub_execute.deactivate_dynamic_kpi(item.key)

    # Carga con filas incompletas / granularity inválida
    def _load(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        q = query.lower()
        if "create table" in q:
            return []
        if "from cardio_dynamic_kpis" in q:
            return [
                {
                    "kpi_key": "",
                    "label": "x",
                    "description": "y",
                    "sql_query_template": "SELECT 1",
                    "default_granularity": "month",
                },
                {
                    "kpi_key": "dyn_ok",
                    "label": "Dyn",
                    "description": "ok",
                    "sql_query_template": "SELECT {period_expr} AS period, 2 AS value FROM flow_coordina f WHERE 1=1 {date_clause}",
                    "default_granularity": "invalid",
                },
            ]
        return _period_rows(1)

    stub_execute._execute = _load  # type: ignore[method-assign]
    stub_execute._load_dynamic_kpis_from_db()
    assert kpi_registry.get("dyn_ok") is not None
    assert kpi_registry.get("dyn_ok").default_granularity == "month"


def test_load_dynamic_kpis_swallows_errors(
    repo: MySQLRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(repo, "_execute", MagicMock(side_effect=RuntimeError("db down")))
    repo._load_dynamic_kpis_from_db()  # no debe explotar


def test_get_user_from_db(stub_execute: MySQLRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    def _execute(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        q = query.lower()
        if "from use_usuarios" in q:
            return [
                {
                    "id": 9,
                    "username": "dbuser",
                    "full_name": "DB User",
                    "role": "clinician",
                    "password_plain": "secret",
                    "password_md5": None,
                    "role_id": 2,
                }
            ]
        if "from use_permiso" in q:
            return [{"permission": "Dashboard:Read"}, {"permission": "kpis:query"}]
        return []

    monkeypatch.setattr(stub_execute, "_execute", _execute)
    user = stub_execute.get_user_by_username("dbuser")
    assert user is not None
    assert user["username"] == "dbuser"
    assert "dashboard:read" in user["permissions"]


def test_get_user_fallback_seed_and_missing(
    stub_execute: MySQLRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(stub_execute, "_execute", lambda *a, **k: [])
    seeded = stub_execute.get_user_by_username("dcaraballo")
    assert seeded is not None
    assert seeded["username"] == "dcaraballo"
    assert seeded["role"] == "clinico"
    assert stub_execute.get_user_by_username("ghost") is None


def test_get_user_default_permissions_when_empty(
    stub_execute: MySQLRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _execute(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if "from use_usuarios" in query.lower():
            return [
                {
                    "id": 1,
                    "username": "noperms",
                    "full_name": "No Perms",
                    "role": "user",
                    "password_plain": "x",
                    "password_md5": None,
                }
            ]
        return []

    monkeypatch.setattr(stub_execute, "_execute", _execute)
    user = stub_execute.get_user_by_username("noperms")
    assert user["permissions"] == ["dashboard:read", "kpis:query"]


def test_catalog_filters_dashboard(stub_execute: MySQLRepository) -> None:
    filters = stub_execute.get_filters()
    assert any(f["key"] == "act_type" for f in filters["filters"])

    catalog = stub_execute.get_kpis_catalog()
    keys = {k["key"] for k in catalog["kpis"]}
    assert "surgery_volume" in keys
    assert "avg_wait_days" in keys

    summary = stub_execute.get_dashboard_summary()
    assert len(summary["cards"]) == 5
    assert summary["cards"][0]["key"] == "surgery_volume"

    charts = stub_execute.get_dashboard_charts()
    assert len(charts["charts"]) == 2

    table = stub_execute.get_dashboard_table()
    assert table["total"] >= 1
    assert "period" in table["rows"][0]["values"]


def test_dashboard_delta_edge_cases(
    stub_execute: MySQLRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _execute(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        q = query.lower()
        if "avg(d.poestadiauci)" in q and "group by" not in q:
            return [{"value": None}]
        # Una sola fila -> delta None; prev=0 también
        if "date_format" in q:
            return [{"period": "2025-01", "value": 0}]
        return []

    monkeypatch.setattr(stub_execute, "_execute", _execute)
    summary = stub_execute.get_dashboard_summary()
    assert all(card.get("delta") is None for card in summary["cards"])


def test_query_kpis_all_builtin_keys(stub_execute: MySQLRepository) -> None:
    keys = [
        "volumen_mensual_total",
        "surgery_volume",
        "ptca_volume",
        "ptca_share_pct",
        "avg_wait_days",
        "espera_maxima_en_dias",
        "mortality_egreso_pct",
        "mortality_30d",
        "mortality_egreso_count",
        "icu_los_avg",
        "reintervenciones_mensual",
        "hemodinamia_volumen_mensual",
        "centros_que_envian_pacientes",
        "top_centro_por_periodo",
        "espera_tramite_a_autorizacion_dias",
        "espera_autorizacion_a_realizado_dias",
        "readmission_30d",  # alias map missing -> treated as dynamic/unknown skip
    ]
    result = stub_execute.query_kpis(
        {
            "kpi_keys": keys,
            "granularity": "year",
            "filters": [
                {"key": "date_from", "values": ["2025-01-01"]},
                {"key": "date_to", "values": ["2025-12-31"]},
                {"key": "act_type", "values": ["all"]},
            ],
        }
    )
    returned = {s["kpi_key"] for s in result["series"]}
    assert "surgery_volume" in returned
    assert "ptca_share_pct" in returned
    assert "hemodinamia_volumen_mensual" in returned


def test_query_kpis_act_type_filters_and_invalid_granularity(stub_execute: MySQLRepository) -> None:
    surgery_only = stub_execute.query_kpis(
        {
            "kpi_keys": ["ptca_volume", "surgery_volume", "avg_wait_days"],
            "granularity": "nope",
            "filters": [{"key": "act_type", "values": ["surgery"]}],
        }
    )
    by_key = {s["kpi_key"]: s for s in surgery_only["series"]}
    assert by_key["ptca_volume"]["points"] == []
    assert by_key["surgery_volume"]["points"]

    ptca_only = stub_execute.query_kpis(
        {
            "kpi_keys": ["surgery_volume", "icu_los_avg", "avg_wait_days"],
            "granularity": "week",
            "filters": [{"key": "act_type", "values": ["ptca"]}],
        }
    )
    by_key = {s["kpi_key"]: s for s in ptca_only["series"]}
    assert by_key["surgery_volume"]["points"] == []
    assert by_key["icu_los_avg"]["points"] == []
    assert by_key["avg_wait_days"]["points"]


def test_query_kpis_dynamic(stub_execute: MySQLRepository) -> None:
    kpi_registry.upsert(
        DynamicKpi(
            key="custom_dyn_kpi",
            label="Custom",
            description="custom",
            sql_query_template=(
                "SELECT {period_expr} AS period, COUNT(*) AS value "
                "FROM flow_coordina f WHERE 1=1 {date_clause}"
            ),
        )
    )
    result = stub_execute.query_kpis(
        {
            "kpi_keys": ["custom_dyn_kpi", "unknown_kpi_xyz"],
            "granularity": "day",
            "filters": [{"key": "date_from", "values": ["2025-01-01"]}],
        }
    )
    keys = [s["kpi_key"] for s in result["series"]]
    assert "custom_dyn_kpi" in keys
    assert "unknown_kpi_xyz" not in keys


def test_query_analytics_ranking_cube_table(stub_execute: MySQLRepository) -> None:
    ranking = stub_execute.query_analytics(
        {
            "widget_type": "ranking",
            "metric_key": "surgery_volume",
            "granularity": "month",
            "limit": 5,
        }
    )
    assert ranking["widget_type"] == "ranking"
    assert ranking["rows"]
    assert ranking["rows"][0]["rank"] == 1

    cube = stub_execute.query_analytics(
        {
            "widget_type": "cube",
            "metric_key": "avg_wait_days",
            "granularity": "bad",
            "row_dimension": "period",
            "column_dimension": "quarter",
            "limit": 200,  # se capea a 100
        }
    )
    assert cube["widget_type"] == "cube"
    assert cube["rows"]
    assert cube["rows"][0]["column_key"].startswith("Q")

    cube_other = stub_execute.query_analytics(
        {
            "widget_type": "cube",
            "metric_key": "surgery_volume",
            "column_dimension": "period",
            "limit": 0,  # se corrige a 1
        }
    )
    assert cube_other["widget_type"] == "cube"

    table = stub_execute.query_analytics({"widget_type": "table", "limit": 5})
    assert table["widget_type"] == "table"
    assert table["rows"]
