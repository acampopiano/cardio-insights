from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_auth_service
from app.core.security import get_current_claims, get_current_token
from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse, MeResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> LoginResponse:
    try:
        return LoginResponse(**auth_service.login(payload.username, payload.password))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", response_model=LogoutResponse)
def logout(
    token: str = Depends(get_current_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    return LogoutResponse(**auth_service.logout(token))


@router.get("/me", response_model=MeResponse)
def me(
    claims: dict = Depends(get_current_claims),
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    username = claims.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        user = auth_service.me(username)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MeResponse(user=user)
