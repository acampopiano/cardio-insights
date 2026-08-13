"""Tests unitarios de JWT, passwords y dependencias de auth."""

from __future__ import annotations

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.config import get_settings
from fastapi import HTTPException

from app.core.security import (
    AuthError,
    create_access_token,
    decode_token,
    get_current_claims,
    get_current_token,
    get_password_hash,
    require_roles,
    verify_password,
)
from app.core.token_store import blocklist


def test_password_hash_roundtrip() -> None:
    hashed = get_password_hash("Demo1234!")
    assert hashed != "Demo1234!"
    assert verify_password("Demo1234!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token() -> None:
    token = create_access_token("clinician", "clinician", ["dashboard:read"])
    payload = decode_token(token)
    assert payload["sub"] == "clinician"
    assert payload["role"] == "clinician"
    assert payload["permissions"] == ["dashboard:read"]
    assert payload["jti"]


def test_decode_token_rejects_tampered() -> None:
    token = create_access_token("clinician", "clinician", [])
    with pytest.raises(AuthError, match="inválido|expirado"):
        decode_token(token + "x")


def test_decode_token_rejects_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    token = create_access_token("clinician", "clinician", [])
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret_key", "otro-secreto-distinto")
    with pytest.raises(AuthError):
        decode_token(token)


def test_decode_token_rejects_expired() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "clinician", "role": "clinician", "permissions": [], "jti": "old", "exp": 1},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthError, match="inválido|expirado"):
        decode_token(token)


def test_get_current_token_requires_bearer() -> None:
    with pytest.raises(AuthError, match="Falta el token"):
        get_current_token(None)

    with pytest.raises(AuthError, match="Falta el token"):
        get_current_token(HTTPAuthorizationCredentials(scheme="Basic", credentials="abc"))


def test_get_current_token_returns_credentials() -> None:
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok-123")
    assert get_current_token(creds) == "tok-123"


def test_get_current_claims_rejects_blocklisted_jti() -> None:
    token = create_access_token("clinician", "clinician", [])
    payload = decode_token(token)
    blocklist.add(payload["jti"])
    with pytest.raises(AuthError, match="Sesión expirada"):
        get_current_claims(token)


def test_get_current_claims_rejects_missing_jti() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "clinician", "role": "clinician", "permissions": [], "exp": 9999999999},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthError, match="Sesión expirada"):
        get_current_claims(token)


def test_get_current_claims_ok() -> None:
    token = create_access_token("clinician", "clinician", ["kpis:query"])
    claims = get_current_claims(token)
    assert claims["sub"] == "clinician"
    assert "kpis:query" in claims["permissions"]


def test_require_roles_allows_and_denies() -> None:
    dependency = require_roles("admin", "clinico")
    assert dependency({"role": "clinico"})["role"] == "clinico"
    assert dependency({"role": "Admin"})["role"] == "Admin"
    with pytest.raises(HTTPException) as exc:
        dependency({"role": "gestion"})
    assert exc.value.status_code == 403
