"""Служебные команды: создание администратора."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole

async def create_admin(name: str, email: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        norm = email.strip().lower()
        existing = await session.scalar(select(User).where(User.email_normalized == norm))
        if existing:
            print(f"Пользователь с email {email} уже существует (role={existing.role}).", file=sys.stderr)
            sys.exit(1)
        user = User(
            id=uuid.uuid4(),
            name=name.strip(),
            email=email.strip(),
            email_normalized=norm,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Администратор создан: {user.email} (id={user.id})")

def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_admin = sub.add_parser("create-admin", help="Создать администратора")
    p_admin.add_argument("--name", required=True)
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--password", required=False, help="Если не указан — будет запрошен интерактивно")

    args = parser.parse_args()

    if args.cmd == "create-admin":
        password = args.password or getpass.getpass("Пароль администратора: ")
        if len(password) < 10:
            print("Пароль должен содержать не менее 10 символов.", file=sys.stderr)
            sys.exit(2)
        asyncio.run(create_admin(args.name, args.email, password))

if __name__ == "__main__":
    main()
