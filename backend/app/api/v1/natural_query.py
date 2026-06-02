import re
from calendar import monthrange
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.dependencies import get_analytics_service, get_kpi_service, get_repository
from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.core.security import get_current_claims
from app.repositories.mysql_repository import MySQLRepository
from app.schemas.kpi_designer import KpiDesignRequest
from app.schemas.natural_query import (
    NaturalQueryFeedbackRequest,
    NaturalQueryFeedbackResponse,
    NaturalQueryGatewayResponse,
    NaturalQueryRequest,
    NaturalQueryRunResponse,
    NaturalQueryTrainingExportResponse,
)
from app.services.kpi_designer_service import KpiDesignerService
from app.services.analytics_service import AnalyticsService
from app.services.kpi_service import KpiService
from app.services.llm_gateway_client import LLMGatewayClient
from app.services.natural_query_learning_service import NaturalQueryLearningService
from app.services.natural_query_service import NaturalQueryService

router = APIRouter(prefix="/natural-query", tags=["Natural Query"])


@router.post("/run", response_model=NaturalQueryRunResponse)
def run_natural_query(
    payload: NaturalQueryRequest,
    claims: dict = Depends(get_current_claims),
    kpi_service: KpiService = Depends(get_kpi_service),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    repository: object = Depends(get_repository),
) -> NaturalQueryRunResponse:
    errors: list[str] = []
    learning_service = NaturalQueryLearningService()

    if _online_memory_enabled():
        min_score = float(get_settings().natural_query_online_memory_min_score or 0.88)
        memory_plan = learning_service.recall_approved_plan(payload.question, min_score=min_score)
        if memory_plan is not None:
            try:
                translated_payload = dict(memory_plan.get("translated_payload") or {})
                query_payload = _translated_payload_to_internal_query(
                    endpoint=str(memory_plan.get("endpoint") or ""),
                    intent=str(memory_plan.get("intent") or "trend"),
                    metric=str(memory_plan.get("metric") or ""),
                    translated_payload=translated_payload,
                )
                if query_payload is not None:
                    refined_query_payload = _refine_query_payload_filters_with_question(
                        question=payload.question,
                        query_payload=dict(query_payload),
                    )
                    result = _execute_internal_query(
                        endpoint=str(memory_plan["endpoint"]),
                        query_payload=refined_query_payload,
                        kpi_service=kpi_service,
                        analytics_service=analytics_service,
                    )
                    response = _build_response(
                        question=payload.question,
                        resolved=True,
                        source="llm",
                        intent=str(memory_plan["intent"]),
                        metric=str(memory_plan["metric"]),
                        endpoint=str(memory_plan["endpoint"]),
                        translated_payload=translated_payload,
                        assumptions=[
                            (
                                "Resuelta por memoria online de ejemplos aprobados "
                                f"(similitud={memory_plan.get('score')}, "
                                f"base='{memory_plan.get('matched_question', '')}')."
                            )
                        ],
                        result=result,
                        errors=errors,
                        query_payload=refined_query_payload,
                        explanation="Consulta resuelta por memoria online de aprendizaje continuo.",
                        auto_kpi=None,
                    )
                    _safe_record_interaction(learning_service, response, payload)
                    _safe_record_auto_feedback(
                        service=learning_service,
                        response=response,
                        user_claims=claims,
                        gateway_confidence=1.0,
                    )
                    return response
            except Exception as exc:
                errors.append(f"Memoria online no pudo resolver la consulta: {exc}")

    gateway_execution = _build_gateway_execution_plan(payload, repository)
    errors.extend(gateway_execution["errors"])

    if gateway_execution["plan"] is not None:
        gateway_plan = gateway_execution["plan"]
        try:
            refined_query_payload = _refine_query_payload_filters_with_question(
                question=payload.question,
                query_payload=dict(gateway_plan["query_payload"]),
            )
            result = _execute_internal_query(
                endpoint=str(gateway_plan["endpoint"]),
                query_payload=refined_query_payload,
                kpi_service=kpi_service,
                analytics_service=analytics_service,
            )
            result = _refine_result_with_question_temporal_hints(payload.question, result)
            response = _build_response(
                question=payload.question,
                resolved=True,
                source=str(gateway_plan["source"]),
                intent=str(gateway_plan["intent"]),
                metric=str(gateway_plan["metric"]),
                endpoint=str(gateway_plan["endpoint"]),
                translated_payload=dict(gateway_plan["translated_payload"]),
                assumptions=list(gateway_plan["assumptions"]),
                result=result,
                errors=errors,
                query_payload=refined_query_payload,
                explanation="Consulta resuelta por traduccion del LLM Gateway.",
                auto_kpi=None,
            )
            _safe_record_interaction(learning_service, response, payload)
            _safe_record_auto_feedback(
                service=learning_service,
                response=response,
                user_claims=claims,
                gateway_confidence=gateway_plan.get("confidence"),
            )
            return response
        except Exception as exc:
            errors.append(f"Fallo ejecucion de payload traducido por gateway: {exc}")

    local_result = _run_local_natural_query(
        payload=payload,
        claims=claims,
        kpi_service=kpi_service,
        analytics_service=analytics_service,
        repository=repository,
    )
    local_result.errors.extend(errors)
    _safe_record_interaction(learning_service, local_result, payload)
    _safe_record_auto_feedback(
        service=learning_service,
        response=local_result,
        user_claims=claims,
        gateway_confidence=None,
    )
    return local_result


@router.post("/feedback", response_model=NaturalQueryFeedbackResponse)
def submit_natural_query_feedback(
    payload: NaturalQueryFeedbackRequest,
    claims: dict = Depends(get_current_claims),
) -> NaturalQueryFeedbackResponse:
    if not payload.interaction_id and not payload.question:
        raise HTTPException(
            status_code=400,
            detail="Debes enviar interaction_id o question para registrar feedback.",
        )

    service = NaturalQueryLearningService()
    feedback_id = service.record_feedback(payload.model_dump(), claims)
    return NaturalQueryFeedbackResponse(feedback_id=feedback_id, recorded=True)


@router.post("/training/export", response_model=NaturalQueryTrainingExportResponse)
def export_natural_query_training_dataset(
    approved_only: bool = Query(default=True),
    _: dict = Depends(get_current_claims),
) -> NaturalQueryTrainingExportResponse:
    service = NaturalQueryLearningService()
    total_samples, export_path = service.export_training_dataset(approved_only=approved_only)
    return NaturalQueryTrainingExportResponse(total_samples=total_samples, export_path=export_path)


def _online_memory_enabled() -> bool:
    return bool(get_settings().natural_query_online_memory_enabled)


def _build_gateway_execution_plan(payload: NaturalQueryRequest, repository: object) -> dict[str, object]:
    errors: list[str] = []
    client = LLMGatewayClient()
    if not client.is_enabled():
        return {"plan": None, "errors": errors}

    gateway_response, gateway_error = client.interpret(
        question=payload.question,
        use_llm_fallback=payload.use_llm_fallback,
    )
    if gateway_error is not None:
        errors.append(gateway_error)
        return {"plan": None, "errors": errors}
    if gateway_response is None:
        errors.append("LLM Gateway no devolvio respuesta.")
        return {"plan": None, "errors": errors}

    plan, validation_errors = _validate_and_build_gateway_plan(gateway_response, repository)
    errors.extend(validation_errors)
    return {"plan": plan, "errors": errors}


def _validate_and_build_gateway_plan(
    gateway_response: NaturalQueryGatewayResponse,
    repository: object,
) -> tuple[dict[str, object] | None, list[str]]:
    errors: list[str] = []

    if not gateway_response.resolved:
        errors.append("LLM Gateway no pudo resolver la consulta (resolved=false).")
        return None, errors

    allowed_intents = {"trend", "ranking", "comparison", "alert"}
    allowed_endpoints = {"/api/v1/kpis/query", "/api/v1/analytics/query"}

    intent = str(gateway_response.intent or "").strip().lower()
    endpoint = str(gateway_response.endpoint or "").strip()
    translated_payload = gateway_response.translated_payload.model_dump() if gateway_response.translated_payload else {}
    metric = str(gateway_response.metric or translated_payload.get("metric") or "").strip()
    source = str(gateway_response.source or "rules").strip().lower()
    if source not in {"rules", "llm"}:
        source = "rules"

    if intent not in allowed_intents:
        errors.append(f"Intent invalido desde gateway: {intent or '(vacio)'}")
    if endpoint not in allowed_endpoints:
        errors.append(f"Endpoint invalido desde gateway: {endpoint or '(vacio)'}")
    if not translated_payload:
        errors.append("Gateway no devolvio translated_payload.")
    if not metric:
        errors.append("Gateway no devolvio metrica.")

    unsafe_reason = _detect_unsafe_translated_payload(translated_payload)
    if unsafe_reason is not None:
        errors.append(unsafe_reason)

    if metric and not _metric_exists_in_local_catalog(metric, repository):
        errors.append(f"Metrica no permitida por catalogo local: {metric}")

    if errors:
        return None, errors

    query_payload = _translated_payload_to_internal_query(
        endpoint=endpoint,
        intent=intent,
        metric=metric,
        translated_payload=translated_payload,
    )
    if query_payload is None:
        return None, ["No se pudo traducir translated_payload al contrato interno."]

    plan: dict[str, object] = {
        "source": source,
        "intent": intent,
        "metric": metric,
        "endpoint": endpoint,
        "confidence": gateway_response.confidence,
        "translated_payload": translated_payload,
        "query_payload": query_payload,
        "assumptions": list(gateway_response.assumptions or []),
    }
    return plan, []


def _translated_payload_to_internal_query(
    endpoint: str,
    intent: str,
    metric: str,
    translated_payload: dict[str, object],
) -> dict[str, object] | None:
    granularity = str(translated_payload.get("granularity") or "month").lower()
    if granularity not in {"day", "week", "month", "year"}:
        granularity = "month"

    filters = _extract_filters(translated_payload)

    if endpoint == "/api/v1/kpis/query":
        return {
            "kpi_keys": [metric],
            "granularity": granularity,
            "filters": filters,
        }

    if endpoint == "/api/v1/analytics/query":
        widget_type = "ranking" if intent == "ranking" else "table"
        requested_limit = translated_payload.get("limit")
        limit = 5 if widget_type == "ranking" else 10
        if isinstance(requested_limit, int):
            limit = requested_limit
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100

        return {
            "widget_type": widget_type,
            "metric_key": metric,
            "granularity": granularity,
            "filters": filters,
            "limit": limit,
        }

    return None


def _extract_filters(translated_payload: dict[str, object]) -> list[dict[str, list[str]]]:
    raw_filters = translated_payload.get("filters")
    if isinstance(raw_filters, list):
        normalized_filters: list[dict[str, list[str]]] = []
        for item in raw_filters:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            values = item.get("values")
            if not key or not isinstance(values, list):
                continue
            normalized_values = [str(value) for value in values if str(value).strip()]
            if not normalized_values:
                continue
            normalized_filters.append({"key": key, "values": normalized_values})
        if normalized_filters:
            return normalized_filters

    period = translated_payload.get("period")
    if not isinstance(period, dict):
        return []

    period_type = str(period.get("type") or "").strip().lower()
    current_year = datetime.now(UTC).year

    # Compatibilidad con gateways que devuelven period shorthand sin "type".
    if not period_type:
        has_year = isinstance(period.get("year"), int)
        has_month = isinstance(period.get("month"), int)
        has_date_range = bool(period.get("date_from") or period.get("date_to"))
        if has_year and has_month:
            period_type = "month"
        elif has_year:
            period_type = "year"
        elif has_date_range:
            period_type = "date_range"

    if period_type == "current_year":
        return [
            {"key": "date_from", "values": [f"{current_year}-01-01"]},
            {"key": "date_to", "values": [f"{current_year}-12-31"]},
        ]
    if period_type == "last_year":
        previous_year = current_year - 1
        return [
            {"key": "date_from", "values": [f"{previous_year}-01-01"]},
            {"key": "date_to", "values": [f"{previous_year}-12-31"]},
        ]
    if period_type == "year":
        year = int(period.get("year") or current_year)
        return [
            {"key": "date_from", "values": [f"{year}-01-01"]},
            {"key": "date_to", "values": [f"{year}-12-31"]},
        ]
    if period_type == "month":
        year = int(period.get("year") or current_year)
        month = int(period.get("month") or 1)
        month = min(max(month, 1), 12)
        last_day = monthrange(year, month)[1]
        return [
            {"key": "date_from", "values": [f"{year}-{month:02d}-01"]},
            {"key": "date_to", "values": [f"{year}-{month:02d}-{last_day:02d}"]},
        ]
    if period_type == "date_range":
        date_from = str(period.get("date_from") or "").strip()
        date_to = str(period.get("date_to") or "").strip()
        out: list[dict[str, list[str]]] = []
        if date_from:
            out.append({"key": "date_from", "values": [date_from]})
        if date_to:
            out.append({"key": "date_to", "values": [date_to]})
        return out

    return []


def _refine_query_payload_filters_with_question(
    question: str,
    query_payload: dict[str, object],
) -> dict[str, object]:
    if not isinstance(query_payload, dict):
        return query_payload

    planner = NaturalQueryService()
    plan = planner.build_query_plan(question)
    hinted_payload = plan.get("payload")
    if not isinstance(hinted_payload, dict):
        return query_payload

    hinted_filters = hinted_payload.get("filters")
    if not isinstance(hinted_filters, list) or not hinted_filters:
        return query_payload

    current_filters = query_payload.get("filters")
    if not isinstance(current_filters, list) or not current_filters:
        query_payload["filters"] = hinted_filters
        return query_payload

    if _is_full_year_filter(current_filters) and not _is_full_year_filter(hinted_filters):
        query_payload["filters"] = hinted_filters

    return query_payload


def _is_full_year_filter(filters: list[object]) -> bool:
    date_from: str | None = None
    date_to: str | None = None
    for item in filters:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        values = item.get("values")
        if not isinstance(values, list) or not values:
            continue
        value = str(values[0] or "").strip()
        if key == "date_from":
            date_from = value
        elif key == "date_to":
            date_to = value

    if not date_from or not date_to:
        return False

    from_match = re.fullmatch(r"(20\d{2})-01-01", date_from)
    to_match = re.fullmatch(r"(20\d{2})-12-31", date_to)
    if not from_match or not to_match:
        return False
    return from_match.group(1) == to_match.group(1)


def _detect_unsafe_translated_payload(translated_payload: dict[str, object]) -> str | None:
    if not translated_payload:
        return None

    blocked_key_fragments = {
        "sql",
        "query_sql",
        "raw_sql",
        "statement",
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "join",
        "where",
        "union",
    }
    blocked_sql_tokens = re.compile(r"\b(select|insert|update|delete|drop|union|join|from|where)\b", re.IGNORECASE)

    stack: list[object] = [translated_payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                normalized_key = str(key).strip().lower()
                if any(fragment in normalized_key for fragment in blocked_key_fragments):
                    return f"Payload traducido rechazado por seguridad (clave no permitida: {key})."
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, str):
            if blocked_sql_tokens.search(current):
                return "Payload traducido rechazado por seguridad (contenido SQL detectado)."

    return None


def _metric_exists_in_local_catalog(metric: str, repository: object) -> bool:
    metric = str(metric or "").strip()
    if not metric:
        return False

    if not hasattr(repository, "get_kpis_catalog"):
        return True

    try:
        catalog = repository.get_kpis_catalog()  # type: ignore[attr-defined]
    except Exception:
        return True

    if not isinstance(catalog, dict):
        return True

    items = catalog.get("kpis")
    if not isinstance(items, list):
        return True

    allowed = {str(item.get("key") or "").strip() for item in items if isinstance(item, dict)}
    if not allowed:
        return True
    return metric in allowed


def _execute_internal_query(
    endpoint: str,
    query_payload: dict[str, object],
    kpi_service: KpiService,
    analytics_service: AnalyticsService,
) -> dict[str, object]:
    if endpoint == "/api/v1/kpis/query":
        return kpi_service.query(query_payload)
    if endpoint == "/api/v1/analytics/query":
        return analytics_service.query(query_payload)
    raise ValueError("Endpoint no permitido para ejecucion interna.")


def _build_response(
    question: str,
    resolved: bool,
    source: str,
    intent: str,
    metric: str,
    endpoint: str,
    translated_payload: dict[str, object],
    assumptions: list[str],
    result: dict[str, object],
    errors: list[str],
    query_payload: dict[str, object],
    explanation: str,
    auto_kpi: dict[str, object] | None,
) -> NaturalQueryRunResponse:
    return NaturalQueryRunResponse(
        question=question,
        resolved=resolved,
        source="llm" if source == "llm" else "rules",
        intent=intent,
        metric=metric,
        endpoint=endpoint,
        translated_payload=translated_payload,
        assumptions=assumptions,
        result=result,
        errors=errors,
        success=resolved,
        endpoint_used=endpoint,
        payload=query_payload,
        explanation=explanation,
        auto_kpi=auto_kpi,
    )


def _safe_record_interaction(
    service: NaturalQueryLearningService,
    response: NaturalQueryRunResponse,
    request_payload: NaturalQueryRequest,
) -> None:
    try:
        interaction_id = service.record_interaction(
            {
                "question": response.question,
                "use_llm_fallback": request_payload.use_llm_fallback,
                "source": response.source,
                "resolved": response.resolved,
                "intent": response.intent,
                "metric": response.metric,
                "endpoint": response.endpoint,
                "translated_payload": response.translated_payload,
                "errors": response.errors,
                "success": response.success,
            }
        )
        response.interaction_id = interaction_id
    except Exception:
        # El aprendizaje no debe romper la respuesta principal.
        return


def _resolve_auto_feedback_mode() -> str:
    mode = str(get_settings().natural_query_auto_feedback_mode or "off").strip().lower()
    if mode in {"off", "llm_only", "all_resolved"}:
        return mode
    return "off"


def _safe_record_auto_feedback(
    service: NaturalQueryLearningService,
    response: NaturalQueryRunResponse,
    user_claims: dict[str, object],
    gateway_confidence: object,
) -> None:
    mode = _resolve_auto_feedback_mode()
    if mode == "off":
        return
    if not response.resolved:
        return
    if not response.interaction_id:
        return
    if mode == "llm_only" and response.source != "llm":
        return

    min_confidence = float(get_settings().natural_query_auto_feedback_min_confidence or 0.0)
    confidence_value: float | None = None
    if isinstance(gateway_confidence, (int, float)):
        confidence_value = float(gateway_confidence)
    if response.source == "llm" and confidence_value is not None and confidence_value < min_confidence:
        return

    try:
        notes = f"auto_feedback mode={mode} source={response.source}"
        if confidence_value is not None:
            notes = f"{notes} confidence={confidence_value:.3f}"

        service.record_feedback(
            {
                "interaction_id": response.interaction_id,
                "question": response.question,
                "accepted": True,
                "corrected_intent": response.intent,
                "corrected_metric": response.metric,
                "corrected_endpoint": response.endpoint,
                "corrected_translated_payload": response.translated_payload,
                "notes": notes,
            },
            user_claims=user_claims,
        )
    except Exception:
        # El auto-feedback no debe romper la respuesta principal.
        return


def _normalize_question_for_temporal_rules(question: str) -> str:
    lowered = question.lower()
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


def _detect_quarter_number(normalized: str) -> int | None:
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
    for token, value in quarter_map.items():
        if f"{token} trimestre" in normalized:
            return value
    return None


def _extract_period_year_month(period: object) -> tuple[int, int] | None:
    if not isinstance(period, str):
        return None
    match = re.fullmatch(r"(20\d{2})-(0[1-9]|1[0-2])", period.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _refine_result_with_question_temporal_hints(
    question: str,
    result: dict[str, object],
) -> dict[str, object]:
    if not isinstance(result, dict):
        return result

    normalized = _normalize_question_for_temporal_rules(question)
    if "trimestre" not in normalized:
        return result

    quarter = _detect_quarter_number(normalized)
    if quarter is None:
        return result

    years = sorted({int(value) for value in re.findall(r"\b(20\d{2})\b", normalized)})
    if len(years) < 2:
        return result

    quarter_months = {(quarter - 1) * 3 + 1, (quarter - 1) * 3 + 2, (quarter - 1) * 3 + 3}
    allowed_years = {years[0], years[-1]}

    series = result.get("series")
    if not isinstance(series, list):
        return result

    for serie in series:
        if not isinstance(serie, dict):
            continue
        points = serie.get("points")
        if not isinstance(points, list):
            continue

        filtered_points: list[dict[str, object]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            parsed = _extract_period_year_month(point.get("period"))
            if parsed is None:
                continue
            year, month = parsed
            if year in allowed_years and month in quarter_months:
                filtered_points.append(point)

        serie["points"] = filtered_points

    return result


def _run_local_natural_query(
    payload: NaturalQueryRequest,
    claims: dict[str, object],
    kpi_service: KpiService,
    analytics_service: AnalyticsService,
    repository: object,
) -> NaturalQueryRunResponse:
    planner = NaturalQueryService()
    plan = planner.build_query_plan(payload.question)

    endpoint_used = str(plan["endpoint_used"])
    query_payload = dict(plan["payload"])
    assumptions = list(plan["assumptions"])
    explanation = str(plan["explanation"])
    auto_kpi: dict[str, object] | None = None
    auto_kpi_mode = _resolve_auto_kpi_mode()

    try:
        if endpoint_used.endswith("/kpis/query"):
            result = kpi_service.query(query_payload)
            if _should_try_auto_kpi(plan, result):
                candidate = plan.get("auto_kpi_candidate")
                if isinstance(candidate, dict):
                    approval_required = auto_kpi_mode == "human_approve"
                    approval_authorized = _can_approve_auto_kpi(claims)
                    can_auto_create = auto_kpi_mode == "auto_create" or (
                        auto_kpi_mode == "human_approve" and payload.approve_auto_kpi and approval_authorized
                    )

                    if not can_auto_create:
                        status = "pending_approval" if approval_required else "suggested"
                        if approval_required and payload.approve_auto_kpi and not approval_authorized:
                            status = "not_authorized"
                        auto_kpi = {
                            "created": False,
                            "mode": auto_kpi_mode,
                            "status": status,
                            "requires_approval": approval_required,
                            "candidate": candidate,
                        }
                        if approval_required and status == "not_authorized":
                            assumptions.append(
                                "Solicitud de aprobacion rechazada: rol/permisos insuficientes para crear KPI."
                            )
                            explanation = (
                                explanation
                                + " Se detecto un KPI candidato, pero el usuario no tiene permisos para aprobar su creacion."
                            )
                        elif approval_required:
                            assumptions.append(
                                "KPI sugerido, pendiente de aprobacion explicita (approve_auto_kpi=true)."
                            )
                            explanation = (
                                explanation
                                + " Se detecto un KPI candidato, pero el modo de seguridad requiere aprobacion humana."
                            )
                        else:
                            assumptions.append("KPI sugerido en modo suggest_only; no se creo automaticamente.")
                            explanation = (
                                explanation
                                + " Se detecto un KPI candidato y se devolvio como sugerencia sin crearlo."
                            )
                    else:
                        created = _create_kpi_from_candidate(candidate, repository, kpi_service)
                        query_payload = {
                            "kpi_keys": [str(created["kpi_key"])],
                            "granularity": query_payload.get("granularity") or "month",
                            "filters": query_payload.get("filters") or [],
                        }
                        result = kpi_service.query(query_payload)
                        assumptions.append("Se creo automaticamente un KPI para resolver la consulta.")
                        explanation = (
                            explanation
                            + " No habia un KPI disponible para la metrica solicitada y se genero uno nuevo."
                        )
                        auto_kpi = {
                            "created": True,
                            "mode": auto_kpi_mode,
                            "generated_kpi_key": created["kpi_key"],
                            "persisted_in_db": created["persisted_in_db"],
                            "validation": created["validation"],
                        }
        else:
            result = analytics_service.query(query_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo ejecutar la consulta natural: {exc}") from exc

    metric = ""
    if endpoint_used.endswith("/kpis/query"):
        kpi_keys = query_payload.get("kpi_keys") if isinstance(query_payload, dict) else None
        if isinstance(kpi_keys, list) and kpi_keys:
            metric = str(kpi_keys[0])
    elif isinstance(query_payload, dict):
        metric = str(query_payload.get("metric_key") or "")

    translated_payload = {
        "intent": str(plan.get("intent") or "trend"),
        "metric": metric,
        "granularity": str(query_payload.get("granularity") or "month"),
        "filters": query_payload.get("filters") if isinstance(query_payload, dict) else [],
    }

    return _build_response(
        question=payload.question,
        resolved=True,
        source="rules",
        intent=str(plan["intent"]),
        metric=metric,
        endpoint=endpoint_used,
        translated_payload=translated_payload,
        assumptions=assumptions,
        result=result,
        errors=[],
        query_payload=query_payload,
        explanation=explanation,
        auto_kpi=auto_kpi,
    )


def _resolve_auto_kpi_mode() -> str:
    mode = str(get_settings().natural_query_auto_kpi_mode or "human_approve").lower().strip()
    if mode in {"suggest_only", "human_approve", "auto_create"}:
        return mode
    return "human_approve"


def _can_approve_auto_kpi(claims: dict[str, object]) -> bool:
    role = str(claims.get("role") or "").strip().lower()
    permissions = claims.get("permissions")
    permission_values = {str(item).strip().lower() for item in permissions or []}

    if "natural_query:auto_kpi_approve" in permission_values:
        return True

    configured = str(get_settings().natural_query_auto_kpi_approver_roles or "")
    allowed_roles = {value.strip().lower() for value in configured.split(",") if value.strip()}
    return role in allowed_roles


def _should_try_auto_kpi(plan: dict[str, object], result: dict[str, object]) -> bool:
    if str(plan.get("intent") or "") != "trend":
        return False
    if not isinstance(plan.get("auto_kpi_candidate"), dict):
        return False
    if not isinstance(result, dict):
        return True
    series = result.get("series")
    if not isinstance(series, list) or len(series) == 0:
        return True
    points_count = 0
    for item in series:
        if isinstance(item, dict):
            points = item.get("points")
            if isinstance(points, list):
                points_count += len(points)
    return points_count == 0


def _persist_dynamic_kpi(item: DynamicKpi, repository: object) -> bool:
    kpi_registry.upsert(item)
    if isinstance(repository, MySQLRepository):
        repository.upsert_dynamic_kpi(item)
        return True
    return False


def _rollback_dynamic_kpi(key: str, repository: object) -> None:
    kpi_registry.remove(key)
    if isinstance(repository, MySQLRepository):
        try:
            repository.deactivate_dynamic_kpi(key)
        except Exception:
            pass


def _create_kpi_from_candidate(
    candidate: dict[str, str],
    repository: object,
    kpi_service: KpiService,
) -> dict[str, object]:
    designer = KpiDesignerService()
    generated = designer.generate(KpiDesignRequest(**candidate))
    registration_payload = generated.registration_payload

    item = DynamicKpi(
        key=registration_payload["key"],
        label=registration_payload["label"],
        description=registration_payload["description"],
        sql_query_template=registration_payload["sql_query_template"],
        default_granularity=registration_payload["default_granularity"],
    )

    persisted_in_db = _persist_dynamic_kpi(item, repository)
    validate_payload = generated.query_payload_example
    try:
        validation_result = kpi_service.query(validate_payload)
    except Exception as exc:
        _rollback_dynamic_kpi(item.key, repository)
        raise HTTPException(status_code=400, detail=f"Fallo la validacion del KPI auto-creado: {exc}") from exc

    series = validation_result.get("series", []) if isinstance(validation_result, dict) else []
    matched_series = [s for s in series if isinstance(s, dict) and str(s.get("kpi_key")) == item.key]
    total_points = sum(len((s.get("points") or [])) for s in matched_series)
    if isinstance(repository, MySQLRepository) and total_points == 0:
        _rollback_dynamic_kpi(item.key, repository)
        raise HTTPException(
            status_code=400,
            detail="El KPI auto-creado no devolvio puntos durante la validacion.",
        )

    return {
        "kpi_key": item.key,
        "persisted_in_db": persisted_in_db,
        "validation": {
            "series_found": len(matched_series),
            "points_found": total_points,
        },
    }
