from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.token_store import blocklist

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    """Error HTTP 401 estandarizado para fallos de autenticacion/autorizacion."""

    def __init__(self, detail: str = "Invalid credentials") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una clave en texto plano contra un hash almacenado."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Genera hash bcrypt de una password para almacenamiento seguro."""
    return pwd_context.hash(password)


def create_access_token(subject: str, role: str, permissions: list[str]) -> str:
    """Crea un JWT firmado con identidad, rol, permisos y tiempos de validez."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decodifica y valida firma/expiracion del JWT, devolviendo sus claims."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthError(detail="Invalid or expired token") from exc


def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Extrae el bearer token del header Authorization de la request actual."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthError(detail="Missing bearer token")
    return credentials.credentials


def get_current_claims(token: str = Depends(get_current_token)) -> dict[str, Any]:
    """Retorna claims del token actual y bloquea tokens revocados por jti."""
    payload = decode_token(token)
    jti = payload.get("jti")
    if not jti or blocklist.contains(jti):
        raise AuthError(detail="Token revoked")
    return payload
