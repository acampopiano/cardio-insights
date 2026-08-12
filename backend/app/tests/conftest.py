"""Fixtures compartidos para la suite de tests."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.dependencies import get_repository
from app.core.token_store import blocklist
from app.main import app


@pytest.fixture(autouse=True)
def _isolate_settings_and_blocklist() -> Generator[None, None, None]:
    """Aísla settings (lru_cache) y limpia la blocklist entre tests."""
    previous_env = dict(os.environ)
    # Backend mock por defecto en unit/API tests (rápido, sin MySQL).
    os.environ.setdefault("REPOSITORY_BACKEND", "mock")
    get_settings.cache_clear()
    get_repository.cache_clear()
    blocklist._tokens.clear()  # noqa: SLF001 - reset intencional en tests
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous_env)
        get_settings.cache_clear()
        get_repository.cache_clear()
        blocklist._tokens.clear()  # noqa: SLF001


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dcaraballo", "password": "Demo1234!"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def get_token(
    client: TestClient,
    username: str = "dcaraballo",
    password: str = "Demo1234!",
) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
