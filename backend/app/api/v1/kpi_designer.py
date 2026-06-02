from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.core.dependencies import get_kpi_service, get_repository
from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.core.security import get_current_claims
from app.schemas.kpi_designer import (
  KpiCreateResponse,
  KpiDesignRequest,
  KpiDesignResponse,
  KpiRegisterRequest,
)
from app.services.kpi_service import KpiService
from app.services.kpi_designer_service import KpiDesignerService

router = APIRouter(prefix="/kpi-designer", tags=["KPI Designer"])


def _persist_dynamic_kpi(item: DynamicKpi, repository: object) -> bool:
  kpi_registry.upsert(item)
  return False


def _rollback_dynamic_kpi(key: str, repository: object) -> None:
  kpi_registry.remove(key)


@router.get("/ui", response_class=HTMLResponse)
def kpi_designer_ui() -> HTMLResponse:
    html = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>KPI Designer</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f5f7fb; }
    .card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 4px 18px rgba(0,0,0,.08); margin-bottom: 12px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    label { font-size: 12px; color: #334; font-weight: 600; }
    .hint { font-size: 12px; color: #5b6576; margin-top: 4px; }
    .title { margin: 0 0 8px 0; }
    .steps { margin: 0 0 12px 0; padding-left: 18px; color: #334; }
    input, textarea, select { width: 100%; box-sizing: border-box; margin-top: 4px; padding: 8px; border: 1px solid #cfd7e3; border-radius: 8px; }
    textarea { min-height: 110px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    button { padding: 10px 14px; border: 0; border-radius: 10px; background: #1d4ed8; color: #fff; font-weight: 700; cursor: pointer; }
    button.secondary { background: #334155; }
    button.ghost { background: #64748b; margin-top: 8px; }
    pre { white-space: pre-wrap; background: #0b1020; color: #d6e2ff; padding: 10px; border-radius: 8px; overflow: auto; }
    .error { margin-top: 10px; color: #9f1239; font-weight: 600; }
    .ok { margin-top: 10px; color: #065f46; font-weight: 600; }
  </style>
</head>
<body>
  <h2 class=\"title\">Formulario simple de KPI</h2>
  <ol class=\"steps\">
    <li>Pega tu token JWT.</li>
    <li>Elige un tipo de KPI y aplica plantilla o escribe SQL propia.</li>
    <li>Usa Crear KPI para generar, validar y registrar en un solo paso.</li>
  </ol>
  <div class=\"card\">
    <label>Token JWT</label>
    <input id=\"token\" placeholder=\"Pega aqui el token (sin Bearer)\"/>
    <div class=\"hint\">Lo obtienes en /api/v1/auth/login, campo access_token.</div>

    <div class=\"grid\">
      <div>
        <label>Tipo de KPI</label>
        <select id=\"kpi_type\">
          <option value=\"custom\">Custom (manual)</option>
          <option value=\"count_trend\">Volumen por periodo (COUNT)</option>
          <option value=\"avg_trend\">Promedio por periodo (AVG)</option>
          <option value=\"ratio_trend\">Porcentaje por periodo (ratio)</option>
          <option value=\"top_sender\">Top centro por periodo</option>
        </select>
      </div>
      <div>
        <label>Granularidad</label>
        <select id=\"granularity\">
          <option value=\"day\">day</option>
          <option value=\"week\">week</option>
          <option value=\"month\" selected>month</option>
        </select>
      </div>
    </div>
    <button class=\"ghost\" type=\"button\" onclick=\"applyTemplate()\">Aplicar plantilla</button>

    <label>Nombre del KPI</label>
    <input id=\"kpi_name\" value=\"Participacion PTCA\"/>
    <div class=\"hint\">Ejemplo: Participacion PTCA, Tasa de reingreso 30 dias.</div>

    <label>Descripcion</label>
    <textarea id=\"description\">Porcentaje de PTCA sobre el total de actividad.</textarea>
    <div class=\"hint\">Describe para que sirve el KPI en una frase clara.</div>

    <label>Consulta SQL asociada (debe devolver period y value)</label>
    <textarea id=\"sql_query\">SELECT
  {period_expr} AS period,
  ROUND(100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0), 2) AS value
FROM flow_coordina f
LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
WHERE f.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period</textarea>
    <div class=\"hint\">La SQL debe devolver aliases exactos: period y value.</div>

    <div class=\"actions\">
      <button type=\"button\" class=\"secondary\" onclick=\"runGenerate()\">Generar snippets</button>
      <button type=\"button\" onclick=\"runCreate()\">Crear KPI (genera + valida + registra)</button>
    </div>
    <div id=\"err\" class=\"error\"></div>
    <div id=\"ok\" class=\"ok\"></div>
  </div>

  <h3>Salida</h3>
  <div class=\"card\"><pre id=\"out\">Sin generar aun</pre></div>

<script>
const templates = {
  count_trend: {
    name: 'Volumen de actos realizados',
    description: 'Cantidad total de actos por periodo.',
    sql: `SELECT
  {period_expr} AS period,
  COUNT(*) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  {date_clause}
GROUP BY {period_expr}
ORDER BY period`
  },
  avg_trend: {
    name: 'Espera promedio por periodo',
    description: 'Promedio de dias entre coordinacion y realizado por periodo.',
    sql: `SELECT
  {period_expr} AS period,
  ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)), 2) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  AND f.FechaCoordina > '1900-01-01'
  AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0
  {date_clause}
GROUP BY {period_expr}
ORDER BY period`
  },
  ratio_trend: {
    name: 'Participacion PTCA',
    description: 'Porcentaje de PTCA sobre actividad total por periodo.',
    sql: `SELECT
  {period_expr} AS period,
  ROUND(100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0), 2) AS value
FROM flow_coordina f
LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
WHERE f.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period`
  },
  top_sender: {
    name: 'Top centro por periodo',
    description: 'Cantidad de actos del centro lider por periodo.',
    sql: `SELECT
  t.period AS period,
  MAX(t.total_actos) AS value
FROM (
  SELECT
    {period_expr} AS period,
    f.CodSeguroCoo AS centro_cod,
    COUNT(*) AS total_actos
  FROM flow_coordina f
  LEFT JOIN stk_cartera stk ON stk.CodPacFichaCubre = f.CodSeguroCoo
  WHERE f.Realizado = 255
    AND f.CodSeguroCoo > 0
    {date_clause}
  GROUP BY {period_expr}, f.CodSeguroCoo
) t
GROUP BY t.period
ORDER BY t.period`
  }
};

function setMessages(okMsg, errMsg) {
  document.getElementById('ok').textContent = okMsg || '';
  document.getElementById('err').textContent = errMsg || '';
}

function getPayload() {
  return {
    kpi_name: document.getElementById('kpi_name').value,
    description: document.getElementById('description').value,
    granularity: document.getElementById('granularity').value,
    sql_query: document.getElementById('sql_query').value
  };
}

function applyTemplate(){
  const kpiType = document.getElementById('kpi_type').value;
  const t = templates[kpiType];
  if (!t) {
    return;
  }
  document.getElementById('kpi_name').value = t.name;
  document.getElementById('description').value = t.description;
  document.getElementById('sql_query').value = t.sql;
}

async function runGenerate(){
  setMessages('', '');
  const token = document.getElementById('token').value.trim();
  if(!token) {
    setMessages('', 'Pega un token JWT primero.');
    return;
  }

  const res = await fetch('/api/v1/kpi-designer/generate', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
    body: JSON.stringify(getPayload())
  });

  const data = await res.json();
  if(!res.ok){
    setMessages('', 'Error: ' + (data.detail || 'No se pudo generar el KPI.'));
    document.getElementById('out').textContent = JSON.stringify(data, null, 2);
    return;
  }
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  setMessages('Snippets generados. Si quieres, ahora crea el KPI con un click.', '');
}

async function runCreate(){
  setMessages('', '');
  const token = document.getElementById('token').value.trim();
  if(!token) {
    setMessages('', 'Pega un token JWT primero.');
    return;
  }

  const res = await fetch('/api/v1/kpi-designer/create', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
    body: JSON.stringify(getPayload())
  });

  const data = await res.json();
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  if(!res.ok){
    setMessages('', 'Error: ' + (data.detail || 'No se pudo crear el KPI.'));
    return;
  }

  setMessages('KPI creado y validado. Ya puedes consultarlo en /api/v1/kpis/query.', '');
}
</script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@router.post("/generate", response_model=KpiDesignResponse)
def generate_kpi_code(
    payload: KpiDesignRequest,
    _: dict = Depends(get_current_claims),
) -> KpiDesignResponse:
    service = KpiDesignerService()
    try:
        return service.generate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/register")
def register_kpi(
    payload: KpiRegisterRequest,
    _: dict = Depends(get_current_claims),
) -> dict[str, object]:
    if payload.default_granularity not in {"day", "week", "month"}:
        raise HTTPException(status_code=400, detail="default_granularity debe ser day, week o month")

    item = DynamicKpi(
        key=payload.key,
        label=payload.label,
        description=payload.description,
        sql_query_template=payload.sql_query_template,
        default_granularity=payload.default_granularity,
    )
    repository = get_repository()
    try:
        persisted_in_db = _persist_dynamic_kpi(item, repository)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo persistir el KPI en MySQL: {exc}") from exc

    return {
        "success": True,
      "message": "KPI registrado y listo para consultar desde /api/v1/kpis/query.",
      "persisted_in_db": persisted_in_db,
        "kpi_key": payload.key,
        "query_payload_example": {
            "kpi_keys": [payload.key],
            "granularity": payload.default_granularity,
            "filters": [
                {"key": "date_from", "values": ["2025-01-01"]},
                {"key": "date_to", "values": ["2026-12-31"]},
            ],
        },
    }


@router.post("/create", response_model=KpiCreateResponse)
def create_kpi(
    payload: KpiDesignRequest,
    _: dict = Depends(get_current_claims),
    kpi_service: KpiService = Depends(get_kpi_service),
) -> KpiCreateResponse:
    designer = KpiDesignerService()
    try:
        generated = designer.generate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    registration_payload = generated.registration_payload
    item = DynamicKpi(
        key=registration_payload["key"],
        label=registration_payload["label"],
        description=registration_payload["description"],
        sql_query_template=registration_payload["sql_query_template"],
        default_granularity=registration_payload["default_granularity"],
    )

    repository = get_repository()
    try:
        persisted_in_db = _persist_dynamic_kpi(item, repository)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo persistir el KPI en MySQL: {exc}") from exc

    validate_payload = generated.query_payload_example
    try:
        validation_result = kpi_service.query(validate_payload)
    except Exception as exc:
        _rollback_dynamic_kpi(item.key, repository)
        raise HTTPException(status_code=400, detail=f"Fallo la validacion del KPI: {exc}") from exc

    series = validation_result.get("series", []) if isinstance(validation_result, dict) else []
    matched_series = [s for s in series if str(s.get("kpi_key")) == item.key]
    total_points = sum(len(s.get("points") or []) for s in matched_series)
    first_series = matched_series[0] if matched_series else {}
    sample_points = (first_series.get("points") or [])[:5] if isinstance(first_series, dict) else []

    return KpiCreateResponse(
        success=True,
        message="KPI creado, validado y listo para consultar desde /api/v1/kpis/query.",
        persisted_in_db=persisted_in_db,
        generated_kpi_key=item.key,
        registration_payload=registration_payload,
        query_payload_example=validate_payload,
        validation={
            "series_found": len(matched_series),
            "points_found": total_points,
            "note": "En modo mock puede no haber puntos para KPIs dinamicos.",
        },
        query_result_preview={
          "kpi_key": item.key,
          "sample_points": sample_points,
          "sample_points_count": len(sample_points),
          "total_points": total_points,
        },
    )
