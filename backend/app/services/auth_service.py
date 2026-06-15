import hashlib
from typing import Any

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, verify_password
from app.core.token_store import blocklist
from app.repositories.interfaces import AuthRepository


class AuthService:
    def __init__(self, auth_repository: AuthRepository) -> None:
        self.auth_repository = auth_repository

    @staticmethod
    def _password_valid(user: dict[str, Any], password: str) -> bool:
        plain_password = user.get("password_plain")
        if plain_password:
            return str(plain_password) == password

        md5_password = user.get("password_md5")
        if md5_password:
            return hashlib.md5(password.encode("utf-8")).hexdigest().lower() == str(md5_password).lower()

        hashed_password = user.get("hashed_password")
        if hashed_password:
            return verify_password(password, hashed_password)

        return False

    def login(self, username: str, password: str) -> dict[str, Any]:
        user = self.auth_repository.get_user_by_username(username)
        if user is None or not self._password_valid(user, password):
            raise ValueError("Usuario o contraseña incorrectos")

        access_token = create_access_token(
            subject=user["username"],
            role=user["role"],
            permissions=user["permissions"],
        )

        settings = get_settings()
        public_user = {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "permissions": user["permissions"],
        }
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": public_user,
        }

    def logout(self, token: str) -> dict[str, Any]:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            blocklist.add(jti)
        return {"success": True, "message": "Sesión cerrada"}

    def me(self, username: str) -> dict[str, Any]:
        user = self.auth_repository.get_user_by_username(username)
        if user is None:
            raise ValueError("Usuario no encontrado")
        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "permissions": user["permissions"],
        }
