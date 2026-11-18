"""FastAPI-зависимости: сессия, текущий пользователь, роли."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, unauthorized
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User, UserRole

SessionDep = Annotated[AsyncSession, Depends(get_session)]

async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized("Отсутствует токен авторизации", "INVALID_TOKEN")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except JWTError:
        raise unauthorized("Недействительный токен", "INVALID_TOKEN")

    if payload.get("type") != "access":
        raise unauthorized("Недействительный тип токена", "INVALID_TOKEN")

    user_id = payload.get("sub")
    if not user_id:
        raise unauthorized("Недействительный токен", "INVALID_TOKEN")

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise unauthorized("Пользователь неактивен или не найден", "INACTIVE_USER")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

async def require_role(user: CurrentUser, allowed: set[str]) -> User:
    if user.role not in allowed:
        raise forbidden("Недостаточно прав для выполнения действия", "FORBIDDEN_ROLE")
    return user

async def get_staff(user: CurrentUser) -> User:
    return await require_role(user, {UserRole.STAFF.value, UserRole.ADMIN.value})

async def get_admin(user: CurrentUser) -> User:
    return await require_role(user, {UserRole.ADMIN.value})

async def get_client(user: CurrentUser) -> User:
    return await require_role(user, {UserRole.CLIENT.value})

StaffUser = Annotated[User, Depends(get_staff)]
AdminUser = Annotated[User, Depends(get_admin)]
ClientUser = Annotated[User, Depends(get_client)]

def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")
