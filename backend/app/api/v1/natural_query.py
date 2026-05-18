from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.dependencies import get_analytics_service, get_kpi_service, get_repository
from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.core.security import get_current_claims
from app.repositories.mysql_repository import MySQLRepository
from app.schemas.kpi_designer import KpiDesignRequest
from app.schemas.natural_query import NaturalQueryRequest, NaturalQueryResponse
from app.services.kpi_designer_service import KpiDesignerService
from app.services.analytics_service import AnalyticsService
from app.services.kpi_service import KpiService
from app.services.natural_query_service import NaturalQueryService

router = APIRouter(prefix="/natural-query", tags=["Natural Query"])


@router.post("/run", response_model=NaturalQueryResponse)
def run_natural_query(
    payload: NaturalQueryRequest,
    claims: dict = Depends(get_current_claims),
    kpi_service: KpiService = Depends(get_kpi_service),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    repository: object = Depends(get_repository),
) -> NaturalQueryResponse:
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

    return NaturalQueryResponse(
        success=True,
        intent=str(plan["intent"]),
        endpoint_used=endpoint_used,
        payload=query_payload,
        assumptions=assumptions,
        explanation=explanation,
        auto_kpi=auto_kpi,
        result=result,
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
