# Cardio Insights Backend (FastAPI)

Backend API para el MVP academico de Cardio Insights, orientado a trabajo desacoplado con frontend y equipo de datos usando contratos JSON estables y repositorio mock reemplazable.

## Stack

- Python 3.12
- FastAPI
- JWT (python-jose)
- Docker / docker-compose
- Pytest

## Estructura

```text
backend/
  app/
    api/
      v1/
        api.py
        auth.py
        health.py
        catalogs.py
        dashboard.py
        kpis.py
    core/
      config.py
      dependencies.py
      security.py
      token_store.py
    repositories/
      interfaces.py
      mock_repository.py
      mysql_repository.py
    schemas/
      auth.py
      health.py
      catalogs.py
      dashboard.py
      kpis.py
    services/
      auth_service.py
      catalog_service.py
      dashboard_service.py
      kpi_service.py
    tests/
      test_api.py
    main.py
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## Endpoints implementados

- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- GET /api/v1/auth/me
- GET /api/v1/health
- GET /api/v1/catalogs/filters
- GET /api/v1/catalogs/kpis
- GET /api/v1/dashboard/summary
- GET /api/v1/dashboard/charts
- GET /api/v1/dashboard/table
- POST /api/v1/kpis/query
- POST /api/v1/analytics/query
- POST /api/v1/natural-query/run
- POST /api/v1/natural-query/feedback
- POST /api/v1/natural-query/training/export

Todos salvo health requieren Authorization: Bearer <token>.

## Variables de entorno nuevas (LLM Gateway)

Agregar en `.env`:

```env
LLM_GATEWAY_URL=http://IP_DE_LA_VM:8000
LLM_GATEWAY_ENABLED=false
LLM_GATEWAY_TIMEOUT_SECONDS=8
NATURAL_QUERY_LEARNING_FILE=data/natural_query_learning.jsonl
NATURAL_QUERY_TRAINING_EXPORT_FILE=data/natural_query_training_dataset.jsonl
NATURAL_QUERY_AUTO_FEEDBACK_MODE=off
NATURAL_QUERY_AUTO_FEEDBACK_MIN_CONFIDENCE=0.80
NATURAL_QUERY_ONLINE_MEMORY_ENABLED=false
NATURAL_QUERY_ONLINE_MEMORY_MIN_SCORE=0.88
```

Comportamiento:

- Si `NATURAL_QUERY_ONLINE_MEMORY_ENABLED=true`, el endpoint intenta primero reutilizar planes aprobados por feedback humano. Esa respuesta se marca como `source=memory`.
- Si `LLM_GATEWAY_ENABLED=true`, el endpoint de natural-query intenta resolver via gateway.
- Si el gateway falla, expira o responde invalido, el backend hace fallback a reglas locales.
- Si `LLM_GATEWAY_ENABLED=false`, siempre usa reglas locales.
- Cada llamada a `POST /api/v1/natural-query/run` guarda una interaccion para aprendizaje continuo.
- Recomendado: mantener `NATURAL_QUERY_AUTO_FEEDBACK_MODE=off` y registrar feedback humano para evitar que el sistema aprenda respuestas incorrectas.
- Si `NATURAL_QUERY_AUTO_FEEDBACK_MODE=all_resolved`, cada consulta resuelta se marca automaticamente como aceptada para entrenamiento. Usar solo en demos controladas.
- Si `NATURAL_QUERY_AUTO_FEEDBACK_MODE=llm_only`, solo auto-aprende respuestas `source=llm` (con umbral opcional `NATURAL_QUERY_AUTO_FEEDBACK_MIN_CONFIDENCE`).

Perfil recomendado para pruebas reales/demos con base INCC:

```env
REPOSITORY_BACKEND=mysql
LLM_GATEWAY_ENABLED=true
NATURAL_QUERY_AUTO_KPI_MODE=auto_create
NATURAL_QUERY_AUTO_FEEDBACK_MODE=llm_only
NATURAL_QUERY_AUTO_FEEDBACK_MIN_CONFIDENCE=0.85
NATURAL_QUERY_ONLINE_MEMORY_ENABLED=true
NATURAL_QUERY_ONLINE_MEMORY_MIN_SCORE=0.92
```

Perfil recomendado para CI/tests reproducibles:

```env
REPOSITORY_BACKEND=mock
LLM_GATEWAY_ENABLED=false
NATURAL_QUERY_AUTO_KPI_MODE=human_approve
NATURAL_QUERY_AUTO_FEEDBACK_MODE=off
NATURAL_QUERY_ONLINE_MEMORY_ENABLED=false
```

## Ejecucion local rapida

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Swagger UI:

- http://localhost:8000/docs

## Docker

```bash
cd backend
docker compose up --build
```

## Modo MySQL real (INCC)

Para usar datos reales en lugar de mocks:

1. Configurar credenciales en `.env`:

```env
REPOSITORY_BACKEND=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=tu_password
MYSQL_DATABASE=incc
```

2. Levantar API y probar endpoints de dashboard/KPI.

KPI keys soportadas con SQL real:

- volumen_mensual_total
- surgery_volume
- ptca_volume
- ptca_share_pct
- mortality_egreso_pct
- avg_wait_days
- icu_los_avg
- mortality_30d (alias operativo de egreso con fallecimiento)
- mortality_egreso_count
- readmission_30d
- espera_maxima_en_dias
- reintervenciones_mensual
- hemodinamia_volumen_mensual
- centros_que_envian_pacientes
- top_centro_por_periodo
- espera_tramite_a_autorizacion_dias
- espera_autorizacion_a_realizado_dias

Autenticacion en modo mysql:

- Se intenta login contra `use_usuarios` (Alias + Clave/MD5text) y permisos desde `use_permiso`.
- Si el usuario no existe en BD, queda fallback a usuarios de desarrollo (`dcaraballo`, `ggarcia`, `acampopiano`, `admin`) para no frenar el MVP.
- Recomendado: crear usuario tecnico de pruebas en `use_usuarios` y usarlo para integracion.

## KPI Designer (interfaz no-code para equipo funcional)

Si la persona que define KPIs no programa en Python, puede usar un formulario simple que genera snippets de codigo listos para pegar.

1. Inicia sesion normalmente para obtener un token JWT.
2. Abre en navegador: `http://localhost:8000/api/v1/kpi-designer/ui`
3. Pega el token cuando lo pida la pantalla.
4. Completa solo estos 4 campos:

- nombre del KPI
- descripcion
- granularidad (`day`, `week`, `month`)
- SQL asociada (debe devolver `period` y `value`)

La SQL debe ser un unico `SELECT`, usar `{period_expr}` y `{date_clause}`, y referenciar solo tablas clinicas permitidas por el backend. Se bloquean comentarios, multiples sentencias, DDL/DML y tablas fuera de allowlist.

5. Presiona "Generar snippets".
6. Copia `registration_payload` de la respuesta.
7. En Swagger, pega ese JSON en `POST /api/v1/kpi-designer/register`.
8. Usa `query_payload_example` para consultar en `POST /api/v1/kpis/query`.

La salida incluye:

- `registration_payload` (para registrar KPI sin tocar codigo)
- `query_payload_example` (para probar el KPI en query)
- snippets de apoyo para equipo tecnico (opcionales)

Nota: si `REPOSITORY_BACKEND=mysql`, el endpoint `/kpi-designer/register` crea/actualiza la tabla `cardio_dynamic_kpis` y persiste el KPI en MySQL. En modo mock, queda en el registry/JSON local.

## Credenciales mock / seed

- admin / Admin1234! (`admin`)
- dcaraballo / Demo1234! (`clinico`)
- ggarcia / Demo1234! (`gestion`)
- acampopiano / Demo1234! (`clinico`)

## Ejemplos de requests y responses

### Login

Request:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "dcaraballo",
  "password": "Demo1234!"
}
```

Response 200:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 7200,
  "user": {
    "id": 2,
    "username": "dcaraballo",
    "full_name": "Diego Caraballo",
    "role": "clinico",
    "permissions": ["dashboard:read", "kpis:query"]
  }
}
```

### Me

Request:

```http
GET /api/v1/auth/me
Authorization: Bearer <jwt>
```

Response 200:

```json
{
  "user": {
    "id": 2,
    "username": "dcaraballo",
    "full_name": "Diego Caraballo",
    "role": "clinico",
    "permissions": ["dashboard:read", "kpis:query"]
  }
}
```

### Dashboard Summary

Request:

```http
GET /api/v1/dashboard/summary
Authorization: Bearer <jwt>
```

Response 200:

```json
{
  "cards": [
    {
      "key": "surgery_volume",
      "label": "Cirugias (mes)",
      "value": 214,
      "unit": "casos",
      "delta": 8.4
    }
  ]
}
```

### KPI Query

Request:

```http
POST /api/v1/kpis/query
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "kpi_keys": ["mortality_30d", "surgery_volume"],
  "filters": [
    { "key": "period", "values": ["last_90_days"] }
  ],
  "granularity": "month"
}
```

Response 200:

```json
{
  "series": [
    {
      "kpi_key": "mortality_30d",
      "points": [{ "period": "2025-11", "value": 2.4 }]
    },
    {
      "kpi_key": "surgery_volume",
      "points": [{ "period": "2025-11", "value": 180.0 }]
    }
  ]
}
```

### Analytics Query (table/ranking)

Request:

```http
POST /api/v1/analytics/query
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "widget_type": "ranking",
  "metric_key": "surgery_volume",
  "granularity": "month",
  "limit": 5,
  "filters": [
    { "key": "date_from", "values": ["2026-01-01"] },
    { "key": "date_to", "values": ["2026-03-31"] }
  ]
}
```

Response 200:

```json
{
  "widget_type": "ranking",
  "title": "Ranking por periodo",
  "columns": [
    { "key": "rank", "label": "Posicion" },
    { "key": "label", "label": "Periodo" },
    { "key": "value", "label": "Valor" }
  ],
  "rows": [{ "rank": 1, "label": "2026-03", "value": 214 }],
  "meta": {
    "metric_key": "surgery_volume",
    "granularity": "month",
    "limit": 5
  }
}
```

Filtros soportados en `POST /api/v1/kpis/query`:

- `date_from` (YYYY-MM-DD)
- `date_to` (YYYY-MM-DD)
- `act_type`: `all`, `surgery`, `ptca`

### Natural Query Run (integrado con LLM Gateway)

Request:

```http
POST /api/v1/natural-query/run
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "question": "Como viene la espera promedio este ano?",
  "use_llm_fallback": true
}
```

Response 200 (ejemplo):

```json
{
  "question": "Como viene la espera promedio este ano?",
  "resolved": true,
  "source": "llm",
  "intent": "trend",
  "metric": "avg_wait_days",
  "endpoint": "/api/v1/kpis/query",
  "translated_payload": {
    "intent": "trend",
    "metric": "avg_wait_days",
    "granularity": "month",
    "period": { "type": "current_year" }
  },
  "assumptions": ["Se interpreto la consulta como tendencia."],
  "result": {
    "series": []
  },
  "errors": [],
  "success": true,
  "endpoint_used": "/api/v1/kpis/query",
  "payload": {
    "kpi_keys": ["avg_wait_days"],
    "granularity": "month",
    "filters": [
      { "key": "date_from", "values": ["2026-01-01"] },
      { "key": "date_to", "values": ["2026-12-31"] }
    ]
  },
  "explanation": "Consulta resuelta por traduccion del LLM Gateway.",
  "auto_kpi": null
}
```

Seguridad aplicada en `natural-query/run`:

- El gateway solo recibe `question` y `use_llm_fallback` (no se envian datos clinicos).
- Se rechaza `translated_payload` con contenido SQL o claves sospechosas.
- Solo se aceptan intents: `trend`, `ranking`, `comparison`, `alert`.
- Solo se aceptan endpoints: `/api/v1/kpis/query`, `/api/v1/analytics/query`.
- Se valida la metrica contra el catalogo local de KPIs cuando esta disponible.

### Aprendizaje y entrenamiento (human-in-the-loop)

1. Ejecuta `POST /api/v1/natural-query/run` y guarda `interaction_id`.
2. Registra correccion humana en `POST /api/v1/natural-query/feedback`.
3. Exporta dataset en `POST /api/v1/natural-query/training/export?approved_only=true`.
4. Usa el archivo JSONL exportado para entrenar/reentrenar el modelo del gateway.

Ejemplo feedback:

```http
POST /api/v1/natural-query/feedback
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "interaction_id": "a1b2c3d4",
  "accepted": true,
  "corrected_intent": "trend",
  "corrected_metric": "avg_wait_days",
  "corrected_endpoint": "/api/v1/kpis/query",
  "corrected_translated_payload": {
    "intent": "trend",
    "metric": "avg_wait_days",
    "granularity": "month",
    "period": { "type": "current_year" }
  },
  "notes": "Interpretacion validada por analista"
}
```

Ejemplo export:

```http
POST /api/v1/natural-query/training/export?approved_only=true
Authorization: Bearer <jwt>
```

Response:

```json
{
  "total_samples": 42,
  "export_path": "C:/.../backend/data/natural_query_training_dataset.jsonl"
}
```

## LLM Gateway VM (referencia rapida)

1. Levantar el servicio en la VM con endpoint `POST /llm/nl2kpi/interpret`.
2. Confirmar conectividad desde el backend (`LLM_GATEWAY_URL`) a la VM.
3. Configurar variables en `.env` y reiniciar API.

## Probar desde Swagger

1. Ir a `http://localhost:8000/docs`.
2. Ejecutar `POST /api/v1/auth/login` y copiar `access_token`.
3. Presionar `Authorize` y pegar `Bearer <token>`.
4. Ejecutar `POST /api/v1/natural-query/run` con:

```json
{
  "question": "Como viene la espera promedio este ano?"
}
```

5. Verificar en la respuesta:

- `source` (`rules`, `llm` o `memory`)
- `translated_payload`
- `endpoint` + `payload`
- `result`
- `errors` (si hubo fallback)

Ejemplo:

```json
{
  "kpi_keys": ["surgery_volume", "ptca_volume", "avg_wait_days"],
  "granularity": "month",
  "filters": [
    { "key": "date_from", "values": ["2025-01-01"] },
    { "key": "date_to", "values": ["2026-12-31"] },
    { "key": "act_type", "values": ["all"] }
  ]
}
```

## Testing recomendado (pytest)

Incluido:

- tests de health
- login + me + logout (invalidación de sesión)
- auth unitaria (JWT, blocklist, passwords plain/md5/bcrypt)
- `sql_guard` (matriz de seguridad del chat clínico)
- auth requerida en endpoints protegidos
- consulta KPI / natural-query

Ejecutar:

```bash
cd backend
pytest -q
# Reporte HTML: backend/htmlcov/index.html
```

Coverage actual (baseline): ver salida de `pytest -q` (`--cov-fail-under=90` se activará al cerrar gaps de chat/ML/MySQL).


Pruebas de integracion MySQL (recomendadas para coverage alto):

```bash
cd backend
docker compose down -v
docker compose up -d mysql
# esperar healthcheck healthy

# PowerShell
$env:RUN_INTEGRATION_DB_TESTS="1"
pytest -q
# o solo integración:
pytest -q app/tests/integration
```

Credenciales por defecto del compose: `cardio` / `cardio`, DB `incc`, user demo `dcaraballo` / `Demo1234!`.

Recomendaciones siguientes:

1. Subir `--cov-fail-under` gradualmente hasta 90.
2. Cerrar gaps restantes de `natural_query` / `kpi_designer` / learning.
3. Snapshot tests de contratos JSON para evitar romper frontend.

## Plan de migracion de mocks a MySQL

1. Mantener MySQLRepository como capa de acceso principal para dashboard/KPI.
2. Validar y refinar reglas de limpieza de sentinelas (1900-01-01, -99, 255).
3. Incorporar nuevas vistas SQL validadas por equipo de datos.
4. Mantener services y routers sin cambios de contrato.
5. Ejecutar suite de pytest + pruebas de contrato contra frontend.
6. Reducir alcance de mocks solo a escenarios de desarrollo offline.

## Supuestos de negocio usados para el MVP

- KPI principal en porcentaje o conteo.
- Granularidad temporal mensual por defecto.
- Un usuario puede ver dashboard y consultar KPI segun permisos.
- Logout invalida el jti del token en memoria de proceso (suficiente para MVP).

## Buenas practicas minimas de seguridad

1. Cambiar JWT_SECRET_KEY en cada entorno.
2. No commitear .env real (solo .env.example).
3. Definir expiracion corta de token en prod.
4. Usar HTTPS en despliegue real.
5. Restringir CORS a dominios del frontend en prod.
6. Agregar rate limiting para login cuando se pase a entorno real.
