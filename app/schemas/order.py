"""Схемы заказов и расчёта."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

PHONE_RE = re.compile(r"^\+?\d{10,15}$")

class QuoteItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID
    filling_id: UUID
    weight_g: int = Field(ge=100, le=10000)
    quantity: int = Field(ge=1, le=20)

class QuoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: List[QuoteItemIn] = Field(min_length=1, max_length=20)

class QuoteItemOut(BaseModel):
    product_id: str
    filling_id: str
    product_name: str
    filling_name: str
    weight_g: int
    quantity: int
    base_price_per_kg: str
    surcharge_per_kg: str
    unit_price: str
    line_total: str

class QuoteOut(BaseModel):
    items: List[QuoteItemOut]
    total: str
    currency: str = "RUB"

class OrderCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: List[QuoteItemIn] = Field(min_length=1, max_length=20)
    expected_total: Annotated[str, StringConstraints(pattern=r"^\d{1,12}(\.\d{1,2})?$")]
    phone: str
    pickup_date: date
    comment: Optional[Annotated[str, StringConstraints(max_length=1000)]] = None

    @field_validator("phone")
    @classmethod
    def _phone_ok(cls, v: str) -> str:
        cleaned = re.sub(r"[\s()\-]", "", v)
        if not PHONE_RE.match(cleaned):
            raise ValueError("Телефон должен содержать + и 10–15 цифр")
        return cleaned

class StatusChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    target_status: str
    reason: Optional[Annotated[str, StringConstraints(max_length=500)]] = None

    @field_validator("target_status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        allowed = {"CONFIRMED", "IN_PRODUCTION", "READY", "COMPLETED", "CANCELLED"}
        if v not in allowed:
            raise ValueError("Недопустимый целевой статус")
        return v

class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)

# --- выходные схемы ---

class OrderItemOut(BaseModel):
    product_id: str
    filling_id: str
    product_name: str
    filling_name: str
    weight_g: int
    quantity: int
    base_price_per_kg: str
    surcharge_per_kg: str
    unit_price: str
    line_total: str

class HistoryOut(BaseModel):
    from_status: Optional[str]
    to_status: str
    actor_id: str
    actor_name: str
    reason: Optional[str]
    created_at: datetime

class PickupLocation(BaseModel):
    address: str
    hours: str

class OrderOut(BaseModel):
    id: str
    status: str
    version: int
    pickup_date: date
    phone: str
    comment: Optional[str]
    total: str
    currency: str = "RUB"
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]
    history: List[HistoryOut]
    pickup_location: PickupLocation

class OrderBrief(BaseModel):
    id: str
    status: str
    version: int
    pickup_date: date
    total: str
    currency: str = "RUB"
    created_at: datetime
    items_count: int
