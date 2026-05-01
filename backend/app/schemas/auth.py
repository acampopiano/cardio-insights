from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    """Representa datos publicos del usuario que pueden exponerse al cliente."""

    id: int
    username: str
    full_name: str
    role: str
    permissions: list[str]


class LoginRequest(BaseModel):
    """Payload de entrada para autenticacion por usuario y password."""

    username: str = Field(min_length=1, examples=["clinician"])
    password: str = Field(min_length=1, examples=["Demo1234!"])


class LoginResponse(BaseModel):
    """Respuesta de login con token bearer y perfil de usuario."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class LogoutResponse(BaseModel):
    """Resultado de cierre de sesion."""

    success: bool
    message: str


class MeResponse(BaseModel):
    """Respuesta del endpoint que retorna usuario autenticado actual."""

    user: UserPublic
