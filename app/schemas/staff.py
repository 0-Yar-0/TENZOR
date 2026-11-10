"""Схемы управления сотрудниками."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

class StaffCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(min_length=2, max_length=100, strip_whitespace=True)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=10, max_length=128)]

class StaffOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
