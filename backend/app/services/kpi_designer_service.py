import re
import unicodedata

from app.schemas.kpi_designer import KpiDesignRequest, KpiDesignResponse


class KpiDesignerService:
    """Genera snippets minimos para incorporar un KPI con un formulario simple."""

    @staticmethod
    def _to_kpi_key(name: str) -> str:
        ascii_name = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")
        return normalized or "kpi_nuevo"

    @staticmethod
    def _sanitize_sql(sql_query: str) -> str:
        sql = sql_query.strip()
        if " period" not in sql.lower() or " value" not in sql.lower():
            raise ValueError("El SQL debe devolver columnas alias 'period' y 'value'")
        return sql

    def generate(self, payload: KpiDesignRequest) -> KpiDesignResponse:
        if payload.granularity not in {"day", "week", "month"}:
            raise ValueError("La granularidad debe ser day, week o month")

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
