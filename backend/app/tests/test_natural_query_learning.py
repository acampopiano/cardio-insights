import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def _get_token(username: str = "dcaraballo", password: str = "Demo1234!") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_natural_query_learning_feedback_and_export(tmp_path: Path) -> None:
    learning_file = tmp_path / "natural_query_learning.jsonl"
    export_file = tmp_path / "natural_query_training_dataset.jsonl"

    os.environ["REPOSITORY_BACKEND"] = "mock"
    os.environ["LLM_GATEWAY_ENABLED"] = "false"
    os.environ["NATURAL_QUERY_LEARNING_FILE"] = str(learning_file)
    os.environ["NATURAL_QUERY_TRAINING_EXPORT_FILE"] = str(export_file)
    get_settings.cache_clear()

    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    run_response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "Como viene la espera promedio este ano?"},
        headers=headers,
    )
    assert run_response.status_code == 200
    run_data = run_response.json()
    interaction_id = run_data.get("interaction_id")
    assert interaction_id

    feedback_response = client.post(
        "/api/v1/natural-query/feedback",
        json={
            "interaction_id": interaction_id,
            "accepted": True,
            "corrected_intent": "trend",
            "corrected_metric": "avg_wait_days",
            "corrected_endpoint": "/api/v1/kpis/query",
            "corrected_translated_payload": {
                "intent": "trend",
                "metric": "avg_wait_days",
                "granularity": "month",
                "period": {"type": "current_year"},
            },
            "notes": "Ejemplo validado por analista.",
        },
        headers=headers,
    )
    assert feedback_response.status_code == 200
    assert feedback_response.json()["recorded"] is True

    export_response = client.post(
        "/api/v1/natural-query/training/export?approved_only=true",
        headers=headers,
    )
    assert export_response.status_code == 200
    export_data = export_response.json()
    assert export_data["total_samples"] >= 1

    exported_path = Path(export_data["export_path"])
    assert exported_path.exists()
    assert exported_path.read_text(encoding="utf-8").strip()


def test_natural_query_auto_feedback_exporta_sin_feedback_manual(tmp_path: Path) -> None:
    learning_file = tmp_path / "natural_query_learning.jsonl"
    export_file = tmp_path / "natural_query_training_dataset.jsonl"

    os.environ["REPOSITORY_BACKEND"] = "mock"
    os.environ["LLM_GATEWAY_ENABLED"] = "false"
    os.environ["NATURAL_QUERY_LEARNING_FILE"] = str(learning_file)
    os.environ["NATURAL_QUERY_TRAINING_EXPORT_FILE"] = str(export_file)
    os.environ["NATURAL_QUERY_AUTO_FEEDBACK_MODE"] = "all_resolved"
    get_settings.cache_clear()

    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    run_response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "Como viene la espera promedio este ano?"},
        headers=headers,
    )
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert run_data.get("interaction_id")

    export_response = client.post(
        "/api/v1/natural-query/training/export?approved_only=true",
        headers=headers,
    )
    assert export_response.status_code == 200
    export_data = export_response.json()
    assert export_data["total_samples"] >= 1

    exported_path = Path(export_data["export_path"])
    assert exported_path.exists()
    assert exported_path.read_text(encoding="utf-8").strip()
