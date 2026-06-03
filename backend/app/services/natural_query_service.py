from __future__ import annotations

import json
import re
import unicodedata
from calendar import monthrange
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path


class NaturalQueryService:
    """Translates simple natural-language prompts into backend query payloads."""

    def build_query_plan(self, question: str) -> dict[str, object]:
        normalized = self._normalize(question)
        assumptions: list[str] = []

        matched_metric_key = self._match_metric_key(normalized)
        metric_key = matched_metric_key or "__unmapped_metric__"
        granularity = self._detect_granularity(normalized)
        filters = self._detect_date_filters(normalized, assumptions)
        auto_kpi_candidate = self.build_auto_kpi_design(question, granularity)
        if metric_key == "__unmapped_metric__":
            inferred_metric = self._infer_metric_for_meta_question(normalized)
            if inferred_metric is not None:
                metric_key = inferred_metric
                assumptions.append(
                    f"No se detectó métrica explícita: se asumió '{inferred_metric}' como proxy de deterioro."
                )
        if metric_key == "__unmapped_metric__" and auto_kpi_candidate is not None:
            assumptions.append("Métrica no mapeada: se intentará creación automática de KPI.")

        if self._is_ranking_intent(normalized):
            ranking_filters = filters
            if not ranking_filters:
                current_year = datetime.now(UTC).year
                ranking_filters = [
                    {"key": "date_from", "values": [f"{current_year}-01-01"]},
                    {"key": "date_to", "values": [f"{current_year}-12-31"]},
                ]
                assumptions.append("Sin fechas explícitas: para ranking se asume el año actual.")

            ranking_limit = 5
            if any(marker in normalized for marker in ["pico", "techo", "maximo", "maxima"]):
                ranking_limit = 1

            payload: dict[str, object] = {
                "widget_type": "ranking",
                "metric_key": matched_metric_key or "surgery_volume",
                "granularity": granularity,
                "limit": ranking_limit,
                "filters": ranking_filters,
            }
            return {
                "intent": "ranking",
                "endpoint_used": "/api/v1/analytics/query",
                "payload": payload,
                "assumptions": assumptions,
                "explanation": "Interpreté la consulta como ranking/top sobre una métrica.",
                "auto_kpi_candidate": None,
            }

        payload = {
            "kpi_keys": [metric_key],
            "granularity": granularity,
            "filters": filters,
        }
        trend_explanation = "Interpreté la consulta como tendencia de un KPI en el tiempo."
        if (
            granularity == "year"
            and re.search(r"\b20\d{2}\b", normalized)
            and ("total" in normalized or "acumulado" in normalized)
        ):
            assumptions.append("Se detectó pedido de total anual: se agregará por año.")
            trend_explanation = "Interpreté la consulta como total anual agregado para el período solicitado."
        if metric_key == "ptca_share_pct":
            trend_explanation = (
                "Interpreté la consulta como tendencia de participación de PTCA "
                "(ptca_share_pct) en el tiempo."
            )
        return {
            "intent": "trend",
            "endpoint_used": "/api/v1/kpis/query",
            "payload": payload,
            "assumptions": assumptions,
            "explanation": trend_explanation,
            "auto_kpi_candidate": auto_kpi_candidate,
        }

    def build_auto_kpi_design(self, question: str, granularity: str) -> dict[str, str] | None:
        normalized = self._normalize(question)
        rules = self._rules()
        auto_rules = rules.get("auto_kpi", {})
        wait_peak_tokens = auto_rules.get("wait_peak_tokens", [])
        total_volume_tokens = auto_rules.get("total_volume_tokens", [])

        if (
            "espera maxima" in normalized
            or "maxima espera" in normalized
            or "mayor espera" in normalized
            or any(token in normalized for token in wait_peak_tokens)
        ):
            return {
                "kpi_name": "Espera máxima en días",
                "description": "Máximo de días de espera entre coordinación y realizado por período.",
                "granularity": granularity,
                "sql_query": (
                    "SELECT {period_expr} AS period, "
                    "MAX(DATEDIFF(f.FechaRealizado, f.FechaCoordina)) AS value "
                    "FROM flow_coordina f "
                    "WHERE f.Realizado = 255 "
                    "AND f.FechaRealizado > '1900-01-01' "
                    "AND f.FechaCoordina > '1900-01-01' "
                    "AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0 "
                    "{date_clause} "
                    "GROUP BY {period_expr} ORDER BY period"
                ),
            }
        if total_volume_tokens and all(token in normalized for token in total_volume_tokens):
            return {
                "kpi_name": "Volumen mensual total",
                "description": "Cantidad total de actividad realizada por período.",
                "granularity": granularity,
                "sql_query": (
                    "SELECT {period_expr} AS period, COUNT(*) AS value "
                    "FROM flow_coordina f "
                    "WHERE f.Realizado = 255 {date_clause} "
                    "GROUP BY {period_expr} ORDER BY period"
                ),
            }
        return None

    @staticmethod
    def _is_ranking_intent(normalized: str) -> bool:
        rules = NaturalQueryService._rules()
        ranking_rules = rules.get("ranking", {})
        peak_markers = ranking_rules.get("peak_markers", ["pico", "techo", "maximo", "maxima"])
        question_markers = ranking_rules.get(
            "question_markers", ["en que", "cual", "cuando", "que dia", "que mes"]
        )
        death_markers = ranking_rules.get("death_markers", ["mur", "fallec", "mortal"])
        default_markers = ranking_rules.get(
            "default_markers",
            [
                "top",
                "ranking",
                "cuales son los",
                "que meses tuvieron",
                "cuales fueron los meses",
                "mes estuvimos peor",
                "peor con las demoras",
                "mayor",
                "mas pacientes",
                "mas cirug",
                "mas ptca",
            ],
        )

        if (
            "en que dia" in normalized
            and ("mas" in normalized or "mayor" in normalized)
            and any(token in normalized for token in death_markers)
        ):
            return True

        if (
            any(token in normalized for token in peak_markers)
            and any(token in normalized for token in question_markers)
        ):
            return True

        if "en que mes" in normalized and (
            "peor" in normalized or "mas" in normalized or "mayor" in normalized
        ):
            return True

        return any(marker in normalized for marker in default_markers)

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
        return unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")

    @staticmethod
    def _detect_granularity(normalized: str) -> str:
        rules = NaturalQueryService._rules()
        granularity_rules = rules.get("granularity", {})
        day_tokens = granularity_rules.get("day_tokens", ["diario", "dia", "dias"])
        week_tokens = granularity_rules.get("week_tokens", ["semanal", "semana", "semanas"])
        month_tokens = granularity_rules.get("month_tokens", ["mensual", "mes", "meses"])
        year_tokens = granularity_rules.get("year_tokens", ["anual", "anio", "anios", "ejercicio"])
        metric_rules = rules.get("metrics", {})
        readmission_tokens = metric_rules.get("readmission_tokens", ["reingres", "readmis"])

        # "reingreso a 30 dias" describe la metrica, no la granularidad de salida.
        if any(token in normalized for token in readmission_tokens):
            day_tokens = [token for token in day_tokens if token not in {"dia", "dias"}]

        if any(word in normalized for word in day_tokens):
            return "day"
        if any(word in normalized for word in week_tokens):
            return "week"
        if any(word in normalized for word in month_tokens):
            return "month"
        if any(word in normalized for word in year_tokens):
            return "year"

        surgery_tokens = metric_rules.get("surgery_tokens", ["cirug"])

        has_explicit_year = re.search(r"\b20\d{2}\b", normalized) is not None
        asks_total = "total" in normalized or "acumulado" in normalized
        mentions_surgery = any(token in normalized for token in surgery_tokens)
        if has_explicit_year and asks_total and mentions_surgery:
            return "year"

        return "month"

    @staticmethod
    def _detect_metric_key(normalized: str) -> str:
        matched = NaturalQueryService._match_metric_key(normalized)
        if matched is not None:
            return matched
        return "surgery_volume"

    @staticmethod
    def _infer_metric_for_meta_question(normalized: str) -> str | None:
        deterioration_tokens = {"deterioro", "empeor", "peor", "degrada", "critico"}
        if "kpi" in normalized and any(token in normalized for token in deterioration_tokens):
            return "avg_wait_days"
        return None

    @staticmethod
    def _match_metric_key(normalized: str) -> str | None:
        rules = NaturalQueryService._rules()
        metric_rules = rules.get("metrics", {})

        if any(token in normalized for token in metric_rules.get("readmission_tokens", ["reingres", "readmis"])):
            return "readmission_30d"
        if any(token in normalized for token in metric_rules.get("reintervenciones_tokens", ["reinterv"])):
            return "reintervenciones_mensual"
        if (
            "espera maxima" in normalized
            or "maxima espera" in normalized
            or "mayor espera" in normalized
        ):
            return None
        if any(token in normalized for token in metric_rules.get("wait_tokens", ["espera", "demora"])):
            return "avg_wait_days"
        if any(token in normalized for token in metric_rules.get("death_count_tokens", ["mur", "muert"])):
            return "mortality_egreso_count"
        if any(token in normalized for token in metric_rules.get("mortality_tokens", ["mortal", "fallec"])):
            return "mortality_egreso_pct"
        ptca_share_patterns = metric_rules.get(
            "ptca_share_patterns",
            [["particip", "ptca"], ["porcentaje", "ptca"], ["proporcion", "ptca"]],
        )
        ptca_share_phrases = metric_rules.get("ptca_share_phrases", ["corresponden a ptca"])
        if any(all(token in normalized for token in pattern) for pattern in ptca_share_patterns) or any(
            phrase in normalized for phrase in ptca_share_phrases
        ):
            return "ptca_share_pct"
        if any(token in normalized for token in metric_rules.get("ptca_tokens", ["ptca"])):
            return "ptca_volume"
        if any(token in normalized for token in metric_rules.get("hemodinamia_tokens", ["hemodinam"])):
            return "hemodinamia_volumen_mensual"
        center_top_tokens = metric_rules.get("center_top_tokens", ["centro", "top"])
        if center_top_tokens and all(token in normalized for token in center_top_tokens):
            return "top_centro_por_periodo"
        if any(token in normalized for token in metric_rules.get("center_tokens", ["centro"])):
            return "centros_que_envian_pacientes"
        if any(token in normalized for token in metric_rules.get("surgery_tokens", ["cirug"])):
            return "surgery_volume"
        return None

    @staticmethod
    def _detect_date_filters(normalized: str, assumptions: list[str]) -> list[dict[str, list[str]]]:
        current_year = datetime.now(UTC).year
        now_utc = datetime.now(UTC).date()
        month_range = NaturalQueryService._detect_month_range(normalized)
        month_number = NaturalQueryService._detect_month_number(normalized)
        years = re.findall(r"\b(20\d{2})\b", normalized)

        last_n_days = NaturalQueryService._detect_last_n_days(normalized)
        if last_n_days is not None:
            days = max(1, min(last_n_days, 3650))
            date_to = now_utc
            date_from = date_to.fromordinal(date_to.toordinal() - days + 1)
            assumptions.append(f"Asumí ventana de últimos {days} días.")
            return [
                {"key": "date_from", "values": [date_from.isoformat()]},
                {"key": "date_to", "values": [date_to.isoformat()]},
            ]

        quarter_window = NaturalQueryService._detect_quarter_comparison_window(normalized)
        if quarter_window is not None:
            from_year, from_month, to_year, to_month = quarter_window
            end_day = monthrange(to_year, to_month)[1]
            assumptions.append("Asumí comparación por trimestre entre años detectados.")
            return [
                {"key": "date_from", "values": [f"{from_year}-{from_month:02d}-01"]},
                {"key": "date_to", "values": [f"{to_year}-{to_month:02d}-{end_day:02d}"]},
            ]

        if month_range is not None and years:
            selected_year = int(min(years))
            start_month, end_month = month_range
            if start_month > end_month:
                start_month, end_month = end_month, start_month
            end_day = monthrange(selected_year, end_month)[1]
            assumptions.append("Asumí rango entre meses explícitos en el año detectado.")
            return [
                {"key": "date_from", "values": [f"{selected_year}-{start_month:02d}-01"]},
                {"key": "date_to", "values": [f"{selected_year}-{end_month:02d}-{end_day:02d}"]},
            ]

        if month_range is not None and "ano pasado" in normalized:
            selected_year = current_year - 1
            start_month, end_month = month_range
            if start_month > end_month:
                start_month, end_month = end_month, start_month
            end_day = monthrange(selected_year, end_month)[1]
            assumptions.append("Asumí rango entre meses explícitos en el año pasado.")
            return [
                {"key": "date_from", "values": [f"{selected_year}-{start_month:02d}-01"]},
                {"key": "date_to", "values": [f"{selected_year}-{end_month:02d}-{end_day:02d}"]},
            ]

        if month_range is not None:
            start_month, end_month = month_range
            if start_month > end_month:
                start_month, end_month = end_month, start_month
            end_day = monthrange(current_year, end_month)[1]
            assumptions.append("Asumí rango entre meses explícitos en el año actual.")
            return [
                {"key": "date_from", "values": [f"{current_year}-{start_month:02d}-01"]},
                {"key": "date_to", "values": [f"{current_year}-{end_month:02d}-{end_day:02d}"]},
            ]

        if month_number is not None and years:
            selected_year = int(min(years))
            last_day = monthrange(selected_year, month_number)[1]
            assumptions.append("Asumí rango del mes solicitado en el año detectado.")
            return [
                {"key": "date_from", "values": [f"{selected_year}-{month_number:02d}-01"]},
                {"key": "date_to", "values": [f"{selected_year}-{month_number:02d}-{last_day:02d}"]},
            ]

        if "ano pasado" in normalized and month_number is not None:
            previous_year = current_year - 1
            last_day = monthrange(previous_year, month_number)[1]
            assumptions.append("Asumí rango del mes solicitado en el año pasado.")
            return [
                {"key": "date_from", "values": [f"{previous_year}-{month_number:02d}-01"]},
                {"key": "date_to", "values": [f"{previous_year}-{month_number:02d}-{last_day:02d}"]},
            ]

        if "ano pasado" in normalized:
            previous_year = current_year - 1
            assumptions.append("Asumí rango del año pasado completo.")
            return [
                {"key": "date_from", "values": [f"{previous_year}-01-01"]},
                {"key": "date_to", "values": [f"{previous_year}-12-31"]},
            ]

        if "este ano" in normalized:
            assumptions.append("Asumí rango desde el inicio del año actual hasta fin de año.")
            return [
                {"key": "date_from", "values": [f"{current_year}-01-01"]},
                {"key": "date_to", "values": [f"{current_year}-12-31"]},
            ]

        if years:
            start_year = min(years)
            end_year = max(years)
            assumptions.append(
                f"Asumí rango {start_year}-01-01 a {end_year}-12-31 detectado en la pregunta."
            )
            return [
                {"key": "date_from", "values": [f"{start_year}-01-01"]},
                {"key": "date_to", "values": [f"{end_year}-12-31"]},
            ]

        assumptions.append("Sin fechas explícitas: se consulta todo el histórico disponible.")
        return []

    @staticmethod
    def _detect_month_number(normalized: str) -> int | None:
        month_map = NaturalQueryService._rules().get("month_map", {})
        for month_name, month_number in month_map.items():
            if month_name in normalized:
                return int(month_number)
        return None

    @staticmethod
    def _detect_month_range(normalized: str) -> tuple[int, int] | None:
        month_map = NaturalQueryService._rules().get("month_map", {})
        if not isinstance(month_map, dict) or not month_map:
            return None

        month_names = [str(name) for name in month_map.keys() if str(name).strip()]
        if not month_names:
            return None

        month_pattern = "|".join(sorted((re.escape(name) for name in month_names), key=len, reverse=True))
        range_patterns = [
            re.compile(rf"\bentre\s+(?P<m1>{month_pattern})\s+y\s+(?P<m2>{month_pattern})\b"),
            re.compile(rf"\bde\s+(?P<m1>{month_pattern})\s+a\s+(?P<m2>{month_pattern})\b"),
        ]

        for pattern in range_patterns:
            match = pattern.search(normalized)
            if not match:
                continue
            m1_name = str(match.group("m1") or "").strip()
            m2_name = str(match.group("m2") or "").strip()
            if m1_name not in month_map or m2_name not in month_map:
                continue
            return int(month_map[m1_name]), int(month_map[m2_name])

        return None

    @staticmethod
    def _detect_quarter_comparison_window(normalized: str) -> tuple[int, int, int, int] | None:
        if "trimestre" not in normalized:
            return None

        quarter_map = {
            "primer": 1,
            "primero": 1,
            "1er": 1,
            "1ro": 1,
            "segundo": 2,
            "2do": 2,
            "tercer": 3,
            "tercero": 3,
            "3er": 3,
            "cuarto": 4,
            "4to": 4,
        }
        quarter_value: int | None = None
        for token, value in quarter_map.items():
            if f"{token} trimestre" in normalized:
                quarter_value = value
                break
        if quarter_value is None:
            return None

        years = sorted({int(value) for value in re.findall(r"\b(20\d{2})\b", normalized)})
        if len(years) < 2:
            return None

        first_year = years[0]
        last_year = years[-1]
        start_month = (quarter_value - 1) * 3 + 1
        end_month = start_month + 2
        return first_year, start_month, last_year, end_month

    @staticmethod
    def _detect_last_n_days(normalized: str) -> int | None:
        patterns = [
            re.compile(r"\bultimos\s+(\d{1,4})\s+dias\b"),
            re.compile(r"\bultimo[s]?\s+(\d{1,4})\s+dias\b"),
            re.compile(r"\blast\s+(\d{1,4})\s+days\b"),
        ]
        for pattern in patterns:
            match = pattern.search(normalized)
            if match:
                return int(match.group(1))
        if "ultimos noventa dias" in normalized:
            return 90
        return None

    @staticmethod
    def _default_rules() -> dict[str, object]:
        return {
            "month_map": {
                "enero": 1,
                "febrero": 2,
                "marzo": 3,
                "abril": 4,
                "mayo": 5,
                "junio": 6,
                "julio": 7,
                "agosto": 8,
                "septiembre": 9,
                "setiembre": 9,
                "octubre": 10,
                "noviembre": 11,
                "diciembre": 12,
            },
            "granularity": {
                "day_tokens": ["diario", "dia", "dias"],
                "week_tokens": ["semanal", "semana", "semanas"],
            },
            "ranking": {
                "peak_markers": ["pico", "techo", "maximo", "maxima"],
                "question_markers": ["en que", "cual", "cuando", "que dia", "que mes"],
                "death_markers": ["mur", "fallec", "mortal"],
                "default_markers": [
                    "top",
                    "ranking",
                    "cuales son los",
                    "que meses tuvieron",
                    "cuales fueron los meses",
                    "mes estuvimos peor",
                    "peor con las demoras",
                    "mayor",
                    "mas pacientes",
                    "mas cirug",
                    "mas ptca",
                ],
            },
            "metrics": {
                "readmission_tokens": ["reingres", "readmis"],
                "reintervenciones_tokens": ["reinterv"],
                "wait_tokens": ["espera", "demora"],
                "death_count_tokens": ["mur", "muert"],
                "mortality_tokens": ["mortal", "fallec"],
                "ptca_share_patterns": [["particip", "ptca"], ["porcentaje", "ptca"], ["proporcion", "ptca"]],
                "ptca_share_phrases": ["corresponden a ptca"],
                "ptca_tokens": ["ptca"],
                "hemodinamia_tokens": ["hemodinam"],
                "center_top_tokens": ["centro", "top"],
                "center_tokens": ["centro"],
                "surgery_tokens": ["cirug", "quirurg"],
            },
            "auto_kpi": {
                "wait_peak_tokens": ["espera maxima", "maxima espera", "mayor espera"],
                "total_volume_tokens": ["volumen", "total"],
            },
        }

    @staticmethod
    @lru_cache
    def _rules() -> dict[str, object]:
        defaults = NaturalQueryService._default_rules()

        backend_root = Path(__file__).resolve().parents[2]
        repo_root = Path(__file__).resolve().parents[3]

        # New scalable layout: split rules by domain.
        rules_dirs = [
            backend_root / "docs" / "natural-query-rules",
            repo_root / "docs" / "natural-query-rules",
        ]
        split_files = ["temporal.json", "intent.json", "metrics.json"]

        merged = dict(defaults)

        def merge_loaded(loaded: dict[str, object]) -> None:
            for key, value in loaded.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged_section = dict(merged[key])
                    merged_section.update(value)
                    merged[key] = merged_section
                else:
                    merged[key] = value

        loaded_any = False
        for rules_dir in rules_dirs:
            for file_name in split_files:
                file_path = rules_dir / file_name
                try:
                    loaded = json.loads(file_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        merge_loaded(loaded)
                        loaded_any = True
                except Exception:
                    continue

        if loaded_any:
            return merged

        # Backward compatibility with legacy single-file rules.
        rules_paths = [
            backend_root / "docs" / "natural-query-language-rules.json",
            repo_root / "docs" / "natural-query-language-rules.json",
        ]
        for rules_path in rules_paths:
            try:
                loaded = json.loads(rules_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    continue
                merged = dict(defaults)
                for key, value in loaded.items():
                    if isinstance(value, dict) and isinstance(merged.get(key), dict):
                        merged_section = dict(merged[key])
                        merged_section.update(value)
                        merged[key] = merged_section
                    else:
                        merged[key] = value
                return merged
            except Exception:
                continue
        return defaults
