from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from dashboard.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from dashboard.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    settings = get_settings()
    admin_hash = (
        get_password_hash(settings.admin_password) if settings.admin_password else ""
    )
    if (
        body.username != settings.admin_user
        or not admin_hash
        or not verify_password(body.password, admin_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(body.username)
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: str = Depends(get_current_user)):
    token = create_access_token(current_user)
    return TokenResponse(access_token=token)
