# Guia rapida del backend para el equipo

## Estado actual del proyecto (importante)

Hoy el repo esta subido solo con trabajo de backend.

Verificacion hecha:

- En el commit actual, del frontend solo existe `frontend/.gitkeep`.
- El resto de archivos de frontend estan locales, pero **sin subir**.

Conclusion: podes trabajar tranquilo en backend, porque frontend todavia no se esta publicando.

## Que ya se hizo en backend (explicado simple)

El backend ya tiene una base bastante completa para arrancar:

- Login con token (usuario y contrasena).
- Endpoints para salud del sistema, catalogos, dashboard y KPIs.
- Consultas de analitica (tabla, ranking y cubo).
- Modo de datos mock (para avanzar rapido sin depender de base real).
- Modo MySQL (para conectar con datos reales).
- Tests automaticos para validar que la API responde bien.

En pocas palabras: la API ya esta lista para probar, integrar y seguir creciendo.

## Como bajar el repo y levantar backend (paso a paso, sin vueltas)

### 1. Clonar el repo

```powershell
git clone <URL_DEL_REPO>
cd cardio-insights
```

### 2. Entrar al backend

```powershell
cd backend
```

### 3. Crear entorno virtual (una sola vez)

```powershell
python -m venv .venv
```

### 4. Activarlo

```powershell
.venv\Scripts\Activate.ps1
```

Si PowerShell te bloquea scripts, ejecuta esto una vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Y volve a correr la activacion.

### 5. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 6. Crear archivo de entorno

```powershell
copy .env.example .env
```

### 7. Levantar la API

```powershell
uvicorn app.main:app --reload --port 8000
```

Cuando levante, abrilo en el navegador:

- Swagger: http://localhost:8000/docs

## Lo mas importante: crear KPIs nuevos (sin programar)

URL directa para crear KPIs:

- http://localhost:8000/api/v1/kpi-designer/ui

Pasos simples:

1. Levanta el backend y entra a Swagger (http://localhost:8000/docs).
2. Hace login en POST /api/v1/auth/login con un usuario de prueba.
3. Copia el access_token de la respuesta.
4. Abri la URL del KPI Designer y pega el token cuando te lo pida.
5. Completa 4 campos: nombre del KPI, descripcion, granularidad y SQL.
6. Toca Generar snippets.
7. Copia el bloque registration_payload que te devuelve.
8. Vuelve a Swagger y pegalo en POST /api/v1/kpi-designer/register.
9. Usa query_payload_example para probar el KPI en POST /api/v1/kpis/query.

Tip rapido: si solo queres probar sin base real, deja el backend en modo mock.

## Usuario de prueba rapido (modo mock)

Si no cambiaste nada en `.env`, podes entrar con:

- Usuario: `admin`
- Contrasena: `Admin1234!`

## Como correr tests para chequear que todo esta bien

Desde `backend/` con el entorno activo:

```powershell
pytest
```

Si da verde, estas listo para trabajar sin sorpresas.

## Si queres usar MySQL real en vez de mock

En `.env`, cambiar/definir:

```env
REPOSITORY_BACKEND=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=tu_password
MYSQL_DATABASE=incc
```

Despues levantas igual con uvicorn.

## Forma recomendada de arrancar a trabajar

Orden simple para no marearse:

1. Levantar API y probar login en Swagger.
2. Probar `health`, `dashboard` y `kpis/query`.
3. Correr tests.
4. Recien ahi empezar cambios de codigo.

## Nota para el equipo

Por ahora mantenemos el foco en backend. El frontend queda local y **no se sube todavia**.
