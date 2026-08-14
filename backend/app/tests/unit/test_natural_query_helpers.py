"""Helpers internos de natural_query (filtros, gateway plan, memoria)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.v1 import natural_query as nq
from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.repositories.mock_repository import MockRepository
from app.schemas.natural_query import NaturalQueryGatewayResponse, TranslatedPayload


def test_extract_filters_from_list_and_date_range_and_period() -> None:
    assert nq._extract_filters(
        {
            "filters": [
                {"key": "date_from", "values": ["2025-01-01"]},
                {"key": "", "values": ["x"]},
                {"key": "empty", "values": []},
                "bad",
            ]
        }
    ) == [{"key": "date_from", "values": ["2025-01-01"]}]

    assert nq._extract_filters({"date_range": {"year": 2024}}) == [
        {"key": "date_from", "values": ["2024-01-01"]},
        {"key": "date_to", "values": ["2024-12-31"]},
    ]
    assert nq._extract_filters(
        {"date_range": {"date_from": "2025-03-01", "date_to": "2025-03-31"}}
    )

    assert nq._extract_filters({"period": {"type": "current_year"}})
    assert nq._extract_filters({"period": {"type": "last_year"}})
    assert nq._extract_filters({"period": {"type": "year", "year": 2022}})
    assert nq._extract_filters({"period": {"type": "month", "year": 2025, "month": 2}})
    assert nq._extract_filters({"period": {"type": "date_range", "date_from": "2025-01-01"}})
    assert nq._extract_filters({"period": {"year": 2023}})  # shorthand sin type
    assert nq._extract_filters({"period": {"type": "unknown"}}) == []
    assert nq._extract_filters({}) == []


def test_translated_payload_to_internal_query() -> None:
    kpi = nq._translated_payload_to_internal_query(
        "/api/v1/kpis/query",
        "trend",
        "surgery_volume",
        {"granularity": "bad", "filters": [{"key": "date_from", "values": ["2025-01-01"]}]},
    )
    assert kpi is not None
    assert kpi["granularity"] == "month"

    ranking = nq._translated_payload_to_internal_query(
        "/api/v1/analytics/query",
        "ranking",
        "surgery_volume",
        {"limit": 0, "ranking": {"limit": 3}},
    )
    assert ranking is not None
    assert ranking["widget_type"] == "ranking"
    assert ranking["limit"] == 1  # corregido desde 0

    ranking_hi = nq._translated_payload_to_internal_query(
        "/api/v1/analytics/query",
        "ranking",
        "surgery_volume",
        {"limit": 500},
    )
    assert ranking_hi is not None
    assert ranking_hi["limit"] == 100

    table = nq._translated_payload_to_internal_query(
        "/api/v1/analytics/query",
        "trend",
        "surgery_volume",
        {},
    )
    assert table is not None
    assert table["widget_type"] == "table"

    assert nq._translated_payload_to_internal_query("/other", "trend", "x", {}) is None


def test_validate_gateway_plan_paths() -> None:
    repo = MockRepository()
    unresolved = NaturalQueryGatewayResponse(resolved=False)
    plan, errors = nq._validate_and_build_gateway_plan(unresolved, repo)
    assert plan is None
    assert errors

    bad = NaturalQueryGatewayResponse(
        resolved=True,
        intent="nope",
        endpoint="/bad",
        metric="",
        source="weird",
        translated_payload=None,
    )
    plan, errors = nq._validate_and_build_gateway_plan(bad, repo)
    assert plan is None

    ok = NaturalQueryGatewayResponse(
        resolved=True,
        intent="ranking",
        endpoint="/api/v1/kpis/query",
        metric="surgery_volume",
        source="llm",
        translated_payload=TranslatedPayload(
            intent="ranking",
            metric="surgery_volume",
            granularity="month",
            limit=3,
        ),
        assumptions=["a"],
        confidence=0.9,
    )
    plan, errors = nq._validate_and_build_gateway_plan(ok, repo)
    assert errors == []
    assert plan is not None
    assert plan["endpoint"] == "/api/v1/analytics/query"


def test_detect_unsafe_payload_and_catalog() -> None:
    assert nq._detect_unsafe_translated_payload({"sql": "select 1"}) is not None
    assert nq._detect_unsafe_translated_payload({"raw_sql": "x"}) is not None
    assert nq._detect_unsafe_translated_payload({"metric": "surgery_volume"}) is None

    repo = MockRepository()
    assert nq._metric_exists_in_local_catalog("surgery_volume", repo) is True
    assert nq._metric_exists_in_local_catalog("__unmapped__", repo) is False
    kpi_registry.upsert(
        DynamicKpi(
            key="dyn_helper",
            label="d",
            description="d",
            sql_query_template="SELECT 1",
        )
    )
    assert nq._metric_exists_in_local_catalog("dyn_helper", repo) is True


def test_memory_plan_matches_and_year_filters() -> None:
    assert nq._memory_plan_matches_question(
        "espera promedio",
        {"metric": "avg_wait_days"},
    )
    assert not nq._memory_plan_matches_question(
        "cirugias totales",
        {"metric": "avg_wait_days"},
    )

    filters = [
        {"key": "date_from", "values": ["2025-01-01"]},
        {"key": "date_to", "values": ["2025-12-31"]},
    ]
    assert nq._is_full_year_filter(filters) is True
    assert nq._full_year_from_filters(filters) == 2025
    assert nq._full_year_from_filters([{"key": "date_from", "values": ["bad"]}]) is None


def test_refine_filters_and_temporal_result() -> None:
    payload = {
        "filters": [
            {"key": "date_from", "values": ["2025-01-01"]},
            {"key": "date_to", "values": ["2025-12-31"]},
        ],
        "granularity": "month",
    }
    refined = nq._refine_query_payload_filters_with_question(
        "entre marzo y agosto de 2025",
        payload,
    )
    assert refined["filters"]

    result = {
        "series": [
            {
                "kpi_key": "surgery_volume",
                "points": [
                    {"period": "2025-01", "value": 1},
                    {"period": "2025-03", "value": 2},
                ],
            }
        ]
    }
    refined_result = nq._refine_result_with_question_temporal_hints(
        "en el primer trimestre",
        result,
    )
    assert isinstance(refined_result, dict)

    assert nq._detect_quarter_number("primer trimestre") == 1
    assert nq._detect_quarter_number("tercer trimestre") == 3
    assert nq._detect_quarter_number("nada") is None
    assert nq._extract_period_year_month("2025-04") == (2025, 4)
    assert nq._extract_period_year_month("bad") is None


def test_build_response_and_auto_kpi_helpers() -> None:
    response = nq._build_response(
        question="q",
        resolved=True,
        source="rules",
        intent="trend",
        metric="surgery_volume",
        endpoint="/api/v1/kpis/query",
        translated_payload={"metric": "surgery_volume"},
        assumptions=[],
        result={"series": []},
        errors=[],
        query_payload={"kpi_keys": ["surgery_volume"]},
        explanation="ok",
        auto_kpi=None,
    )
    assert response.success is True
    assert response.endpoint_used == "/api/v1/kpis/query"

    assert nq._resolve_auto_kpi_mode() in {"off", "suggest_only", "auto_create", "human_approve"}
    assert nq._can_approve_auto_kpi({"role": "admin"}) in {True, False}
    assert nq._should_try_auto_kpi(
        {"metric": "__unmapped_metric__", "intent": "trend"},
        {"series": []},
    ) in {True, False}


def test_execute_internal_query_dispatch() -> None:
    kpi = MagicMock()
    kpi.query.return_value = {"series": []}
    analytics = MagicMock()
    analytics.query.return_value = {"rows": []}

    nq._execute_internal_query("/api/v1/kpis/query", {"kpi_keys": ["x"]}, kpi, analytics)
    kpi.query.assert_called_once()

    nq._execute_internal_query("/api/v1/analytics/query", {"widget_type": "ranking"}, kpi, analytics)
    analytics.query.assert_called_once()

    with pytest.raises(ValueError):
        nq._execute_internal_query("/nope", {}, kpi, analytics)


def test_safe_record_helpers(tmp_path, monkeypatch) -> None:
    import os
    from app.core.config import get_settings
    from app.services.natural_query_learning_service import NaturalQueryLearningService
    from app.schemas.natural_query import NaturalQueryRequest

    os.environ["NATURAL_QUERY_LEARNING_FILE"] = str(tmp_path / "l.jsonl")
    os.environ["NATURAL_QUERY_TRAINING_EXPORT_FILE"] = str(tmp_path / "e.jsonl")
    os.environ["NATURAL_QUERY_AUTO_FEEDBACK_MODE"] = "all_resolved"
    get_settings.cache_clear()
    service = NaturalQueryLearningService()
    response = nq._build_response(
        question="espera promedio",
        resolved=True,
        source="rules",
        intent="trend",
        metric="avg_wait_days",
        endpoint="/api/v1/kpis/query",
        translated_payload={"metric": "avg_wait_days"},
        assumptions=[],
        result={},
        errors=[],
        query_payload={},
        explanation="x",
        auto_kpi=None,
    )
    nq._safe_record_interaction(service, response, NaturalQueryRequest(question="espera promedio"))
    nq._safe_record_auto_feedback(service, response, {"sub": "u", "role": "r"}, gateway_confidence=0.95)
    assert nq._resolve_auto_feedback_mode() == "all_resolved"
