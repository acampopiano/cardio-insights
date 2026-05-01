# Backend explicado para equipo (Cardio Insights)

Objetivo de este documento:

- Entender rapido que hace cada archivo principal del backend.
- Saber por donde entra una request y por donde salen los datos.
- Tener una guia comun para onboarding y mantenimiento.

## 1. Mapa simple del backend

El backend sigue esta idea:

1. API (endpoints): recibe requests HTTP.
2. Service: aplica logica de negocio.
3. Repository: obtiene datos (mock o MySQL).
4. Schemas: validan entrada y salida.
5. Core: configuracion, dependencias y seguridad.

Flujo corto:

- Cliente -> endpoint -> service -> repository -> DB/mock -> service -> response schema -> cliente.

## 2. Archivos principales y para que sirven

### 2.1 Arranque de la app

- backend/app/main.py
  - Crea la app FastAPI.
  - Configura CORS.
  - Registra el router principal (`api_router`) con prefijo `/api/v1`.
  - Es el punto de entrada cuando se levanta Uvicorn.

### 2.2 Configuracion global

- backend/app/core/config.py
  - Define `Settings` (app, JWT, backend mock/mysql, MySQL host/user/db, etc.).
  - Lee variables desde `.env`.
  - `get_settings()` usa cache para no recrear config en cada llamado.

### 2.3 Inyeccion de dependencias

- backend/app/core/dependencies.py
  - Decide que repositorio usar segun `repository_backend`.
  - Si `mysql`: usa `MySQLRepository`.
  - Si no: usa `MockRepository`.
  - Expone constructores de servicios (`get_auth_service`, `get_kpi_service`, etc.).

### 2.4 Seguridad y JWT

- backend/app/core/security.py
  - Maneja hash/validacion de password (bcrypt).
  - Crea tokens JWT (`create_access_token`).
  - Decodifica y valida token (`decode_token`).
  - Extrae token Bearer del header.
  - Valida claims y revisa revocacion por `jti`.

- backend/app/core/token_store.py
  - Blocklist en memoria para tokens cerrados (logout).
  - Si un `jti` esta en blocklist, el token queda invalidado.

## 3. API v1 (rutas)

### 3.1 Router raiz

- backend/app/api/v1/api.py
  - Junta y monta todos los routers de la version v1:
    - auth
    - health
    - catalogs
    - dashboard
    - kpis

### 3.2 Auth

- backend/app/api/v1/auth.py
  - `POST /auth/login`: valida usuario/clave y devuelve JWT.
  - `POST /auth/logout`: revoca token actual.
  - `GET /auth/me`: devuelve perfil del usuario logueado.

### 3.3 KPIs

- backend/app/api/v1/kpis.py
  - `POST /kpis/query`: endpoint principal para consultar series KPI.
  - Requiere autenticacion.
  - Toma payload validado y delega en `KpiService`.

### 3.4 Catalogos

- backend/app/api/v1/catalogs.py
  - `GET /catalogs/filters`: devuelve filtros disponibles para UI.
  - `GET /catalogs/kpis`: devuelve catalogo de KPIs.

### 3.5 Dashboard

- backend/app/api/v1/dashboard.py
  - `GET /dashboard/summary`: tarjetas resumen.
  - `GET /dashboard/charts`: series para graficos.
  - `GET /dashboard/table`: datos tabulares.

### 3.6 Health

- backend/app/api/v1/health.py
  - `GET /health`: chequeo basico de vida del servicio.

## 4. Services (logica de negocio)

- backend/app/services/auth_service.py
  - Login, logout, me.
  - Valida password en 3 formatos:
    - plano
    - md5
    - hash bcrypt
  - Emite token JWT y arma respuesta publica de usuario.

- backend/app/services/kpi_service.py
  - Capa simple que delega `query_kpis` al repositorio activo.

- backend/app/services/catalog_service.py
  - Devuelve filtros y catalogo de KPIs via repositorio.

- backend/app/services/dashboard_service.py
  - Devuelve summary/charts/table via repositorio.

## 5. Repositories (acceso a datos)

### 5.1 Contratos

- backend/app/repositories/interfaces.py
  - Define interfaces abstractas:
    - `AuthRepository`
    - `AnalyticsRepository`
  - Obliga a que mock y mysql tengan la misma "forma" de metodos.

### 5.2 MockRepository

- backend/app/repositories/mock_repository.py
  - Fuente de datos fake para desarrollo sin DB.
  - Permite probar frontend/API rapido cuando MySQL no esta disponible.

### 5.3 MySQLRepository

- backend/app/repositories/mysql_repository.py
  - Conexion real a MySQL (db `incc`).
  - Ejecuta SQL para:
    - auth de usuario
    - filtros y catalogo
    - dashboard
    - query KPI con filtros y granularidad
  - Funciones clave:
    - `_execute`: ejecuta SQL y devuelve filas tipo dict.
    - `_date_clause`: arma filtro de fechas valido.
    - `_normalize_act_type`: normaliza filtro de tipo de acto.
    - `_period_expr`: define expresion SQL para day/week/month.
    - `query_kpis`: corazon de consulta KPI (elige query por kpi_key).

## 6. Schemas (contratos de entrada/salida)

- backend/app/schemas/auth.py
  - Modelos para login/logout/me.

- backend/app/schemas/kpis.py
  - Payload de query KPI (`kpi_keys`, `filters`, `granularity`).
  - Respuesta de series y puntos.

- backend/app/schemas/catalogs.py
  - Estructura de filtros y definiciones KPI.

- backend/app/schemas/dashboard.py
  - Estructura de tarjetas, graficos y tabla del dashboard.

- backend/app/schemas/health.py
  - Respuesta de health check.

## 7. Tests base

- backend/app/tests/test_api.py
  - Verifica endpoints base:
    - health
    - login/me
    - auth obligatoria en dashboard
    - query KPI

- backend/app/tests/test_integration_mysql.py
  - Test de integracion opcional con MySQL real.
  - Se habilita con variable de entorno `RUN_INTEGRATION_DB_TESTS=1`.

## 8. Donde tocar cuando cambias KPIs o SQL

Si agregas o cambias un KPI, revisar en este orden:

1. backend/app/schemas/kpis.py
2. backend/app/repositories/interfaces.py (si cambia contrato)
3. backend/app/repositories/mysql_repository.py (SQL real)
4. backend/app/repositories/mock_repository.py (paridad mock)
5. backend/app/services/kpi_service.py
6. backend/app/api/v1/kpis.py
7. backend/app/tests/test_api.py
8. backend/app/tests/test_integration_mysql.py

Si tambien impacta dashboard:

- backend/app/api/v1/dashboard.py
- backend/app/services/dashboard_service.py
- backend/app/schemas/dashboard.py
- backend/app/repositories/mysql_repository.py

## 9. Flujo de request KPI explicado con ejemplo

Ejemplo: `POST /api/v1/kpis/query`

1. Entra request al endpoint en `api/v1/kpis.py`.
2. Se valida token (auth) y payload (schema).
3. Endpoint llama `KpiService.query(...)`.
4. Service llama `analytics_repository.query_kpis(...)`.
5. Dependiendo de config:
   - mock: devuelve datos simulados.
   - mysql: ejecuta SQL real.
6. Se devuelve respuesta con formato del schema.

## 10. Regla practica para no perderse

Cuando algo falla, depurar por capas:

1. Endpoint (llega bien?)
2. Schema (payload/response validos?)
3. Service (logica correcta?)
4. Repository (SQL/DB correcta?)
5. Config (.env/backend seleccionado?)

Con esta secuencia, encontrar errores es mucho mas rapido.
