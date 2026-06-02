from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings


class NaturalQueryLearningService:
    """Persistencia de interacciones y feedback para entrenamiento de NL2KPI."""

    def __init__(self) -> None:
        settings = get_settings()
        self._learning_file = self._resolve_path(settings.natural_query_learning_file)
        self._training_export_file = self._resolve_path(settings.natural_query_training_export_file)

    @staticmethod
    def _resolve_path(raw_path: str) -> Path:
        candidate = Path(str(raw_path or "").strip())
        if candidate.is_absolute():
            return candidate
        backend_root = Path(__file__).resolve().parents[2]
        return backend_root / candidate

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def _append_json_line(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _read_json_lines(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                rows.append(data)
        return rows

    def record_interaction(self, payload: dict[str, Any]) -> str:
        interaction_id = str(uuid4())
        row = {
            "type": "interaction",
            "interaction_id": interaction_id,
            "created_at": self._now_iso(),
            **payload,
        }
        self._append_json_line(self._learning_file, row)
        return interaction_id

    def record_feedback(self, payload: dict[str, Any], user_claims: dict[str, Any]) -> str:
        feedback_id = str(uuid4())
        row = {
            "type": "feedback",
            "feedback_id": feedback_id,
            "created_at": self._now_iso(),
            "user": {
                "username": str(user_claims.get("sub") or ""),
                "role": str(user_claims.get("role") or ""),
            },
            **payload,
        }
        self._append_json_line(self._learning_file, row)
        return feedback_id

    @staticmethod
    def _normalize_question(text: str) -> str:
        lowered = str(text or "").lower().strip()
        replacements = {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ñ": "n",
        }
        for old, new in replacements.items():
            lowered = lowered.replace(old, new)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered

    @staticmethod
    def _similarity_score(left: str, right: str) -> float:
        left_n = NaturalQueryLearningService._normalize_question(left)
        right_n = NaturalQueryLearningService._normalize_question(right)
        if not left_n or not right_n:
            return 0.0

        seq_score = SequenceMatcher(None, left_n, right_n).ratio()
        left_tokens = set(left_n.split())
        right_tokens = set(right_n.split())
        if not left_tokens or not right_tokens:
            return seq_score

        intersection = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        token_score = float(intersection / union) if union else 0.0
        return max(seq_score, token_score)

    def recall_approved_plan(self, question: str, min_score: float = 0.88) -> dict[str, Any] | None:
        rows = self._read_json_lines(self._learning_file)
        if not rows:
            return None

        interactions: dict[str, dict[str, Any]] = {}
        feedback_rows: list[dict[str, Any]] = []
        for row in rows:
            row_type = str(row.get("type") or "").lower()
            if row_type == "interaction":
                interaction_id = str(row.get("interaction_id") or "").strip()
                if interaction_id:
                    interactions[interaction_id] = row
            elif row_type == "feedback":
                feedback_rows.append(row)

        best: dict[str, Any] | None = None
        best_score = 0.0
        for feedback in reversed(feedback_rows):
            if not bool(feedback.get("accepted")):
                continue

            interaction_id = str(feedback.get("interaction_id") or "").strip()
            linked_interaction = interactions.get(interaction_id, {})

            sample_question = str(feedback.get("question") or linked_interaction.get("question") or "").strip()
            if not sample_question:
                continue

            score = self._similarity_score(question, sample_question)
            if score < min_score or score < best_score:
                continue

            corrected_payload = feedback.get("corrected_translated_payload")
            if not isinstance(corrected_payload, dict):
                corrected_payload = linked_interaction.get("translated_payload")
            if not isinstance(corrected_payload, dict):
                corrected_payload = {}

            intent = str(
                feedback.get("corrected_intent")
                or linked_interaction.get("intent")
                or corrected_payload.get("intent")
                or ""
            ).strip()
            metric = str(
                feedback.get("corrected_metric")
                or linked_interaction.get("metric")
                or corrected_payload.get("metric")
                or ""
            ).strip()
            endpoint = str(
                feedback.get("corrected_endpoint")
                or linked_interaction.get("endpoint")
                or ""
            ).strip()

            if not intent or not metric or not endpoint:
                continue

            best = {
                "intent": intent,
                "metric": metric,
                "endpoint": endpoint,
                "translated_payload": corrected_payload,
                "matched_question": sample_question,
                "score": round(score, 4),
            }
            best_score = score

        return best

    def export_training_dataset(self, approved_only: bool = True) -> tuple[int, str]:
        rows = self._read_json_lines(self._learning_file)
        interactions: dict[str, dict[str, Any]] = {}
        feedback_rows: list[dict[str, Any]] = []

        for row in rows:
            row_type = str(row.get("type") or "").lower()
            if row_type == "interaction":
                interaction_id = str(row.get("interaction_id") or "")
                if interaction_id:
                    interactions[interaction_id] = row
            elif row_type == "feedback":
                feedback_rows.append(row)

        samples: list[dict[str, Any]] = []
        for feedback in feedback_rows:
            accepted = bool(feedback.get("accepted"))
            if approved_only and not accepted:
                continue

            interaction_id = str(feedback.get("interaction_id") or "")
            linked_interaction = interactions.get(interaction_id, {})
            question = str(feedback.get("question") or linked_interaction.get("question") or "").strip()
            if not question:
                continue

            corrected_payload = feedback.get("corrected_translated_payload")
            if not isinstance(corrected_payload, dict):
                corrected_payload = linked_interaction.get("translated_payload")
            if not isinstance(corrected_payload, dict):
                corrected_payload = {}

            intent = str(
                feedback.get("corrected_intent")
                or linked_interaction.get("intent")
                or corrected_payload.get("intent")
                or ""
            ).strip()
            metric = str(
                feedback.get("corrected_metric")
                or linked_interaction.get("metric")
                or corrected_payload.get("metric")
                or ""
            ).strip()
            endpoint = str(
                feedback.get("corrected_endpoint")
                or linked_interaction.get("endpoint")
                or ""
            ).strip()

            if not intent or not metric or not endpoint:
                continue

            sample = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Traduce preguntas clinicas a contratos NL2KPI sin generar SQL. "
                            "Devuelve intent, metric, endpoint y translated_payload."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                "target": {
                    "resolved": True,
                    "intent": intent,
                    "metric": metric,
                    "endpoint": endpoint,
                    "translated_payload": corrected_payload,
                },
                "metadata": {
                    "accepted": accepted,
                    "interaction_id": interaction_id,
                    "feedback_id": str(feedback.get("feedback_id") or ""),
                    "created_at": str(feedback.get("created_at") or ""),
                },
            }
            samples.append(sample)

        self._training_export_file.parent.mkdir(parents=True, exist_ok=True)
        with self._training_export_file.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, ensure_ascii=False) + "\n")

        return len(samples), str(self._training_export_file)


__all__ = ["NaturalQueryLearningService"]
