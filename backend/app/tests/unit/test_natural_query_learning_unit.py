"""Cobertura unitaria del learning service (memoria / export / validación)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.natural_query_learning_service import NaturalQueryLearningService


@pytest.fixture
def learning(tmp_path: Path) -> NaturalQueryLearningService:
    learning_file = tmp_path / "learning.jsonl"
    export_file = tmp_path / "export.jsonl"
    os.environ["NATURAL_QUERY_LEARNING_FILE"] = str(learning_file)
    os.environ["NATURAL_QUERY_TRAINING_EXPORT_FILE"] = str(export_file)
    get_settings.cache_clear()
    return NaturalQueryLearningService()


def test_resolve_absolute_and_relative(tmp_path: Path) -> None:
    abs_path = tmp_path / "abs.jsonl"
    assert NaturalQueryLearningService._resolve_path(str(abs_path)) == abs_path
    rel = NaturalQueryLearningService._resolve_path("data/foo.jsonl")
    assert rel.name == "foo.jsonl"


def test_normalize_and_similarity() -> None:
    normalized = NaturalQueryLearningService._normalize_question("  ESPERA   Promedio  ")
    assert normalized == "espera promedio"
    assert NaturalQueryLearningService._similarity_score("", "hola") == 0.0
    score = NaturalQueryLearningService._similarity_score(
        "espera promedio este ano",
        "espera promedio este anio",
    )
    assert score > 0.8


def test_is_valid_plan() -> None:
    ok = NaturalQueryLearningService._is_valid_plan(
        "trend",
        "avg_wait_days",
        "/api/v1/kpis/query",
        {"metric": "avg_wait_days"},
    )
    assert ok is True
    assert (
        NaturalQueryLearningService._is_valid_plan(
            "",
            "x",
            "/api/v1/kpis/query",
            {},
        )
        is False
    )
    assert (
        NaturalQueryLearningService._is_valid_plan(
            "trend",
            "__unmapped__",
            "/api/v1/kpis/query",
            {},
        )
        is False
    )
    assert (
        NaturalQueryLearningService._is_valid_plan(
            "trend",
            "avg_wait_days",
            "/api/v1/other",
            {},
        )
        is False
    )
    assert (
        NaturalQueryLearningService._is_valid_plan(
            "weird",
            "avg_wait_days",
            "/api/v1/kpis/query",
            {},
        )
        is False
    )
    assert (
        NaturalQueryLearningService._is_valid_plan(
            "trend",
            "avg_wait_days",
            "/api/v1/kpis/query",
            {"metric": "__unmapped__"},
        )
        is False
    )
    assert (
        NaturalQueryLearningService._is_valid_plan(
            "trend",
            "avg_wait_days",
            "/api/v1/kpis/query",
            {"metric": "other"},
        )
        is False
    )


def test_read_json_lines_skips_bad(learning: NaturalQueryLearningService, tmp_path: Path) -> None:
    path = learning._learning_file
    path.write_text(
        "\nnot-json\n" + json.dumps({"type": "interaction", "interaction_id": "1"}) + "\n",
        encoding="utf-8",
    )
    rows = learning._read_json_lines(path)
    assert len(rows) == 1
    assert learning._read_json_lines(tmp_path / "missing.jsonl") == []


def test_record_and_recall_and_export(learning: NaturalQueryLearningService) -> None:
    iid = learning.record_interaction(
        {
            "question": "Como viene la espera promedio este ano?",
            "intent": "trend",
            "metric": "avg_wait_days",
            "endpoint": "/api/v1/kpis/query",
            "translated_payload": {
                "intent": "trend",
                "metric": "avg_wait_days",
                "granularity": "month",
            },
        }
    )
    learning.record_feedback(
        {
            "interaction_id": iid,
            "accepted": True,
            "question": "Como viene la espera promedio este ano?",
            "corrected_intent": "trend",
            "corrected_metric": "avg_wait_days",
            "corrected_endpoint": "/api/v1/kpis/query",
            "corrected_translated_payload": {
                "intent": "trend",
                "metric": "avg_wait_days",
                "granularity": "month",
            },
        },
        {"sub": "clinician", "role": "clinician"},
    )
    # feedback rechazado / inválido no debe ganar
    learning.record_feedback(
        {
            "interaction_id": "nope",
            "accepted": False,
            "question": "otra cosa",
        },
        {"sub": "clinician", "role": "clinician"},
    )
    learning.record_feedback(
        {
            "interaction_id": "badplan",
            "accepted": True,
            "question": "plan invalido xyz",
            "corrected_intent": "trend",
            "corrected_metric": "__unmapped__",
            "corrected_endpoint": "/api/v1/kpis/query",
        },
        {"sub": "x", "role": "y"},
    )

    assert learning.recall_approved_plan("pregunta sin match", min_score=0.99) is None
    recalled = learning.recall_approved_plan(
        "Como viene la espera promedio este ano?",
        min_score=0.5,
    )
    assert recalled is not None
    assert recalled["metric"] == "avg_wait_days"

    total, path = learning.export_training_dataset(approved_only=True)
    assert total >= 1
    assert Path(path).exists()

    total_all, _ = learning.export_training_dataset(approved_only=False)
    assert total_all >= total


def test_recall_empty_file(learning: NaturalQueryLearningService) -> None:
    assert learning.recall_approved_plan("hola") is None


def test_export_skips_invalid_and_missing_question(learning: NaturalQueryLearningService) -> None:
    learning._append_json_line(
        learning._learning_file,
        {"type": "feedback", "accepted": True, "interaction_id": "x"},
    )
    learning._append_json_line(
        learning._learning_file,
        {
            "type": "feedback",
            "accepted": True,
            "interaction_id": "y",
            "question": "espera promedio",
            "corrected_intent": "trend",
            "corrected_metric": "__unmapped__",
            "corrected_endpoint": "/api/v1/kpis/query",
            "corrected_translated_payload": "not-a-dict",
        },
    )
    total, _ = learning.export_training_dataset(approved_only=True)
    assert total == 0
