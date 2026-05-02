from pydantic import BaseModel, ConfigDict, Field


class KpiDesignRequest(BaseModel):
    kpi_name: str = Field(min_length=3, examples=["Participacion PTCA"])
    description: str = Field(min_length=5, examples=["Porcentaje de PTCA sobre el total de actividad."])
    granularity: str = Field(default="month", examples=["day", "week", "month"])
    sql_query: str = Field(
        min_length=20,
        description="SQL asociado al KPI. Debe devolver aliases period y value.",
        examples=[
            "SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,\n"
            "       ROUND(100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0), 2) AS value\n"
            "FROM flow_coordina f\n"
            "LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod\n"
            "LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod\n"
            "WHERE f.FechaRealizado > '1900-01-01'\n"
            "GROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')\n"
            "ORDER BY period"
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kpi_name": "Participacion PTCA",
                "description": "Porcentaje de PTCA sobre el total de actividad.",
                "granularity": "month",
                "sql_query": "SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,\n       ROUND(100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0), 2) AS value\nFROM flow_coordina f\nLEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod\nLEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod\nWHERE f.FechaRealizado > '1900-01-01'\nGROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')\nORDER BY period",
            }
        }
    )


class KpiDesignResponse(BaseModel):
    generated_kpi_key: str
    catalog_snippet: str
    query_snippet: str
    query_payload_example: dict[str, object]
    registration_payload: dict[str, str]
    notes: list[str]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "generated_kpi_key": "participacion_ptca",
                "catalog_snippet": "{\n    \"key\": \"participacion_ptca\",\n    \"label\": \"Participacion PTCA\",\n    \"unit\": \"valor\",\n    \"description\": \"Porcentaje de PTCA sobre el total de actividad.\",\n},",
                "query_snippet": "elif normalized_key == \"participacion_ptca\":\n    query = \"\"\"...\"\"\"",
                "query_payload_example": {
                    "kpi_keys": ["participacion_ptca"],
                    "granularity": "month",
                    "filters": [
                        {"key": "date_from", "values": ["2025-01-01"]},
                        {"key": "date_to", "values": ["2026-12-31"]}
                    ]
                },
                "registration_payload": {
                    "key": "participacion_ptca",
                    "label": "Participacion PTCA",
                    "description": "Porcentaje de PTCA sobre el total de actividad.",
                    "sql_query_template": "SELECT ... AS period, ... AS value ...",
                    "default_granularity": "month"
                },
                "notes": [
                    "catalog_snippet y query_snippet son para pegar en codigo Python, no para enviar a /kpis/query.",
                    "Usa query_payload_example para probar el KPI en /api/v1/kpis/query.",
                    "La key tecnica se genera automaticamente desde el nombre.",
                ],
            }
        }
    )


class KpiRegisterRequest(BaseModel):
    key: str = Field(min_length=3, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=3)
    description: str = Field(min_length=5)
    sql_query_template: str = Field(min_length=20)
    default_granularity: str = Field(default="month", examples=["day", "week", "month"])
