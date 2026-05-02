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
