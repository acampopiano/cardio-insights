"""Tests unitarios de AuthService (login/logout/me) sin HTTP."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, get_password_hash
from app.core.token_store import blocklist
from app.services.auth_service import AuthService


class _FakeAuthRepo:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self._users = {u["username"]: u for u in users}

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        return self._users.get(username)


def _svc(*users: dict[str, Any]) -> AuthService:
    return AuthService(_FakeAuthRepo(list(users)))


def test_login_with_hashed_password() -> None:
    svc = _svc(
        {
            "id": 1,
            "username": "clinician",
            "full_name": "Dr. Test",
            "role": "clinician",
            "permissions": ["dashboard:read"],
            "hashed_password": get_password_hash("Demo1234!"),
        }
    )
    result = svc.login("clinician", "Demo1234!")
    assert result["token_type"] == "bearer"
    assert result["user"]["username"] == "clinician"
    assert "password" not in result["user"]
    assert "hashed_password" not in result["user"]
    payload = decode_token(result["access_token"])
    assert payload["sub"] == "clinician"


def test_login_with_plain_password() -> None:
    svc = _svc(
        {
            "id": 2,
            "username": "legacy",
            "full_name": "Legacy",
            "role": "clinician",
            "permissions": [],
            "password_plain": "PlainPass1",
        }
    )
    result = svc.login("legacy", "PlainPass1")
    assert result["user"]["username"] == "legacy"


def test_login_with_md5_password() -> None:
    password = "Md5Pass1"
    md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
    svc = _svc(
        {
            "id": 3,
            "username": "md5user",
            "full_name": "MD5",
            "role": "clinician",
            "permissions": [],
            "password_md5": md5,
        }
    )
    result = svc.login("md5user", password)
    assert result["user"]["username"] == "md5user"


def test_login_rejects_bad_password() -> None:
    svc = _svc(
        {
            "id": 1,
            "username": "clinician",
            "full_name": "Dr. Test",
            "role": "clinician",
            "permissions": [],
            "hashed_password": get_password_hash("Demo1234!"),
        }
    )
    with pytest.raises(ValueError, match="incorrectos"):
        svc.login("clinician", "wrong")


def test_login_rejects_unknown_user() -> None:
    svc = _svc()
    with pytest.raises(ValueError, match="incorrectos"):
        svc.login("nobody", "x")


def test_login_rejects_user_without_password_fields() -> None:
    svc = _svc(
        {
            "id": 9,
            "username": "broken",
            "full_name": "Broken",
            "role": "clinician",
            "permissions": [],
        }
    )
    with pytest.raises(ValueError, match="incorrectos"):
        svc.login("broken", "anything")


def test_logout_blocklists_jti() -> None:
    svc = _svc()
    token = create_access_token("clinician", "clinician", [])
    jti = decode_token(token)["jti"]
    result = svc.logout(token)
    assert result["success"] is True
    assert blocklist.contains(jti) is True


def test_logout_without_jti_still_succeeds() -> None:
    svc = _svc()
    settings = get_settings()
    token = jwt.encode(
        {"sub": "clinician", "role": "clinician", "permissions": [], "exp": 9999999999},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    result = svc.logout(token)
    assert result["success"] is True


def test_me_returns_public_user() -> None:
    svc = _svc(
        {
            "id": 1,
            "username": "clinician",
            "full_name": "Dr. Test",
            "role": "clinician",
            "permissions": ["kpis:query"],
            "hashed_password": get_password_hash("x"),
        }
    )
    me = svc.me("clinician")
    assert me == {
        "id": 1,
        "username": "clinician",
        "full_name": "Dr. Test",
        "role": "clinician",
        "permissions": ["kpis:query"],
    }


def test_me_unknown_user() -> None:
    svc = _svc()
    with pytest.raises(ValueError, match="no encontrado"):
        svc.me("ghost")
