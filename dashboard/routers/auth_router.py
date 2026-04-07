from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from dashboard.auth import (
    create_access_token,
    get_current_user,
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
    if (
        not secrets.compare_digest(body.username, settings.admin_user)
        or not secrets.compare_digest(body.password, settings.admin_password)
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
