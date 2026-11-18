"""Роутер авторизации."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.core.deps import CurrentUser, SessionDep
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth_service

router = APIRouter()

@router.post("/auth/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterIn, session: SessionDep):
    user = await auth_service.register_client(session, payload.name, payload.email, payload.password)
    return UserOut(id=str(user.id), name=user.name, email=user.email, role=user.role)

@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, request: Request, session: SessionDep):
    token, expires_in = await auth_service.login(session, payload.email, payload.password)
    return TokenOut(access_token=token, expires_in=expires_in)

@router.get("/users/me", response_model=UserOut)
async def me(user: CurrentUser):
    return UserOut(id=str(user.id), name=user.name, email=user.email, role=user.role)
