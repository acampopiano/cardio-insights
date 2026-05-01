import hashlib
from typing import Any

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, verify_password
from app.core.token_store import blocklist
from app.repositories.interfaces import AuthRepository


class AuthService:
    """Orquesta autenticacion, emision de token y consulta de perfil del usuario."""

    def __init__(self, auth_repository: AuthRepository) -> None:
        """Inyecta repositorio de autenticacion para desacoplar acceso a datos."""
        self.auth_repository = auth_repository

    @staticmethod
    def _password_valid(user: dict[str, Any], password: str) -> bool:
        """Valida password contra formatos heredados: plano, md5 o hash bcrypt."""
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
        """Autentica usuario y devuelve token JWT con datos publicos de sesion."""
        user = self.auth_repository.get_user_by_username(username)
        if user is None or not self._password_valid(user, password):
            raise ValueError("Invalid username or password")

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
        """Revoca token actual agregando su jti a la blocklist en memoria."""
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            blocklist.add(jti)
        return {"success": True, "message": "Session closed"}

    def me(self, username: str) -> dict[str, Any]:
        """Obtiene el perfil publico del usuario autenticado por su username."""
        user = self.auth_repository.get_user_by_username(username)
        if user is None:
            raise ValueError("User not found")
        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "permissions": user["permissions"],
        }
