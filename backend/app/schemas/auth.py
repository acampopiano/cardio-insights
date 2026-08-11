from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    permissions: list[str]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, examples=["dcaraballo"])
    password: str = Field(min_length=1, examples=["Demo1234!"])


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class LogoutResponse(BaseModel):
    success: bool
    message: str


class MeResponse(BaseModel):
    user: UserPublic
