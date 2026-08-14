"""Ramas de detección de métricas/fechas del servicio local NL2KPI."""

from __future__ import annotations

from app.services.natural_query_service import NaturalQueryService


def test_metric_detection_variants() -> None:
    svc = NaturalQueryService
    assert svc._match_metric_key("tasa de reingreso a 30 dias") == "readmission_30d"
    assert svc._match_metric_key("reintervenciones del mes") == "reintervenciones_mensual"
    assert svc._match_metric_key("espera maxima mensual") is None
    assert svc._match_metric_key("demora quirurgica") == "avg_wait_days"
    assert svc._match_metric_key("cuantos murieron") == "mortality_egreso_count"
    assert svc._match_metric_key("mortalidad al egreso") == "mortality_egreso_pct"
    assert svc._match_metric_key("participacion de ptca") == "ptca_share_pct"
    assert svc._match_metric_key("volumen de ptca") == "ptca_volume"
    assert svc._match_metric_key("actos de hemodinamia") == "hemodinamia_volumen_mensual"
    assert svc._match_metric_key("top centros que envian") == "top_centro_por_periodo"
    assert svc._match_metric_key("centros derivadores") == "centros_que_envian_pacientes"
    assert svc._match_metric_key("actividad quirurgica") == "surgery_volume"
    assert svc._match_metric_key("sin metrica conocida") is None
    assert svc._detect_metric_key("sin metrica conocida") == "surgery_volume"
    assert svc._infer_metric_for_meta_question("que kpi muestra el deterioro") == "avg_wait_days"
    assert svc._infer_metric_for_meta_question("hola") is None


def test_granularity_and_date_filters() -> None:
    assumptions: list[str] = []
    assert NaturalQueryService._detect_granularity("reingreso a 30 dias") in {"day", "month", "week", "year"}
    assert NaturalQueryService._detect_granularity("serie semanal") == "week"
    assert NaturalQueryService._detect_granularity("evolucion mensual") == "month"
    assert NaturalQueryService._detect_granularity("total de cirugias en 2024") == "year"

    filters = NaturalQueryService._detect_date_filters("ultimos 90 dias", assumptions)
    assert filters[0]["key"] == "date_from"

    assumptions.clear()
    filters = NaturalQueryService._detect_date_filters(
        "entre marzo y agosto de 2024",
        assumptions,
    )
    assert filters

    assumptions.clear()
    filters = NaturalQueryService._detect_date_filters(
        "entre marzo y agosto del ano pasado",
        assumptions,
    )
    assert filters

    assumptions.clear()
    filters = NaturalQueryService._detect_date_filters("entre marzo y enero", assumptions)
    assert filters  # año actual, meses swapped

    assumptions.clear()
    filters = NaturalQueryService._detect_date_filters("en enero de 2024", assumptions)
    assert filters[0]["values"][0].endswith("-01-01")
