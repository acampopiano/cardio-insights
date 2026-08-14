"""Validaciones del diseñador de KPIs."""

from __future__ import annotations

import pytest

from app.schemas.kpi_designer import KpiDesignRequest
from app.services.kpi_designer_service import KpiDesignerService


def _valid_sql() -> str:
    return (
        "SELECT {period_expr} AS period, COUNT(*) AS value "
        "FROM flow_coordina f WHERE f.Realizado = 255 {date_clause} "
        "GROUP BY {period_expr} ORDER BY period"
    )


def test_generate_ok() -> None:
    svc = KpiDesignerService()
    result = svc.generate(
        KpiDesignRequest(
            kpi_name="Volumen Especial",
            description="Descripcion valida del KPI",
            granularity="month",
            sql_query=_valid_sql(),
        )
    )
    assert result.generated_kpi_key == "volumen_especial"
    assert "period" in result.registration_payload["sql_query_template"]


@pytest.mark.parametrize(
    "sql,match",
    [
        ("DELETE FROM flow_coordina", "SELECT"),
        ("SELECT 1 AS period, 1 AS value FROM flow_coordina; DROP TABLE x", "punto y coma"),
        ("SELECT 1 AS period, 1 AS value FROM flow_coordina -- comment", "comentarios"),
        ("SELECT 1 AS period, 1 AS value FROM flow_coordina /* x */", "comentarios"),
        (
            "SELECT 1 AS period, 1 AS value FROM flow_coordina WHERE 1=1 UPDATE x",
            "no permitida",
        ),
        ("SELECT COUNT(*) AS total FROM flow_coordina", "period"),
        (
            "SELECT {period_expr} AS period, 1 AS value FROM flow_coordina",
            "placeholders",
        ),
        (
            "SELECT {period_expr} AS period, 1 AS value FROM use_usuarios f WHERE 1=1 {date_clause}",
            "no permitidas",
        ),
    ],
)
def test_sanitize_rejects(sql: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        KpiDesignerService()._sanitize_sql(sql)


def test_invalid_granularity() -> None:
    with pytest.raises(ValueError, match="granularidad"):
        KpiDesignerService().generate(
            KpiDesignRequest(
                kpi_name="KPI invalido",
                description="Descripcion valida del KPI",
                granularity="hora",
                sql_query=_valid_sql(),
            )
        )


def test_to_kpi_key_fallback() -> None:
    assert KpiDesignerService._to_kpi_key("!!!") == "kpi_nuevo"
