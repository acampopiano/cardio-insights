# Guia simple para trabajar KPIs y SQL en Cardio Insights

Esta guia es para empezar desde cero.
Objetivo: que puedas bajar el repo, crear tu rama, tocar KPIs/SQL y subir cambios sin romper nada.

## 1) Primer arranque (desde que abres VS Code)

1. Abre VS Code.
2. Presiona `Ctrl+Shift+P`.
3. Escribe `Git: Clone` y elige esa opcion.
4. Pega la URL del repo. (https://github.com/acampopiano/cardio-insights.git)
5. Elige una carpeta en tu PC para guardarlo.
6. Cuando termine, haz clic en `Open`.

## 2) Configurar Git (solo una vez en tu PC)

Abre terminal en VS Code (`Terminal > New Terminal`) y ejecuta:

```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@ejemplo.com"
```

## 3) Ir a la rama correcta

Regla del equipo:

- `main` = estable
- `develop` = integracion
- `feature/*` = tu trabajo

En terminal:

```powershell
git fetch origin
git switch develop
git pull --ff-only origin develop
```

Si no ves archivos Python dentro de `backend/app`, casi seguro estas en la rama incorrecta. Vuelve a `develop`.

## 4) Crear una rama por feature (siempre)

Ejemplos de nombre:

- `feature/kpi-mortality-30d`
- `feature/sql-filtro-fechas-kpis`
- `feature/dashboard-kpi-icu-los`

Comando:

```powershell
git switch -c feature/nombre-corto-y-claro
```

## 5) Que archivos tocar para KPIs y SQL

### Archivos principales (backend)

- `backend/app/api/v1/kpis.py`
  - Endpoint de consulta KPI.
  - Aqui se validan/reciben filtros del request.

- `backend/app/services/kpi_service.py`
  - Logica de negocio KPI.
  - Aqui suele estar la orquestacion entre API y repositorio.

- `backend/app/repositories/interfaces.py`
  - Contrato de funciones del repositorio.
  - Si agregas una consulta nueva, actualiza la interfaz.

- `backend/app/repositories/mysql_repository.py`
  - SQL real contra MySQL (`incc`).
  - Aqui se cambia casi todo lo importante de consultas KPI y filtros.

- `backend/app/repositories/mock_repository.py`
  - Datos mock para desarrollo offline.
  - Si agregas KPI nuevo, agrega respuesta mock para mantener compatibilidad.

- `backend/app/schemas/kpis.py`
  - Modelos de entrada/salida de KPIs.
  - Si cambias forma de respuesta o filtros, actualiza schemas.

### Archivos relacionados (cuando el KPI aparece en dashboard)

- `backend/app/api/v1/dashboard.py`
- `backend/app/services/dashboard_service.py`
- `backend/app/schemas/dashboard.py`
- `backend/app/repositories/mysql_repository.py` (bloques de dashboard)

### Tests que debes tocar

- `backend/app/tests/test_api.py`
- `backend/app/tests/test_integration_mysql.py`

Si agregas KPI/consulta y no ajustas tests, el cambio queda incompleto.

## 6) Levantar backend local

En terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crear variables de entorno:

```powershell
Copy-Item .env.example .env
```

Luego edita `.env` con tus datos de DB local.

Levantar API:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Swagger:

- http://127.0.0.1:8000/docs

## 7) Flujo minimo para cambiar un KPI

1. Crea rama `feature/...` desde `develop`.
2. Cambia schema si cambia contrato (`schemas/kpis.py`).
3. Cambia interfaz (`repositories/interfaces.py`) si agregas metodo nuevo.
4. Implementa SQL en `repositories/mysql_repository.py`.
5. Ajusta mock en `repositories/mock_repository.py`.
6. Ajusta servicio (`services/kpi_service.py`) y endpoint (`api/v1/kpis.py`) si aplica.
7. Corre tests.
8. Levanta API y prueba en `/docs`.
9. Commit + push + PR a `develop`.

## 8) Comandos de calidad antes de subir

Desde `backend`:

```powershell
pytest -q
$env:RUN_INTEGRATION_DB_TESTS="1"
pytest -q app/tests/test_integration_mysql.py
Remove-Item Env:RUN_INTEGRATION_DB_TESTS
```

## 9) Commit y push

```powershell
git status
git add .
git commit -m "feat(kpi): agrega KPI X con filtros Y"
git push -u origin feature/nombre-corto-y-claro
```

Luego crea Pull Request hacia `develop`.

## 10) Checklist de Definition of Done

Antes de abrir PR, confirma todo esto:

- [ ] Estoy en rama `feature/*`, no en `main`.
- [ ] El cambio compila y levanta local.
- [ ] KPIs responden bien en `/docs`.
- [ ] Tests base pasan.
- [ ] Si hay SQL nuevo, esta cubierto por test o caso manual documentado.
- [ ] Actualice mock si cambie contrato.
- [ ] PR apunta a `develop`.

## 11) Errores comunes (y solucion rapida)

- Error: `uvicorn no se reconoce`
  - Usa `python -m uvicorn ...` con el venv activo.

- Error: no aparecen archivos del backend
  - Haz `git switch develop` y `git pull --ff-only origin develop`.

- Error: no conecta MySQL
  - Revisa `.env` (host, puerto, user, password, database).

- Error: KPI nuevo rompe dashboard
  - Revisa schema, mock y consultas dashboard en conjunto.

## 12) Regla de oro del repo

Nunca pushear directo a `main`.
Siempre: `feature/*` -> PR -> `develop`.
