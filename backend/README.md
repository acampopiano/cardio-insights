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

Todos salvo health requieren Authorization: Bearer <token>.

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

- surgery_volume
- ptca_volume
- mortality_egreso_pct
- avg_wait_days
- icu_los_avg
- mortality_30d (alias operativo de egreso con fallecimiento)

Autenticacion en modo mysql:

- Se intenta login contra `use_usuarios` (Alias + Clave/MD5text) y permisos desde `use_permiso`.
- Si el usuario no existe en BD, queda fallback a usuarios de desarrollo (`clinician`, `admin`) para no frenar el MVP.
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

5. Presiona "Generar snippets".
6. Copia `registration_payload` de la respuesta.
7. En Swagger, pega ese JSON en `POST /api/v1/kpi-designer/register`.
8. Usa `query_payload_example` para consultar en `POST /api/v1/kpis/query`.

La salida incluye:

- `registration_payload` (para registrar KPI sin tocar codigo)
- `query_payload_example` (para probar el KPI en query)
- snippets de apoyo para equipo tecnico (opcionales)

Nota: si `REPOSITORY_BACKEND=mysql`, el endpoint `/kpi-designer/register` persiste el KPI en MySQL y sobrevive reinicios. En modo mock, queda en memoria.

## Credenciales mock

- clinician / Demo1234!
- admin / Admin1234!

## Ejemplos de requests y responses

### Login

Request:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "clinician",
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
    "id": 1,
    "username": "clinician",
    "full_name": "Dr. Ana Pereira",
    "role": "clinician",
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
    "id": 1,
    "username": "clinician",
    "full_name": "Dr. Ana Pereira",
    "role": "clinician",
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
- login + me
- auth requerida en endpoints protegidos
- consulta KPI

Ejecutar:

```bash
cd backend
pytest -q
```

Pruebas de integracion MySQL (opcionales):

```bash
cd backend
# PowerShell
$env:RUN_INTEGRATION_DB_TESTS="1"
$env:INCC_TEST_USERNAME="tu_alias"
$env:INCC_TEST_PASSWORD="tu_password"
pytest -q app/tests/test_integration_mysql.py
```

Recomendaciones siguientes:

1. Agregar tests de error contractuales (401, 404, payload invalido).
2. Agregar snapshot tests de contratos JSON para evitar romper frontend.
3. Agregar tests de repositorio MySQL con DB de prueba en docker compose.

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
