"""Contratos HTTP de auth (401/logout/me)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import get_settings
from app.core.token_store import blocklist
from app.tests.conftest import get_token


def test_login_ok(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dcaraballo", "password": "Demo1234!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["username"] == "dcaraballo"


def test_login_bad_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dcaraballo", "password": "wrong"},
    )
    assert response.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_valid_token(client: TestClient) -> None:
    token = get_token(client)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "dcaraballo"


def test_me_rejects_garbage_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_logout_invalidates_session(client: TestClient) -> None:
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert logout.json()["success"] is True

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 401


def test_logout_requires_token(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout").status_code == 401


def test_me_rejects_token_without_subject(client: TestClient) -> None:
    settings = get_settings()
    token = jwt.encode(
        {"role": "clinician", "permissions": [], "jti": "no-sub", "exp": 9999999999},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_me_returns_404_when_user_missing(client: TestClient, monkeypatch) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "ghost-user",
            "role": "clinician",
            "permissions": [],
            "jti": "ghost-jti",
            "exp": 9999999999,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    # Asegurar que el jti no esté bloqueado.
    assert not blocklist.contains("ghost-jti")

    from app.services import auth_service as auth_service_module

    original_me = auth_service_module.AuthService.me

    def _missing(self, username: str):
        if username == "ghost-user":
            raise ValueError("Usuario no encontrado")
        return original_me(self, username)

    monkeypatch.setattr(auth_service_module.AuthService, "me", _missing)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
