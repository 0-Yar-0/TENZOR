"""Регистрация, вход, создание сотрудников."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, unauthorized, not_found, unprocessable
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User, UserRole

def _normalize_email(email: str) -> str:
    return email.strip().lower()

async def register_client(session: AsyncSession, name: str, email: str, password: str) -> User:
    norm = _normalize_email(email)
    existing = await session.scalar(select(User).where(User.email_normalized == norm))
    if existing:
        raise conflict("Пользователь с таким email уже существует", "EMAIL_EXISTS")
    user = User(
        id=uuid.uuid4(),
        name=name.strip(),
        email=email.strip(),
        email_normalized=norm,
        password_hash=hash_password(password),
        role=UserRole.CLIENT.value,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def login(session: AsyncSession, email: str, password: str) -> tuple[str, int]:
    norm = _normalize_email(email)
    user = await session.scalar(select(User).where(User.email_normalized == norm))
    if not user or not verify_password(password, user.password_hash):
        raise unauthorized("Неверный email или пароль", "INVALID_CREDENTIALS")
    if not user.is_active:
        raise unauthorized("Пользователь неактивен", "INACTIVE_USER")
    token, expires_in = create_access_token(str(user.id), user.role)
    return token, expires_in

async def create_staff(session: AsyncSession, name: str, email: str, password: str) -> User:
    norm = _normalize_email(email)
    existing = await session.scalar(select(User).where(User.email_normalized == norm))
    if existing:
        raise conflict("Пользователь с таким email уже существует", "EMAIL_EXISTS")
    user = User(
        id=uuid.uuid4(),
        name=name.strip(),
        email=email.strip(),
        email_normalized=norm,
        password_hash=hash_password(password),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def set_staff_active(session: AsyncSession, staff_id: uuid.UUID, active: bool) -> User:
    user = await session.get(User, staff_id)
    if not user or user.role != UserRole.STAFF.value:
        raise not_found("Сотрудник не найден", "STAFF_NOT_FOUND")
    user.is_active = active
    await session.commit()
    await session.refresh(user)
    return user
