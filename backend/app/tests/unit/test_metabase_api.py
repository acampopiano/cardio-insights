"""Contratos del endpoint de embed Metabase."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.tests.conftest import get_token


def test_metabase_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/metabase/embed-token").status_code == 401


def test_metabase_503_without_secret(client: TestClient) -> None:
    os.environ["METABASE_SECRET_KEY"] = "change-me"
    get_settings.cache_clear()
    token = get_token(client)
    response = client.get(
        "/api/v1/metabase/embed-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


def test_metabase_embed_token_ok(client: TestClient) -> None:
    os.environ["METABASE_SECRET_KEY"] = "test-secret-key"
    os.environ["METABASE_SITE_URL"] = "http://metabase.local"
    os.environ["METABASE_DEFAULT_DASHBOARD_ID"] = "7"
    get_settings.cache_clear()
    token = get_token(client)
    response = client.get(
        "/api/v1/metabase/embed-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dashboard_id"] == 7
    assert data["iframe_url"].startswith("http://metabase.local/embed/dashboard/")
    assert "bordered=false" in data["iframe_url"]


def test_metabase_embed_token_custom_dashboard(client: TestClient) -> None:
    os.environ["METABASE_SECRET_KEY"] = "test-secret-key"
    os.environ["METABASE_SITE_URL"] = "http://metabase.local"
    get_settings.cache_clear()
    token = get_token(client)
    response = client.get(
        "/api/v1/metabase/embed-token?dashboard_id=42",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["dashboard_id"] == 42
