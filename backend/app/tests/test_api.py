from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get_token() -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician", "password": "Demo1234!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


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
    assert me_response.json()["user"]["username"] == "clinician"


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
