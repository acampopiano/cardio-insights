from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.main import app


def _load_samples(dataset_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("El dataset debe ser una lista JSON.")
    return [item for item in payload if isinstance(item, dict) and item.get("question")]


def _build_feedback_payload(
    interaction_id: str,
    sample: dict[str, Any],
    question: str,
    fallback_metric: str,
) -> dict[str, Any]:
    expected_payload = sample.get("expected_payload")
    if not isinstance(expected_payload, dict):
        expected_payload = {}

    metric = str(expected_payload.get("metric") or fallback_metric or "").strip()
    intent = str(sample.get("intent") or expected_payload.get("intent") or "trend").strip().lower()
    endpoint = str(sample.get("endpoint") or "/api/v1/kpis/query").strip()

    corrected_payload = dict(expected_payload)
    if "intent" not in corrected_payload:
        corrected_payload["intent"] = intent
    if metric and "metric" not in corrected_payload:
        corrected_payload["metric"] = metric

    return {
        "interaction_id": interaction_id,
        "question": question,
        "accepted": True,
        "corrected_intent": intent,
        "corrected_metric": metric,
        "corrected_endpoint": endpoint,
        "corrected_translated_payload": corrected_payload,
        "notes": f"bootstrap_mvp_sample_id={sample.get('id')}",
    }


def _maybe_generate_variants(question: str, enable_augmentation: bool) -> list[str]:
    if not enable_augmentation:
        return [question]

    variants = {question}
    normalized = question.strip()
    variants.add(normalized.replace("Como viene", "Cual es la tendencia de"))
    variants.add(normalized.replace("Mostrame", "Mostrar"))
    variants.add(normalized.replace("este ano", "en el ano actual"))
    variants.add(normalized.replace("?", ""))

    cleaned = [item.strip() for item in variants if item and item.strip()]
    # Preserva orden estable para reproducibilidad.
    return list(dict.fromkeys(cleaned))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap rapido de dataset de entrenamiento NL2KPI.")
    parser.add_argument(
        "--dataset",
        default="docs/natural-query-examples-mvp.json",
        help="Ruta al dataset base de preguntas.",
    )
    parser.add_argument(
        "--username",
        default="dcaraballo",
        help="Usuario para login API.",
    )
    parser.add_argument(
        "--password",
        default="Demo1234!",
        help="Password para login API.",
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        help="Genera variantes simples de cada pregunta para aumentar volumen rapido.",
    )
    parser.add_argument(
        "--use-mock",
        action="store_true",
        help="Fuerza REPOSITORY_BACKEND=mock durante la corrida.",
    )
    args = parser.parse_args()

    if args.use_mock:
        os.environ["REPOSITORY_BACKEND"] = "mock"

    get_settings.cache_clear()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = BACKEND_ROOT / dataset_path

    samples = _load_samples(dataset_path)
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": args.username, "password": args.password},
    )
    if login_response.status_code != 200:
        raise RuntimeError(f"Login fallido: status={login_response.status_code} body={login_response.text}")

    token = login_response.json().get("access_token")
    if not token:
        raise RuntimeError("No se obtuvo access_token.")

    headers = {"Authorization": f"Bearer {token}"}

    total_runs = 0
    recorded_feedback = 0
    skipped = 0

    for sample in samples:
        base_question = str(sample.get("question") or "").strip()
        if not base_question:
            skipped += 1
            continue

        for question in _maybe_generate_variants(base_question, enable_augmentation=args.augment):
            run_response = client.post(
                "/api/v1/natural-query/run",
                json={"question": question, "use_llm_fallback": True},
                headers=headers,
            )
            total_runs += 1

            if run_response.status_code != 200:
                skipped += 1
                continue

            run_data = run_response.json()
            interaction_id = str(run_data.get("interaction_id") or "").strip()
            if not interaction_id:
                skipped += 1
                continue

            feedback_payload = _build_feedback_payload(
                interaction_id=interaction_id,
                sample=sample,
                question=question,
                fallback_metric=str(run_data.get("metric") or ""),
            )
            feedback_response = client.post(
                "/api/v1/natural-query/feedback",
                json=feedback_payload,
                headers=headers,
            )
            if feedback_response.status_code == 200:
                recorded_feedback += 1
            else:
                skipped += 1

    export_response = client.post(
        "/api/v1/natural-query/training/export?approved_only=true",
        headers=headers,
    )
    if export_response.status_code != 200:
        raise RuntimeError(
            f"Export fallido: status={export_response.status_code} body={export_response.text}"
        )

    export_data = export_response.json()

    print(
        json.dumps(
            {
                "total_samples_input": len(samples),
                "total_runs": total_runs,
                "recorded_feedback": recorded_feedback,
                "skipped": skipped,
                "export": export_data,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
