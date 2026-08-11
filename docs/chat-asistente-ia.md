# Asistente IA (chat en lenguaje natural sobre los datos)

Módulo de chat que permite preguntar en español sobre los datos clínicos del INCC y
obtiene la respuesta consultando la base **en tiempo real**. Traduce la pregunta a SQL
con un LLM (OpenAI), valida y ejecuta esa consulta en modo **solo lectura**, y redacta
la respuesta en lenguaje natural.

Es un módulo **autónomo**: no usa el motor anterior de KPIs (`KpiRegistry`,
`NaturalQueryService`, `llm_gateway`, endpoints `/kpis`, `/analytics`, etc.). El SQL se
genera dinámicamente en cada pregunta; no hay plantillas ni KPIs predefinidos.

---

## Cómo funciona (flujo)

```
Pregunta + historial de la conversación
        │
        ▼
1) OpenAI genera el SQL  (gpt-5-mini + SCHEMA_CONTEXT + ejemplos few-shot, salida JSON estructurada)
        │
        ▼
2) sql_guard valida      (un solo SELECT, tablas permitidas, sin DDL/DML, columnas existentes, fuerza LIMIT)
        │
        ▼
3) Ejecución read-only   (usuario MySQL dedicado + transacción READ ONLY + timeout)
        │
        ├── ¿error de validación o de MySQL? ──► se le devuelve el error al LLM
        │      para que CORRIJA el SQL y se reintenta (hasta CHAT_MAX_SQL_ATTEMPTS).
        ▼
4) OpenAI redacta la respuesta en lenguaje natural (con unidades y, en comparativas, % de variación)
        │
        ▼
Respuesta = texto + SQL ejecutado + filas (tabla auditable)
```

> El bucle de reintento con auto-corrección (paso 3) es lo que hace al chat robusto: si el
> modelo genera una columna inexistente o un SQL que falla, recibe el mensaje de error exacto
> y vuelve a intentar, en vez de devolver un error al usuario.

---

## Archivos

Backend:

- `backend/app/api/v1/chat.py` — endpoint `POST /api/v1/chat` (requiere login).
- `backend/app/schemas/chat.py` — modelos de request/response.
- `backend/app/services/chat_service.py` — orquesta todo: genera SQL, valida, ejecuta (con
  reintento + auto-corrección), resume. Contiene el `SCHEMA_CONTEXT` (esquema real + reglas de
  negocio) y los ejemplos few-shot. Introspecta las columnas reales (`INFORMATION_SCHEMA`,
  cacheadas) para validar y ajusta los parámetros del modelo según la familia (ver más abajo).
- `backend/app/services/sql_guard.py` — guardrails con `sqlglot` (allowlist de tablas, solo
  SELECT, validación de columnas existentes, LIMIT).
- `backend/db/create_chat_user.sql` — script para crear el usuario MySQL de solo lectura.

Frontend:

- `frontend/src/routes/AgentePage.tsx` — UI del chat (burbujas, sugerencias, tabla de datos, "Ver SQL").
- `frontend/src/features/chat/chatApi.ts` — cliente HTTP del endpoint.

---

## Seguridad (defensa en capas)

De más fuerte a más débil. La idea: aunque el LLM se equivoque, que sea imposible hacer daño.

1. **Usuario MySQL de solo lectura** (`cardio_chat`): solo `SELECT` y solo sobre las tablas
   clínicas (sin acceso a usuarios/claves). Es la barrera real, a nivel base de datos.
2. **Transacción `READ ONLY`**: la consulta corre dentro de `START TRANSACTION READ ONLY`,
   así MySQL rechaza cualquier escritura aunque el usuario tuviera permisos.
3. **Validación con `sqlglot`**: solo una sentencia, debe ser `SELECT`, solo tablas de la
   allowlist, sin `INSERT/UPDATE/DELETE/DDL` ni multi-statement.
4. **Validación de columnas**: las columnas calificadas (`alias.columna`) deben existir
   realmente en su tabla (se introspecta `INFORMATION_SCHEMA` una vez por proceso). Atrapa
   columnas inventadas antes de tocar la base; si falla la introspección, no bloquea.
5. **Límites de ejecución**: `LIMIT` forzado + `max_execution_time` (timeout de query).

Tablas permitidas (allowlist en `sql_guard.py`):
`flow_coordina`, `dat_cirugia`, `call_ptcamaster`, `flow_procedimientocardiologia`,
`sqlsalud_fallece`.

`sqlsalud_fallece` aporta **fallecimientos con causa** (join `sf.NroHistoria = f.CodPac`).
Usarla para mortalidad a 30 días post-cirugía/PTCA y desglose por causa; la mortalidad al
egreso “clásica” sigue pudiendo resolverse con `flow_procedimientocardiologia.FechaFallece`.

---

## Configuración (`backend/.env`)

```env
CHAT_ENABLED=true
OPENAI_API_KEY=sk-...            # API key real de OpenAI (con billing activo)
OPENAI_MODEL=gpt-5-mini          # modelo actual (ver nota sobre modelos abajo)

# Usuario MySQL de SOLO LECTURA para el chat (no reusar el usuario principal)
CHAT_MYSQL_USER=cardio_chat
CHAT_MYSQL_PASSWORD=la-clave-del-usuario-readonly

CHAT_MAX_ROWS=500                # tope de filas por consulta
CHAT_QUERY_TIMEOUT_MS=5000       # timeout de la consulta (ms)
CHAT_MAX_SQL_ATTEMPTS=3          # intentos de generación de SQL (>1 habilita auto-corrección)
```

El chat se conecta al mismo servidor MySQL que el resto del backend
(`MYSQL_HOST`/`MYSQL_PORT`/`MYSQL_DATABASE`), pero con el usuario `CHAT_MYSQL_USER`.

### Modelo de OpenAI y latencia

El modelo se cambia solo con `OPENAI_MODEL` (sin tocar código). El servicio ajusta los
parámetros de la llamada según la familia, en `chat_service.py` (`_completion_kwargs`):

- **Serie GPT-5** (ej. `gpt-5-mini`): es un modelo de razonamiento. No acepta `temperature`
  distinta de 1, así que ese parámetro **no se envía**; y se usa `reasoning_effort="minimal"`
  para minimizar la latencia (el text-to-SQL ya está muy guiado por el `SCHEMA_CONTEXT` y los
  few-shot, no necesita razonamiento pesado).
- **o1/o3/o4**: tampoco aceptan `temperature` custom; no se envían parámetros extra.
- **gpt-4o / gpt-4.1 / etc.**: se envía la `temperature` (0 para generar SQL, 0.2 para redactar).

Comparativa rápida (orientativa): `gpt-4o-mini` es el más rápido y barato; `gpt-5-mini` es más
capaz (mejor en seguimientos y comparativas) a cambio de algo más de latencia y costo. Si se
cambia de familia, solo hay que editar `OPENAI_MODEL`.

### Crear el usuario de solo lectura

Debe ejecutarlo un administrador de MySQL (root o cuenta con `GRANT OPTION`).
Ver `backend/db/create_chat_user.sql`:

```sql
CREATE USER IF NOT EXISTS 'cardio_chat'@'%' IDENTIFIED BY 'una-clave-fuerte';
GRANT SELECT ON incc.flow_coordina                 TO 'cardio_chat'@'%';
GRANT SELECT ON incc.dat_cirugia                   TO 'cardio_chat'@'%';
GRANT SELECT ON incc.call_ptcamaster               TO 'cardio_chat'@'%';
GRANT SELECT ON incc.flow_procedimientocardiologia TO 'cardio_chat'@'%';
GRANT SELECT ON incc.sqlsalud_fallece              TO 'cardio_chat'@'%';
FLUSH PRIVILEGES;
```

> Provisional: si todavía no existe `cardio_chat`, se puede usar el usuario principal
> en `CHAT_MYSQL_USER`; las capas de software (sqlglot + READ ONLY) igual bloquean
> escrituras, pero conviene migrar al usuario dedicado para tener también la barrera
> por privilegios.

---

## Reglas de negocio que conoce el chat

Están descritas en texto dentro de `SCHEMA_CONTEXT` (no en código), extraídas del SQL real
de producción. Las más importantes:

- Fechas `<= '1900-01-01'` son nulos lógicos: siempre se filtran con `> '1900-01-01'`.
- "Realizado": `f.Realizado = 255 AND f.FechaRealizado > '1900-01-01'`.
- Cirugía = join `dat_cirugia d` con `flow_coordina f` por `f.Cod = d.CodCoordina`.
- PTCA = join `call_ptcamaster c` con `flow_coordina f` por `f.Cod = c.CodCoordina`.
- Espera (días) = `DATEDIFF(f.FechaRealizado, f.FechaCoordina)` (ambas fechas válidas, diferencia >= 0).
- Mortalidad al egreso = sobre `flow_procedimientocardiologia` (independiente), `FechaFallece > '1900-01-01'` indica fallecido.
- Valores negativos como `-99` son centinelas de "sin dato" y se excluyen en promedios.

> Nota sobre datos históricos: en 2022–2023 la fecha de coordinación se cargaba igual a la
> de realización, por lo que las métricas de "espera" de esos años salen ~0 por la forma de
> carga, no por la realidad clínica. Recién desde 2024 la espera se registra de forma significativa.

---

## Robustez y calidad de las respuestas

Mejoras incorporadas para reducir fallos y dar respuestas más útiles:

- **Auto-corrección con reintento**: si el SQL falla (columna inexistente, error de MySQL,
  validación) se le devuelve el error exacto al modelo y se reintenta hasta
  `CHAT_MAX_SQL_ATTEMPTS`. El usuario solo ve un error si se agotan todos los intentos.
- **Validación de columnas**: además de la allowlist de tablas, se chequea que las columnas
  `alias.columna` existan de verdad (introspección de `INFORMATION_SCHEMA`).
- **Comparaciones en una sola consulta**: el prompt y los few-shot enseñan a resolver
  comparativas (año vs año, períodos, categorías) con `UNION ALL` (columna etiqueta, ideal para
  tabla) o agregación condicional `CASE`. El modelo no abandona una comparación por creer que
  necesita dos consultas.
- **Preguntas de seguimiento**: usa el historial para resolver "y el anterior", "comparalos",
  etc. "El anterior" = el período inmediatamente anterior al de la respuesta previa. Por defecto
  responde solo ese valor; arma una comparación solo si se pide explícitamente.
- **Sin repreguntas**: ante ambigüedad elige la interpretación más directa en vez de pedir
  confirmación. `can_answer=false` se reserva para lo genuinamente imposible con el esquema.

> Nota sobre "tipos de procedimiento": en este esquema el tipo de acto es **implícito por la
> tabla** (Cirugía = `dat_cirugia`, PTCA = `call_ptcamaster`); no hay una columna con el nombre
> fino del procedimiento. Los rankings "por tipo" se responden a nivel Cirugía vs PTCA.

---

## Probar el chat

1. Backend y frontend levantados (`uvicorn` en `:8000`, `vite` en `:5173`).
2. Login en la UI.
3. Ir a **Asistente IA**.

Ejemplos:

- "¿Cuántas cirugías se realizaron en 2024?"
- "Mostrame la mortalidad al egreso por mes en 2025" (devuelve tabla)
- "Compará la mortalidad al egreso entre 2024 y 2025" (incluye diferencia y % de variación)
- "Comparame la cantidad de cirugías y de PTCA por mes en 2024" (tabla comparativa)
- Seguimiento: tras "¿Cuántas cirugías se realizaron en 2024?", preguntar "¿y en el anterior?"
  (resuelve el valor de 2023 usando el contexto, sin repreguntar)

La respuesta muestra el texto y, debajo, los desplegables **"Ver consulta SQL"** y
**"Ver datos"** (la tabla se abre sola cuando hay más de una fila).

---

## Cómo extender

- **Más métricas / tablas**: agregar las columnas y reglas en `SCHEMA_CONTEXT`
  (`chat_service.py`) y, si es otra tabla, sumarla a la allowlist en `sql_guard.py`
  y dar `SELECT` al usuario `cardio_chat`.
- **Mejorar precisión**: agregar ejemplos few-shot (`_FEW_SHOT`) con pares pregunta→SQL correctos.
- **Formato de respuesta**: ajustar `_ANSWER_SYSTEM_PROMPT`.
- **Cambiar el modelo**: editar `OPENAI_MODEL` en `.env`. Si es de otra familia, los parámetros
  (`temperature` / `reasoning_effort`) se ajustan solos en `_completion_kwargs`.
- **Cantidad de reintentos**: `CHAT_MAX_SQL_ATTEMPTS` (1 = sin auto-corrección).

---

## Limitaciones

- Solo responde lo que se puede obtener con un `SELECT` sobre las tablas permitidas.
- La calidad depende del `SCHEMA_CONTEXT`: si el esquema real cambia, hay que actualizarlo.
- Requiere conexión a OpenAI y billing activo.
