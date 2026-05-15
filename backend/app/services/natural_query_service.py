from __future__ import annotations

import re
from datetime import UTC, datetime


class NaturalQueryService:
    """Translates simple natural-language prompts into backend query payloads."""

    def build_query_plan(self, question: str) -> dict[str, object]:
        normalized = self._normalize(question)
        assumptions: list[str] = []

        metric_key = self._detect_metric_key(normalized)
        granularity = self._detect_granularity(normalized)
        filters = self._detect_date_filters(normalized, assumptions)

        if "top" in normalized or "ranking" in normalized:
            payload: dict[str, object] = {
                "widget_type": "ranking",
                "metric_key": metric_key,
                "granularity": granularity,
                "limit": 5,
                "filters": filters,
            }
            return {
                "intent": "ranking",
                "endpoint_used": "/api/v1/analytics/query",
                "payload": payload,
                "assumptions": assumptions,
                "explanation": "Interprete la consulta como ranking/top sobre una metrica.",
            }

        payload = {
            "kpi_keys": [metric_key],
            "granularity": granularity,
            "filters": filters,
        }
        return {
            "intent": "trend",
            "endpoint_used": "/api/v1/kpis/query",
            "payload": payload,
            "assumptions": assumptions,
            "explanation": "Interprete la consulta como tendencia de un KPI en el tiempo.",
        }

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower()
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
        return lowered

    @staticmethod
    def _detect_granularity(normalized: str) -> str:
        if any(word in normalized for word in ["diario", "dia", "dias"]):
            return "day"
        if any(word in normalized for word in ["semanal", "semana", "semanas"]):
            return "week"
        return "month"

    @staticmethod
    def _detect_metric_key(normalized: str) -> str:
        if "reinterv" in normalized:
            return "reintervenciones_mensual"
        if "espera" in normalized or "demora" in normalized:
            return "avg_wait_days"
        if "mortal" in normalized or "fallec" in normalized:
            return "mortality_egreso_pct"
        if "particip" in normalized and "ptca" in normalized:
            return "ptca_share_pct"
        if "ptca" in normalized:
            return "ptca_volume"
        if "hemodinam" in normalized:
            return "hemodinamia_volumen_mensual"
        if "centro" in normalized and "top" in normalized:
            return "top_centro_por_periodo"
        if "centro" in normalized:
            return "centros_que_envian_pacientes"
        if "cirug" in normalized:
            return "surgery_volume"
        if "volumen" in normalized and "total" in normalized:
            return "volumen_mensual_total"
        return "surgery_volume"

    @staticmethod
    def _detect_date_filters(normalized: str, assumptions: list[str]) -> list[dict[str, list[str]]]:
        current_year = datetime.now(UTC).year

        if "este ano" in normalized:
            assumptions.append("Asumi rango desde el inicio del ano actual hasta fin de ano.")
            return [
                {"key": "date_from", "values": [f"{current_year}-01-01"]},
                {"key": "date_to", "values": [f"{current_year}-12-31"]},
            ]

        years = re.findall(r"\b(20\d{2})\b", normalized)
        if years:
            start_year = min(years)
            end_year = max(years)
            assumptions.append(f"Asumi rango {start_year}-01-01 a {end_year}-12-31 detectado en la pregunta.")
            return [
                {"key": "date_from", "values": [f"{start_year}-01-01"]},
                {"key": "date_to", "values": [f"{end_year}-12-31"]},
            ]

        assumptions.append("Sin fechas explicitas: se consulta todo el historico disponible.")
        return []
