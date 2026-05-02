from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.core.dependencies import get_repository
from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.core.security import get_current_claims
from app.repositories.mysql_repository import MySQLRepository
from app.schemas.kpi_designer import KpiDesignRequest, KpiDesignResponse, KpiRegisterRequest
from app.services.kpi_designer_service import KpiDesignerService

router = APIRouter(prefix="/kpi-designer", tags=["KPI Designer"])


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
    .card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 4px 18px rgba(0,0,0,.08); }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    label { font-size: 12px; color: #334; font-weight: 600; }
    .hint { font-size: 12px; color: #5b6576; margin-top: 4px; }
    .title { margin: 0 0 8px 0; }
    .steps { margin: 0 0 12px 0; padding-left: 18px; color: #334; }
    input, textarea { width: 100%; box-sizing: border-box; margin-top: 4px; padding: 8px; border: 1px solid #cfd7e3; border-radius: 8px; }
    textarea { min-height: 110px; }
    button { margin-top: 12px; padding: 10px 14px; border: 0; border-radius: 10px; background: #1d4ed8; color: #fff; font-weight: 700; cursor: pointer; }
    pre { white-space: pre-wrap; background: #0b1020; color: #d6e2ff; padding: 10px; border-radius: 8px; overflow: auto; }
    .error { margin-top: 10px; color: #9f1239; font-weight: 600; }
  </style>
</head>
<body>
  <h2 class=\"title\">Formulario simple de KPI</h2>
  <ol class=\"steps\">
    <li>Pega tu token JWT.</li>
    <li>Completa solo 4 campos: nombre, descripcion, granularidad y SQL.</li>
    <li>Genera el codigo sugerido para el equipo tecnico.</li>
  </ol>
  <div class=\"card\">
    <label>Token JWT</label>
    <input id=\"token\" placeholder=\"Pega aqui el token (sin Bearer)\"/>
    <div class=\"hint\">Lo obtienes en /api/v1/auth/login, campo access_token.</div>

    <label>Nombre del KPI</label>
    <input id=\"kpi_name\" value=\"Participacion PTCA\"/>
    <div class=\"hint\">Ejemplo: Participacion PTCA, Tasa de reingreso 30 dias.</div>

    <label>Descripcion</label>
    <textarea id=\"description\">Porcentaje de PTCA sobre el total de actividad.</textarea>
    <div class=\"hint\">Describe para que sirve el KPI en una frase clara.</div>

    <label>Granularidad</label>
    <input id=\"granularity\" value=\"month\"/>
    <div class=\"hint\">Usa day, week o month.</div>

    <label>Consulta SQL asociada (debe devolver period y value)</label>
    <textarea id=\"sql_query\">SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,
       ROUND(100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0), 2) AS value
FROM flow_coordina f
LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
WHERE f.FechaRealizado > '1900-01-01'
GROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')
ORDER BY period</textarea>
    <div class=\"hint\">No necesitas completar campos tecnicos adicionales.</div>

    <button onclick=\"run()\">Generar snippets</button>
    <div id=\"err\" class=\"error\"></div>
  </div>

  <h3>Salida</h3>
  <div class=\"card\"><pre id=\"out\">Sin generar aun</pre></div>

<script>
async function run(){
  document.getElementById('err').textContent = '';
  const token = document.getElementById('token').value.trim();
  if(!token) return;
  const payload = {
    kpi_name: document.getElementById('kpi_name').value,
    description: document.getElementById('description').value,
    granularity: document.getElementById('granularity').value,
    sql_query: document.getElementById('sql_query').value
  };

  const res = await fetch('/api/v1/kpi-designer/generate', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
    body: JSON.stringify(payload)
  });
  if(!res.ok){
    const err = await res.json();
    document.getElementById('err').textContent = 'Error: ' + (err.detail || 'No se pudo generar el KPI.');
    return;
  }
  const data = await res.json();
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
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
    kpi_registry.upsert(item)

    persisted_in_db = False
    repository = get_repository()
    if isinstance(repository, MySQLRepository):
      try:
        repository.upsert_dynamic_kpi(item)
        persisted_in_db = True
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
