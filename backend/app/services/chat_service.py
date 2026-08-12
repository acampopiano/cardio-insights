"""Asistente conversacional text-to-SQL sobre los datos clínicos.

Flujo:
    1. El LLM traduce la pregunta a un único SELECT de MySQL.
    2. sql_guard valida (solo SELECT, tablas permitidas) y fuerza LIMIT.
    3. Se ejecuta con un usuario MySQL de SOLO LECTURA.
    4. El LLM redacta la respuesta en lenguaje natural a partir de las filas.

No depende de KpiRegistry ni de los servicios de KPIs: es autónomo.
"""

from __future__ import annotations

import json
from typing import Any

import pymysql
from openai import OpenAI
from pymysql.cursors import DictCursor

from app.core.config import get_settings
from app.schemas.chat import ChatMessage, ChatResponse
from app.services.sql_guard import ALLOWED_TABLES, UnsafeQueryError, sanitize

# Contexto que el modelo necesita para escribir SQL correcto. Es lean: vive como
# texto, no como una capa de software. Refleja el esquema REAL de producción y
# las reglas validadas en las consultas existentes. Si cambia el esquema, se edita acá.
SCHEMA_CONTEXT = """\
Base de datos MySQL `incc` (Instituto Nacional de Cirugía Cardíaca). Esquema de producción.
Las tablas tienen muchísimas columnas; abajo SOLO las relevantes para análisis.

flow_coordina (alias f) — tabla central: una fila por acto/procedimiento coordinado.
  - Cod INT PK
  - FechaCoordina DATE          -- cuándo se coordinó
  - FechaRealizado DATE         -- cuándo se realizó (<= '1900-01-01' = no realizado)
  - FechaEgreso DATE            -- egreso
  - FechaFinTramite, FechaInputTramite DATE -- fechas de trámite/autorización
  - Realizado SMALLINT          -- 255 = realizado
  - Autorizado SMALLINT         -- 255 = autorizado
  - EdadCoo INT                 -- edad del paciente al coordinar
  - CodPac INT                  -- id interno de paciente (sin nombre)
  - CodSeguroCoo INT            -- centro/seguro que deriva al paciente
  - CodCoordinaReglaMotivo INT  -- 105,109,120 = reingreso/readmisión

dat_cirugia (alias d) — una fila = una CIRUGÍA. Join: d.CodCoordina = f.Cod
  - k_id BIGINT PK
  - CodCoordina INT
  - POestadiaUCI INT            -- días de estadía postoperatoria en UCI

call_ptcamaster (alias c) — una fila = una PTCA/angioplastia. Join: c.CodCoordina = f.Cod
  - Cod INT PK
  - CodCoordina INT

flow_procedimientocardiologia (alias p) — resultados (mortalidad/egresos). Se usa de forma INDEPENDIENTE (sin join).
  - Cod INT PK
  - FechaFallece DATE           -- <= '1900-01-01' = NO falleció; > '1900-01-01' = falleció
  - FechaEgreso DATE            -- egreso hospitalario

sqlsalud_fallece (alias sf) — registro de FALLECIMIENTOS con CAUSA. Preferirla cuando pregunten por causa de muerte o mortalidad post-procedimiento con causa.
  - NroHistoria INT             -- = flow_coordina.CodPac (y pac_ficha.Cod). NO es pac_ficha.NroHistoria.
  - Fecha DATETIME              -- fecha de fallecimiento (<= '1900-01-01' = inválida)
  - IdTipo / Tipo               -- causa: 1 Cardíaca, 2 Neurológica, 3 Renal, 4 Vascular, 5 Sepsis, 6 Pulmonar, 7 Hemorragia, 8 Tumor, 9 Suicidio, 10 Otras, 11 Sin Identificar
  - Nota VARCHAR                -- texto libre
  Una fila por fallecido (~5195). Filtrar NroHistoria > 0 y Fecha > '1900-01-01'.

Reglas de negocio CRÍTICAS (validadas en producción):
- Fechas <= '1900-01-01' son nulos lógicos: SIEMPRE filtralas con `> '1900-01-01'`.
- "Realizado": f.Realizado = 255 AND f.FechaRealizado > '1900-01-01'.
- Volumen de CIRUGÍA: dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina, con f.FechaRealizado > '1900-01-01'.
- Volumen de PTCA: call_ptcamaster c JOIN flow_coordina f ON f.Cod = c.CodCoordina, con f.FechaRealizado > '1900-01-01'.
- Volumen TOTAL de actividad: COUNT(*) de flow_coordina f con f.Realizado = 255 AND f.FechaRealizado > '1900-01-01'.
- Tiempo de espera (días): DATEDIFF(f.FechaRealizado, f.FechaCoordina), con ambas fechas > '1900-01-01' y la diferencia >= 0.
- MORTALIDAD al egreso (%): usar SOLO flow_procedimientocardiologia p (sin join):
  ROUND(100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2),
  filtrando p.FechaEgreso > '1900-01-01' y agrupando por p.FechaEgreso.
- MORTALIDAD con CAUSA / a 30 días post-cirugía o PTCA: JOIN sqlsalud_fallece sf ON sf.NroHistoria = f.CodPac
  AND sf.Fecha > '1900-01-01' AND DATEDIFF(sf.Fecha, f.FechaRealizado) BETWEEN 0 AND 30.
  Causa cardíaca: sf.IdTipo = 1. Excluir sf.NroHistoria = 0.
- Estadía UCI promedio: AVG(d.POestadiaUCI) filtrando SIEMPRE d.POestadiaUCI >= 0 (los valores negativos como -99 son "sin dato").
- Valores numéricos negativos como -99 son centinelas de "sin dato": excluilos en promedios/sumas (campo >= 0).
- Participación PTCA (%): sobre flow_coordina f LEFT JOIN dat_cirugia d ON d.CodCoordina=f.Cod LEFT JOIN call_ptcamaster c ON c.CodCoordina=f.Cod,
  ROUND(100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0), 2), con f.FechaRealizado > '1900-01-01'.
- Reingreso/readmisión: flow_coordina f con f.CodCoordinaReglaMotivo IN (105,109,120) y f.Realizado = 255.
- Agrupar por mes: DATE_FORMAT(fecha, '%Y-%m'); por año: YEAR(fecha). Para actividad usar FechaRealizado; para mortalidad usar FechaEgreso.
- NO hay nombres de pacientes ni datos de contacto en estas tablas.
"""

# Ejemplos verdad-de-producción: anclan al modelo a los patrones correctos.
_FEW_SHOT = """\
Ejemplos de traducción correcta:

P: ¿Cuántas cirugías se realizaron en 2024?
SQL: SELECT COUNT(*) AS total FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina WHERE f.FechaRealizado > '1900-01-01' AND YEAR(f.FechaRealizado) = 2024

P: Mostrame la mortalidad al egreso por mes en 2025
SQL: SELECT DATE_FORMAT(p.FechaEgreso, '%Y-%m') AS mes, ROUND(100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2) AS mortalidad_pct FROM flow_procedimientocardiologia p WHERE p.FechaEgreso > '1900-01-01' AND YEAR(p.FechaEgreso) = 2025 GROUP BY mes ORDER BY mes

P: ¿Cuál fue la espera promedio en días el año pasado?
SQL: SELECT ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)), 2) AS espera_promedio FROM flow_coordina f WHERE f.FechaRealizado > '1900-01-01' AND f.FechaCoordina > '1900-01-01' AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0 AND YEAR(f.FechaRealizado) = YEAR(CURDATE()) - 1

P: Estadía promedio en UCI por mes en 2024
SQL: SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS mes, ROUND(AVG(d.POestadiaUCI), 2) AS estadia_uci_promedio FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina WHERE f.FechaRealizado > '1900-01-01' AND d.POestadiaUCI >= 0 AND YEAR(f.FechaRealizado) = 2024 GROUP BY mes ORDER BY mes

P: Comparame el tiempo de espera promedio del año pasado contra el anterior (en tabla)
SQL: SELECT 'Año pasado' AS periodo, ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)), 2) AS espera_promedio_dias FROM flow_coordina f WHERE f.FechaRealizado > '1900-01-01' AND f.FechaCoordina > '1900-01-01' AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0 AND YEAR(f.FechaRealizado) = YEAR(CURDATE()) - 1 UNION ALL SELECT 'Año anterior', ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)), 2) FROM flow_coordina f WHERE f.FechaRealizado > '1900-01-01' AND f.FechaCoordina > '1900-01-01' AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0 AND YEAR(f.FechaRealizado) = YEAR(CURDATE()) - 2

P: Comparame las cirugías realizadas en 2024 vs 2023
SQL: SELECT 2024 AS anio, COUNT(*) AS total_cirugias FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina WHERE f.FechaRealizado > '1900-01-01' AND YEAR(f.FechaRealizado) = 2024 UNION ALL SELECT 2023, COUNT(*) FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina WHERE f.FechaRealizado > '1900-01-01' AND YEAR(f.FechaRealizado) = 2023

P (seguimiento; antes se preguntó "¿Cuántas cirugías se realizaron en 2024?"): ¿y en el anterior?
SQL: SELECT COUNT(*) AS total_cirugias FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina WHERE f.FechaRealizado > '1900-01-01' AND YEAR(f.FechaRealizado) = 2023

P: ¿Cuántas muertes a 30 días post-cirugía hubo en 2024 y cuántas fueron cardíacas?
SQL: SELECT COUNT(*) AS cirugias, SUM(CASE WHEN sf.Fecha > '1900-01-01' AND DATEDIFF(sf.Fecha, f.FechaRealizado) BETWEEN 0 AND 30 THEN 1 ELSE 0 END) AS muertes_30d, SUM(CASE WHEN sf.IdTipo = 1 AND sf.Fecha > '1900-01-01' AND DATEDIFF(sf.Fecha, f.FechaRealizado) BETWEEN 0 AND 30 THEN 1 ELSE 0 END) AS muertes_30d_cardiaca FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina LEFT JOIN sqlsalud_fallece sf ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0 WHERE f.Realizado = 255 AND f.FechaRealizado > '1900-01-01' AND YEAR(f.FechaRealizado) = 2024

P: Fallecidos por causa en 2025
SQL: SELECT sf.Tipo AS causa, COUNT(*) AS total FROM sqlsalud_fallece sf WHERE sf.Fecha > '1900-01-01' AND sf.NroHistoria > 0 AND YEAR(sf.Fecha) = 2025 GROUP BY sf.Tipo ORDER BY total DESC
"""

_SQL_SYSTEM_PROMPT = f"""\
Eres un asistente que traduce preguntas en español sobre datos clínicos a UNA sola consulta SQL de MySQL (SELECT).

{SCHEMA_CONTEXT}

{_FEW_SHOT}

Reglas estrictas:
- Devuelve SOLO un SELECT (sin INSERT/UPDATE/DELETE/DDL, sin múltiples sentencias, sin punto y coma final).
- Usa únicamente las tablas y columnas listadas arriba. NO inventes columnas ni tablas.
- Aplicá SIEMPRE las reglas de negocio (filtros de fecha > '1900-01-01', Realizado=255, joins correctos).
- Usá can_answer=false ÚNICAMENTE cuando sea genuinamente imposible con el esquema/datos disponibles. NUNCA lo uses por ambigüedad ni para pedir aclaraciones.
- NUNCA hagas preguntas de vuelta ni pidas confirmación. Ante varias interpretaciones posibles, elegí la MÁS DIRECTA y respondé con la consulta.
- Agregá alias legibles a las columnas (ej. AS total, AS mes, AS espera_promedio).
- Las COMPARACIONES (entre años, períodos, categorías o métricas) SÍ se resuelven en UNA sola consulta: usá UNION ALL con una columna etiqueta (ideal para tabla) o agregación condicional con CASE. NUNCA respondas can_answer=false solo porque la pregunta sea una comparación.
- Si la pregunta es de seguimiento (ej. "y el anterior", "y en 2023?", "y la mortalidad?"), usá el contexto de la conversación para inferir la MISMA métrica con el nuevo período/filtro y devolvé esa consulta. "El anterior/previo" = el período inmediatamente anterior al de la respuesta previa (ej. si antes fue 2024, "el anterior" = 2023). Por defecto respondé SOLO ese nuevo valor; armá una comparación únicamente si el usuario lo pide explícitamente.
"""

_ANSWER_SYSTEM_PROMPT = """\
Eres un analista clínico. Respondes en español, de forma breve y clara, basándote ÚNICAMENTE en los datos provistos.
No inventes cifras que no estén en los resultados. Si los resultados están vacíos, dilo explícitamente.
Cuando haya varias filas, resume los puntos clave; no listes más de ~10 filas en prosa.
Incluí SIEMPRE la unidad de la cifra cuando se pueda inferir de la pregunta o del nombre de la columna:
días para esperas/estadías, % para porcentajes/tasas, y "casos"/"procedimientos" para conteos.
Cuando la pregunta sea una COMPARACIÓN (entre años, períodos, categorías o métricas), agregá SIEMPRE
la diferencia absoluta y la variación porcentual entre los valores comparados, e indicá si subió o bajó.
"""

_SQL_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sql_plan",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "can_answer": {"type": "boolean"},
                "sql": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["can_answer", "sql", "reason"],
        },
    },
}


# Cache de columnas reales por tabla (introspección de INFORMATION_SCHEMA).
# Se llena una vez por proceso; si la introspección falla, queda vacío y la
# validación de columnas simplemente no se aplica (el reintento la cubre).
_COLUMN_CACHE: dict[str, set[str]] | None = None


class ChatService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: OpenAI | None = None
        if self._settings.openai_api_key:
            self._client = OpenAI(api_key=self._settings.openai_api_key)

    def is_enabled(self) -> bool:
        return bool(self._settings.chat_enabled and self._client is not None)

    def _completion_kwargs(self, temperature: float) -> dict[str, Any]:
        """Parámetros de muestreo/latencia según el modelo configurado.

        - GPT-5: no acepta temperatura != 1; usamos reasoning_effort='minimal' para
          minimizar la latencia (el text-to-SQL está muy guiado y no necesita
          razonamiento pesado).
        - o1/o3/o4: tampoco aceptan temperatura custom; no enviamos parámetros extra.
        - Resto (gpt-4o, gpt-4.1, etc.): enviamos la temperatura indicada.
        """
        model = self._settings.openai_model.lower()
        if model.startswith("gpt-5"):
            return {"reasoning_effort": "minimal"}
        if model.startswith(("o1", "o3", "o4")):
            return {}
        return {"temperature": temperature}

    def ask(self, question: str, history: list[ChatMessage] | None = None) -> ChatResponse:
        history = history or []

        if not self.is_enabled():
            return ChatResponse(
                question=question,
                answer="El asistente no está disponible. Configura CHAT_ENABLED y OPENAI_API_KEY.",
                resolved=False,
                error="chat_disabled",
            )

        plan = self._generate_sql(question, history)
        if not plan.get("can_answer") or not str(plan.get("sql") or "").strip():
            reason = str(plan.get("reason") or "No se pudo interpretar la pregunta con los datos disponibles.")
            return ChatResponse(question=question, answer=reason, resolved=False, error="not_answerable")

        raw_sql = str(plan["sql"])
        attempts = max(1, int(self._settings.chat_max_sql_attempts))
        allowed_columns = self._allowed_columns()
        last_error = ""
        last_sql = raw_sql

        for attempt in range(attempts):
            is_last = attempt == attempts - 1

            # Validación de seguridad (defensa en profundidad).
            try:
                safe_sql = sanitize(raw_sql, self._settings.chat_max_rows, allowed_columns)
            except UnsafeQueryError as exc:
                last_error = f"unsafe_sql: {exc}"
                last_sql = raw_sql
                if is_last:
                    break
                raw_sql = self._fix_sql(question, history, raw_sql, str(exc))
                if not raw_sql:
                    break
                continue

            last_sql = safe_sql

            # Ejecución read-only. Si falla, devolvemos el error de MySQL al LLM para que corrija.
            try:
                rows = self._run_readonly(safe_sql)
            except Exception as exc:  # noqa: BLE001 - error de ejecución se reintenta/reporta
                last_error = f"db_error: {exc}"
                if is_last:
                    break
                raw_sql = self._fix_sql(question, history, safe_sql, str(exc))
                if not raw_sql:
                    break
                continue

            answer = self._summarize(question, rows)
            return ChatResponse(
                question=question,
                answer=answer,
                resolved=True,
                sql=safe_sql,
                rows=rows,
                row_count=len(rows),
            )

        return ChatResponse(
            question=question,
            answer="No pude resolver la consulta de forma segura tras varios intentos.",
            resolved=False,
            sql=last_sql,
            error=last_error or "unresolved",
        )

    def _generate_sql(self, question: str, history: list[ChatMessage]) -> dict[str, Any]:
        assert self._client is not None
        messages: list[dict[str, str]] = [{"role": "system", "content": _SQL_SYSTEM_PROMPT}]
        for msg in history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": question})

        completion = self._client.chat.completions.create(
            model=self._settings.openai_model,
            messages=messages,  # type: ignore[arg-type]
            response_format=_SQL_RESPONSE_SCHEMA,  # type: ignore[arg-type]
            **self._completion_kwargs(0),
        )
        content = completion.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"can_answer": False, "sql": "", "reason": "Respuesta del modelo no interpretable."}

    def _fix_sql(
        self,
        question: str,
        history: list[ChatMessage],
        previous_sql: str,
        error_message: str,
    ) -> str:
        """Pide al LLM corregir el SQL a partir del error. Devuelve el SQL corregido o ''."""
        assert self._client is not None
        messages: list[dict[str, str]] = [{"role": "system", "content": _SQL_SYSTEM_PROMPT}]
        for msg in history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": question})
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {"can_answer": True, "sql": previous_sql, "reason": ""}, ensure_ascii=False
                ),
            }
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Ese SQL falló con este error de MySQL:\n{error_message}\n\n"
                    "Corregí el SQL respetando el esquema y las reglas de negocio "
                    "(usá solo columnas y tablas que existan). Devolvé el JSON con el SQL corregido."
                ),
            }
        )

        try:
            completion = self._client.chat.completions.create(
                model=self._settings.openai_model,
                messages=messages,  # type: ignore[arg-type]
                response_format=_SQL_RESPONSE_SCHEMA,  # type: ignore[arg-type]
                **self._completion_kwargs(0),
            )
            data = json.loads(completion.choices[0].message.content or "{}")
        except Exception:  # noqa: BLE001 - si falla la corrección, devolvemos vacío
            return ""

        if not data.get("can_answer"):
            return ""
        return str(data.get("sql") or "").strip()

    def _summarize(self, question: str, rows: list[dict[str, Any]]) -> str:
        assert self._client is not None
        # Limitar el payload enviado al modelo para no inflar tokens.
        sample = rows[:50]
        data_blob = json.dumps(sample, ensure_ascii=False, default=str)
        user_content = (
            f"Pregunta del usuario: {question}\n\n"
            f"Resultados de la consulta (JSON, hasta 50 filas):\n{data_blob}\n\n"
            f"Total de filas devueltas: {len(rows)}.\n"
            "Redacta la respuesta para el usuario."
        )
        completion = self._client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            **self._completion_kwargs(0.2),
        )
        return (completion.choices[0].message.content or "").strip() or "No obtuve resultados para esa consulta."

    def _allowed_columns(self) -> dict[str, set[str]]:
        """Devuelve {tabla: {columnas}} reales, cacheado por proceso.

        Si la introspección falla, devuelve {} y la validación de columnas se omite.
        """
        global _COLUMN_CACHE
        if _COLUMN_CACHE is not None:
            return _COLUMN_CACHE

        result: dict[str, set[str]] = {}
        try:
            conn = pymysql.connect(
                host=self._settings.mysql_host,
                port=self._settings.mysql_port,
                user=self._settings.chat_mysql_user,
                password=self._settings.chat_mysql_password,
                database=self._settings.mysql_database,
                cursorclass=DictCursor,
                autocommit=True,
                read_timeout=10,
            )
            try:
                tables = sorted(ALLOWED_TABLES)
                placeholders = ", ".join(["%s"] * len(tables))
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT TABLE_NAME AS t, COLUMN_NAME AS c "
                        "FROM INFORMATION_SCHEMA.COLUMNS "
                        f"WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})",
                        [self._settings.mysql_database, *tables],
                    )
                    for row in cursor.fetchall():
                        table = str(row["t"]).lower()
                        column = str(row["c"]).lower()
                        result.setdefault(table, set()).add(column)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 - sin metadata, no bloqueamos consultas
            result = {}

        _COLUMN_CACHE = result
        return result

    def _run_readonly(self, sql: str) -> list[dict[str, Any]]:
        conn = pymysql.connect(
            host=self._settings.mysql_host,
            port=self._settings.mysql_port,
            user=self._settings.chat_mysql_user,
            password=self._settings.chat_mysql_password,
            database=self._settings.mysql_database,
            cursorclass=DictCursor,
            autocommit=True,
            read_timeout=max(5, int(self._settings.chat_query_timeout_ms / 1000) + 2),
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET SESSION max_execution_time = %s", (int(self._settings.chat_query_timeout_ms),))
                # Transacción READ ONLY: el servidor rechaza cualquier escritura,
                # incluso si el usuario MySQL tuviera permisos de modificación.
                cursor.execute("START TRANSACTION READ ONLY")
                try:
                    cursor.execute(sql)
                    rows = list(cursor.fetchall())
                finally:
                    cursor.execute("ROLLBACK")
                return rows
        finally:
            conn.close()


__all__ = ["ChatService", "SCHEMA_CONTEXT"]
