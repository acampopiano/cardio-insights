from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings


@dataclass
class RunStats:
    total: int = 0
    ok: int = 0
    failed: int = 0
    resolved: int = 0
    unresolved: int = 0
    with_interaction_id: int = 0
    llm_source: int = 0
    rules_source: int = 0


def _resolve_path(raw_path: str) -> Path:
    candidate = Path(str(raw_path or "").strip())
    if candidate.is_absolute():
        return candidate
    return BACKEND_ROOT / candidate


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def _count_learning_types(path: Path) -> dict[str, int]:
    counts = {"interaction": 0, "feedback": 0}
    if not path.exists():
        return counts

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            row_type = str(row.get("type") or "").strip().lower()
            if row_type in counts:
                counts[row_type] += 1

    return counts


def _load_questions(dataset_path: Path, limit: int) -> list[str]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("El dataset debe ser una lista JSON.")

    questions: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if question:
            questions.append(question)
        if len(questions) >= limit:
            break
    return questions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test de aprendizaje NL2KPI con medicion de crecimiento antes/despues."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL base del backend")
    parser.add_argument(
        "--dataset",
        default="docs/natural-query-examples-mvp.json",
        help="Ruta al dataset de preguntas (relativa al backend o absoluta)",
    )
    parser.add_argument("--limit", type=int, default=20, help="Cantidad maxima de preguntas a ejecutar")
    parser.add_argument("--username", default="clinician", help="Usuario para login")
    parser.add_argument("--password", default="Demo1234!", help="Password para login")
    parser.add_argument(
        "--require-growth",
        action="store_true",
        help="Falla con codigo de salida 2 si no crece el dataset exportado.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit debe ser mayor o igual a 1")

    settings = get_settings()
    learning_path = _resolve_path(settings.natural_query_learning_file)
    export_path = _resolve_path(settings.natural_query_training_export_file)

    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = BACKEND_ROOT / dataset_path

    questions = _load_questions(dataset_path, args.limit)
    if not questions:
        raise RuntimeError("No se encontraron preguntas en el dataset.")

    before_learning_lines = _count_lines(learning_path)
    before_export_lines = _count_lines(export_path)
    before_learning_types = _count_learning_types(learning_path)

    stats = RunStats(total=len(questions))

    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": args.username, "password": args.password},
        )
        if login_response.status_code != 200:
            raise RuntimeError(
                f"Login fallido: status={login_response.status_code} body={login_response.text}"
            )

        access_token = str(login_response.json().get("access_token") or "")
        if not access_token:
            raise RuntimeError("No se obtuvo access_token.")

        headers = {"Authorization": f"Bearer {access_token}"}

        for question in questions:
            response = client.post(
                "/api/v1/natural-query/run",
                json={"question": question, "use_llm_fallback": True},
                headers=headers,
            )
            if response.status_code != 200:
                stats.failed += 1
                continue

            stats.ok += 1
            data = response.json()

            if bool(data.get("resolved")):
                stats.resolved += 1
            else:
                stats.unresolved += 1

            if str(data.get("interaction_id") or "").strip():
                stats.with_interaction_id += 1

            source = str(data.get("source") or "").strip().lower()
            if source == "llm":
                stats.llm_source += 1
            elif source == "rules":
                stats.rules_source += 1

        export_response = client.post(
            "/api/v1/natural-query/training/export?approved_only=true",
            headers=headers,
        )
        if export_response.status_code != 200:
            raise RuntimeError(
                f"Export fallido: status={export_response.status_code} body={export_response.text}"
            )

        export_data = export_response.json()

    after_learning_lines = _count_lines(learning_path)
    after_export_lines = _count_lines(export_path)
    after_learning_types = _count_learning_types(learning_path)

    summary = {
        "config": {
            "base_url": args.base_url,
            "dataset": str(dataset_path),
            "limit": args.limit,
            "learning_file": str(learning_path),
            "export_file": str(export_path),
            "auto_feedback_mode": str(settings.natural_query_auto_feedback_mode),
            "auto_feedback_min_confidence": float(settings.natural_query_auto_feedback_min_confidence),
        },
        "runs": {
            "total": stats.total,
            "ok": stats.ok,
            "failed": stats.failed,
            "resolved": stats.resolved,
            "unresolved": stats.unresolved,
            "with_interaction_id": stats.with_interaction_id,
            "llm_source": stats.llm_source,
            "rules_source": stats.rules_source,
        },
        "learning": {
            "before_lines": before_learning_lines,
            "after_lines": after_learning_lines,
            "delta_lines": after_learning_lines - before_learning_lines,
            "before_types": before_learning_types,
            "after_types": after_learning_types,
            "delta_interaction": after_learning_types["interaction"] - before_learning_types["interaction"],
            "delta_feedback": after_learning_types["feedback"] - before_learning_types["feedback"],
        },
        "export": {
            "before_lines": before_export_lines,
            "after_lines": after_export_lines,
            "delta_lines": after_export_lines - before_export_lines,
            "endpoint_result": export_data,
        },
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.require_growth and (after_export_lines - before_export_lines) <= 0:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
