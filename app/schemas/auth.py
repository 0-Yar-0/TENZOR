"""Схемы авторизации и пользователей."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

NAME_RE = re.compile(r"^.{2,100}$", re.DOTALL)

class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(min_length=2, max_length=100, strip_whitespace=True)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=10, max_length=128)]

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("Имя должно быть от 2 до 100 символов")
        return v

class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]

class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    role: str

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        return str(v)
