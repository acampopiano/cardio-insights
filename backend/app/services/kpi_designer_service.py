import re
import unicodedata

from app.schemas.kpi_designer import KpiDesignRequest, KpiDesignResponse


class KpiDesignerService:
    """Genera snippets minimos para incorporar un KPI con un formulario simple."""

    _ALLOWED_TABLES = {
        "flow_coordina",
        "dat_cirugia",
        "call_ptcamaster",
        "flow_procedimientocardiologia",
        "stk_cartera",
        "pvd_master",
        "pvd_masterqq",
        "pac_ficha",
        "salud_coordina",
        "salud_paciente",
    }

    _BLOCKED_SQL_TOKENS = {
        "alter",
        "create",
        "delete",
        "drop",
        "grant",
        "insert",
        "load_file",
        "outfile",
        "replace",
        "revoke",
        "truncate",
        "update",
    }

    @staticmethod
    def _to_kpi_key(name: str) -> str:
        ascii_name = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")
        return normalized or "kpi_nuevo"

    @staticmethod
    def _sanitize_sql(sql_query: str) -> str:
        sql = sql_query.strip()
        lowered = sql.lower()

        if not lowered.startswith("select"):
            raise ValueError("El SQL debe ser un SELECT.")
        if ";" in sql:
            raise ValueError("El SQL debe contener una sola sentencia, sin punto y coma.")
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise ValueError("El SQL no debe incluir comentarios.")
        if re.search(r"\b(" + "|".join(KpiDesignerService._BLOCKED_SQL_TOKENS) + r")\b", lowered):
            raise ValueError("El SQL contiene una operacion no permitida para KPIs.")
        if not re.search(r"\bas\s+period\b", lowered) or not re.search(r"\bas\s+value\b", lowered):
            raise ValueError("El SQL debe devolver columnas alias 'period' y 'value'")
        if "{period_expr}" not in sql or "{date_clause}" not in sql:
            raise ValueError("El SQL debe usar los placeholders {period_expr} y {date_clause}.")

        table_refs = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered)
        unknown_tables = sorted({table for table in table_refs if table not in KpiDesignerService._ALLOWED_TABLES})
        if unknown_tables:
            raise ValueError(f"El SQL referencia tablas no permitidas: {', '.join(unknown_tables)}")

        return sql

    def generate(self, payload: KpiDesignRequest) -> KpiDesignResponse:
        if payload.granularity not in {"day", "week", "month", "year"}:
            raise ValueError("La granularidad debe ser day, week, month o year")

        key = self._to_kpi_key(payload.kpi_name)
        label = payload.kpi_name.strip()
        description = payload.description.strip()
        sql = self._sanitize_sql(payload.sql_query)

        catalog_snippet = (
            "{\n"
            f"    \"key\": \"{key}\",\n"
            f"    \"label\": \"{label}\",\n"
            "    \"unit\": \"valor\",\n"
            f"    \"description\": \"{description}\",\n"
            "},"
        )

        query_snippet = (
            f"elif normalized_key == \"{key}\":\n"
            "    query = \"\"\"\n"
            f"        {sql}\n"
            "    \"\"\""
        )

        query_payload_example = {
            "kpi_keys": [key],
            "granularity": payload.granularity,
            "filters": [
                {"key": "date_from", "values": ["2025-01-01"]},
                {"key": "date_to", "values": ["2026-12-31"]},
            ],
        }

        registration_payload = {
            "key": key,
            "label": label,
            "description": description,
            "sql_query_template": sql,
            "default_granularity": payload.granularity,
        }

        notes = [
            "1) catalog_snippet y query_snippet son codigo para pegar en el backend.",
            "2) No enviar esos snippets a /api/v1/kpis/query.",
            "3) Para probar el KPI por API, usa query_payload_example como body.",
            f"4) Granularidad sugerida para este KPI: {payload.granularity}.",
        ]

        return KpiDesignResponse(
            generated_kpi_key=key,
            catalog_snippet=catalog_snippet,
            query_snippet=query_snippet,
            query_payload_example=query_payload_example,
            registration_payload=registration_payload,
            notes=notes,
        )
