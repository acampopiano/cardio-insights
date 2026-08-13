import json
import os
from pathlib import Path
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def _get_token(username: str = "dcaraballo", password: str = "Demo1234!") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _set_auto_kpi_mode(mode: str) -> None:
    os.environ["NATURAL_QUERY_AUTO_KPI_MODE"] = mode
    get_settings.cache_clear()


def _set_auto_kpi_approver_roles(roles_csv: str) -> None:
    os.environ["NATURAL_QUERY_AUTO_KPI_APPROVER_ROLES"] = roles_csv
    get_settings.cache_clear()


def _reset_auto_kpi_mode() -> None:
    os.environ.pop("NATURAL_QUERY_AUTO_KPI_MODE", None)
    os.environ.pop("NATURAL_QUERY_AUTO_KPI_APPROVER_ROLES", None)
    get_settings.cache_clear()


def _set_gateway_enabled(enabled: bool) -> None:
    os.environ["LLM_GATEWAY_ENABLED"] = "true" if enabled else "false"
    get_settings.cache_clear()


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_and_me() -> None:
    token = _get_token()

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "dcaraballo"


def test_dashboard_summary_requires_auth() -> None:
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401


def test_kpi_query() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/kpis/query",
        json={
            "kpi_keys": ["mortality_30d", "surgery_volume", "ptca_share_pct"],
            "filters": [{"key": "period", "values": ["last_90_days"]}],
            "granularity": "month",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["series"]) == 3


def test_analytics_query_requires_auth() -> None:
    response = client.post(
        "/api/v1/analytics/query",
        json={"widget_type": "table", "limit": 5},
    )
    assert response.status_code == 401


def test_analytics_query_ranking() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/analytics/query",
        json={
            "widget_type": "ranking",
            "metric_key": "surgery_volume",
            "granularity": "month",
            "limit": 3,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["widget_type"] == "ranking"
    assert len(data["rows"]) <= 3


def test_analytics_query_cube() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/analytics/query",
        json={
            "widget_type": "cube",
            "metric_key": "surgery_volume",
            "granularity": "month",
            "row_dimension": "period",
            "column_dimension": "quarter",
            "aggregation": "sum",
            "limit": 20,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["widget_type"] == "cube"
    assert "rows" in data
    assert "meta" in data


def test_analytics_query_cube_avg_wait_days() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/analytics/query",
        json={
            "widget_type": "cube",
            "metric_key": "avg_wait_days",
            "granularity": "month",
            "row_dimension": "period",
            "column_dimension": "quarter",
            "aggregation": "avg",
            "limit": 20,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["widget_type"] == "cube"
    assert data["meta"]["metric_key"] == "avg_wait_days"


def test_kpi_designer_create_one_click() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/kpi-designer/create",
        json={
            "kpi_name": "KPI prueba one click",
            "description": "KPI de prueba para flujo generar-validar-registrar",
            "granularity": "month",
            "sql_query": (
                "SELECT {period_expr} AS period, COUNT(*) AS value "
                "FROM flow_coordina f "
                "WHERE f.Realizado = 255 {date_clause} "
                "GROUP BY {period_expr} ORDER BY period"
            ),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["generated_kpi_key"] == "kpi_prueba_one_click"


def test_natural_query_trend() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "Como viene la espera promedio en 2026?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "trend"
    assert data["endpoint_used"] == "/api/v1/kpis/query"
    assert "result" in data


def test_natural_query_total_surgeries_specific_year_is_year_granularity() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "Mostrame el total de cirugias en 2025"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "trend"
    assert data["endpoint_used"] == "/api/v1/kpis/query"
    assert data["payload"]["granularity"] == "year"
    assert "total anual" in data["explanation"].lower()


def test_natural_query_surgical_activity_maps_to_surgery_volume() -> None:
    previous_gateway = os.environ.get("LLM_GATEWAY_ENABLED")
    previous_memory = os.environ.get("NATURAL_QUERY_ONLINE_MEMORY_ENABLED")
    os.environ["LLM_GATEWAY_ENABLED"] = "false"
    os.environ["NATURAL_QUERY_ONLINE_MEMORY_ENABLED"] = "false"
    get_settings.cache_clear()
    token = _get_token()
    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como estuvo la actividad quirurgica a lo largo de 2025?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["intent"] == "trend"
        assert data["metric"] == "surgery_volume"
        assert data["payload"]["kpi_keys"] == ["surgery_volume"]
        assert data["payload"]["filters"] == [
            {"key": "date_from", "values": ["2025-01-01"]},
            {"key": "date_to", "values": ["2025-12-31"]},
        ]
    finally:
        if previous_gateway is None:
            os.environ.pop("LLM_GATEWAY_ENABLED", None)
        else:
            os.environ["LLM_GATEWAY_ENABLED"] = previous_gateway
        if previous_memory is None:
            os.environ.pop("NATURAL_QUERY_ONLINE_MEMORY_ENABLED", None)
        else:
            os.environ["NATURAL_QUERY_ONLINE_MEMORY_ENABLED"] = previous_memory
        get_settings.cache_clear()


def test_natural_query_ranking() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "Top centros que mas envian pacientes este ano"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "ranking"
    assert data["endpoint_used"] == "/api/v1/analytics/query"
    assert "result" in data


def test_natural_query_worst_month_wait_delays_is_ranking() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "En que mes estuvimos peor con las demoras?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "ranking"
    assert data["endpoint_used"] == "/api/v1/analytics/query"
    assert data["payload"]["metric_key"] == "avg_wait_days"
    current_year = datetime.now(UTC).year
    assert data["payload"]["filters"] == [
        {"key": "date_from", "values": [f"{current_year}-01-01"]},
        {"key": "date_to", "values": [f"{current_year}-12-31"]},
    ]


def test_natural_query_worst_month_wait_delays_last_year() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "El ano pasado, que mes estuvimos peor con las demoras?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "ranking"
    assert data["endpoint_used"] == "/api/v1/analytics/query"
    assert data["payload"]["metric_key"] == "avg_wait_days"
    current_year = datetime.now(UTC).year
    previous_year = current_year - 1
    assert data["payload"]["filters"] == [
        {"key": "date_from", "values": [f"{previous_year}-01-01"]},
        {"key": "date_to", "values": [f"{previous_year}-12-31"]},
    ]


def test_natural_query_peak_surgery_day_in_january_last_year() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "En que dia del mes de enero del ano pasado, tuvimos el pico de cirugias?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "ranking"
    assert data["endpoint_used"] == "/api/v1/analytics/query"
    assert data["payload"]["metric_key"] == "surgery_volume"
    assert data["payload"]["granularity"] == "day"
    assert data["payload"]["limit"] == 1
    previous_year = datetime.now(UTC).year - 1
    assert data["payload"]["filters"] == [
        {"key": "date_from", "values": [f"{previous_year}-01-01"]},
        {"key": "date_to", "values": [f"{previous_year}-01-31"]},
    ]


def test_natural_query_peak_surgery_day_in_march_2024() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "En que dia del mes de marzo del ano 2024, tuvimos el pico de cirugias?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "ranking"
    assert data["endpoint_used"] == "/api/v1/analytics/query"
    assert data["payload"]["metric_key"] == "surgery_volume"
    assert data["payload"]["granularity"] == "day"
    assert data["payload"]["limit"] == 1
    assert data["payload"]["filters"] == [
        {"key": "date_from", "values": ["2024-03-01"]},
        {"key": "date_to", "values": ["2024-03-31"]},
    ]


def test_natural_query_peak_deaths_day_in_2025() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "En que dia del ano 2025, murieron mas personas?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "ranking"
    assert data["endpoint_used"] == "/api/v1/analytics/query"
    assert data["payload"]["metric_key"] == "mortality_egreso_count"
    assert data["payload"]["granularity"] == "day"
    assert data["payload"]["limit"] == 5
    assert data["payload"]["filters"] == [
        {"key": "date_from", "values": ["2025-01-01"]},
        {"key": "date_to", "values": ["2025-12-31"]},
    ]


def test_natural_query_ranking_between_two_months_in_year() -> None:
    _set_gateway_enabled(False)
    token = _get_token()
    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Como se comporto la demora quirurgica entre marzo y agosto de 2025, y en que mes pego el salto mas fuerte?"
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["payload"]["filters"] == [
            {"key": "date_from", "values": ["2025-03-01"]},
            {"key": "date_to", "values": ["2025-08-31"]},
        ]
    finally:
        os.environ.pop("LLM_GATEWAY_ENABLED", None)
        get_settings.cache_clear()


def test_natural_query_trend_ptca_percentage_maps_share_metric() -> None:
    token = _get_token()
    response = client.post(
        "/api/v1/natural-query/run",
        json={"question": "Que porcentaje de los procedimientos corresponden a PTCA para el ano 2025?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["intent"] == "trend"
    assert data["endpoint_used"] == "/api/v1/kpis/query"
    assert data["payload"]["kpi_keys"] == ["ptca_share_pct"]
    assert "ptca_share_pct" in data["explanation"]


def test_natural_query_auto_creates_kpi_for_total_volume() -> None:
    _set_auto_kpi_mode("auto_create")
    token = _get_token()
    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene el volumen total de actividad en 2025?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["intent"] == "trend"
        assert data["endpoint_used"] == "/api/v1/kpis/query"
        assert data["auto_kpi"]["created"] is True
        assert data["auto_kpi"]["mode"] == "auto_create"
        assert data["payload"]["kpi_keys"] == ["volumen_mensual_total"]
        assert data["result"]["series"]
    finally:
        _reset_auto_kpi_mode()


def test_natural_query_auto_creates_medical_wait_peak_kpi() -> None:
    _set_auto_kpi_mode("auto_create")
    token = _get_token()
    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera maxima mensual de pacientes en 2025?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["intent"] == "trend"
        assert data["auto_kpi"]["created"] is True
        assert data["auto_kpi"]["generated_kpi_key"] == "espera_maxima_en_dias"
        assert data["payload"]["kpi_keys"] == ["espera_maxima_en_dias"]
        assert data["result"]["series"]
    finally:
        _reset_auto_kpi_mode()


def test_natural_query_suggest_only_does_not_create_kpi() -> None:
    _set_auto_kpi_mode("suggest_only")
    token = _get_token()
    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene el volumen total de actividad en 2025?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_kpi"]["created"] is False
        assert data["auto_kpi"]["mode"] == "suggest_only"
        assert data["auto_kpi"]["status"] == "suggested"
        assert data["payload"]["kpi_keys"] == ["__unmapped_metric__"]
    finally:
        _reset_auto_kpi_mode()


def test_natural_query_human_approve_requires_opt_in() -> None:
    _set_auto_kpi_mode("human_approve")
    _set_auto_kpi_approver_roles("admin,direccion")
    clinico_token = _get_token("dcaraballo", "Demo1234!")
    try:
        without_approval = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene el volumen total de actividad en 2025?"},
            headers={"Authorization": f"Bearer {clinico_token}"},
        )
        assert without_approval.status_code == 200
        data_no = without_approval.json()
        assert data_no["auto_kpi"]["created"] is False
        assert data_no["auto_kpi"]["status"] == "pending_approval"

        clinico_with_approval = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Como viene el volumen total de actividad en 2025?",
                "approve_auto_kpi": True,
            },
            headers={"Authorization": f"Bearer {clinico_token}"},
        )
        assert clinico_with_approval.status_code == 200
        data_clinico = clinico_with_approval.json()
        assert data_clinico["auto_kpi"]["created"] is False
        assert data_clinico["auto_kpi"]["status"] == "not_authorized"

        _set_auto_kpi_approver_roles("clinico")
        approved_with_role = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Como viene el volumen total de actividad en 2025?",
                "approve_auto_kpi": True,
            },
            headers={"Authorization": f"Bearer {clinico_token}"},
        )
        assert approved_with_role.status_code == 200
        data_yes = approved_with_role.json()
        assert data_yes["auto_kpi"]["created"] is True
        assert data_yes["auto_kpi"]["mode"] == "human_approve"
        assert data_yes["payload"]["kpi_keys"] == ["volumen_mensual_total"]
    finally:
        _reset_auto_kpi_mode()


def test_natural_query_meta_deterioro_infiere_metrica_proxy() -> None:
    os.environ["LLM_GATEWAY_ENABLED"] = "false"
    get_settings.cache_clear()
    token = _get_token()
    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Si miramos los ultimos 180 dias, cual KPI muestra el deterioro mas marcado y desde cuando empezo la tendencia?"
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert data["metric"] == "avg_wait_days"
        assert data["payload"]["kpi_keys"] == ["avg_wait_days"]
        assert data["payload"]["filters"]
    finally:
        os.environ.pop("LLM_GATEWAY_ENABLED", None)
        get_settings.cache_clear()


def test_natural_query_mvp_dataset() -> None:
    token = _get_token()
    dataset_path = Path(__file__).resolve().parents[2] / "docs" / "natural-query-examples-mvp.json"
    samples = json.loads(dataset_path.read_text(encoding="utf-8"))

    assert isinstance(samples, list)
    assert len(samples) > 0

    mismatches: list[str] = []
    total_cases = len(samples)
    passed_cases = 0

    for sample in samples:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": sample["question"]},
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code != 200:
            mismatches.append(f"id={sample.get('id')} status={response.status_code}")
            continue

        data = response.json()
        sample_ok = True
        if data.get("intent") != sample.get("intent"):
            sample_ok = False
            mismatches.append(
                f"id={sample.get('id')} intent esperado={sample.get('intent')} obtenido={data.get('intent')}"
            )
        if data.get("endpoint_used") != sample.get("endpoint"):
            sample_ok = False
            mismatches.append(
                f"id={sample.get('id')} endpoint esperado={sample.get('endpoint')} obtenido={data.get('endpoint_used')}"
            )
        if sample_ok:
            passed_cases += 1

    precision = round((passed_cases / total_cases) * 100.0, 2)
    summary = (
        f"[NL-MVP] total={total_cases} aciertos={passed_cases} "
        f"fallos={total_cases - passed_cases} precision_pct={precision}"
    )
    print(summary)

    assert not mismatches, summary + "\n" + "\n".join(mismatches)
