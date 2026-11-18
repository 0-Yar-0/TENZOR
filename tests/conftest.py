"""Фикстуры тестов: изолированная БД, клиент, пользователи."""
from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.user import User, UserRole

# Для тестов нужна отдельная БД, например candy_test
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://candy:candy@localhost:5432/candy_test",
)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()

@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as s:
        yield s
        await s.rollback()

@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _override():
        async with maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def admin_user(session):
    u = User(
        id=uuid.uuid4(),
        name="Admin",
        email="admin@test.local",
        email_normalized="admin@test.local",
        password_hash=hash_password("AdminPassword123"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u

@pytest_asyncio.fixture
async def staff_user(session):
    u = User(
        id=uuid.uuid4(),
        name="Staff",
        email="staff@test.local",
        email_normalized="staff@test.local",
        password_hash=hash_password("StaffPassword123"),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u

@pytest_asyncio.fixture
async def client_user(session):
    u = User(
        id=uuid.uuid4(),
        name="Client",
        email="client@test.local",
        email_normalized="client@test.local",
        password_hash=hash_password("ClientPassword123"),
        role=UserRole.CLIENT.value,
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u

async def auth_headers(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

@pytest_asyncio.fixture
async def admin_headers(client, admin_user):
    return await auth_headers(client, "admin@test.local", "AdminPassword123")

@pytest_asyncio.fixture
async def staff_headers(client, staff_user):
    return await auth_headers(client, "staff@test.local", "StaffPassword123")

@pytest_asyncio.fixture
async def client_headers(client, client_user):
    return await auth_headers(client, "client@test.local", "ClientPassword123")
