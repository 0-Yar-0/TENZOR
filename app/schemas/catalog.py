"""Схемы каталога."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NameStr = Annotated[str, StringConstraints(min_length=1, max_length=150, strip_whitespace=True)]
MoneyStr = Annotated[str, StringConstraints(pattern=r"^\d{1,9}(\.\d{1,2})?$")]

class FillingBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    surcharge_per_kg: Decimal

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        return str(v)

    @field_validator("surcharge_per_kg", mode="before")
    @classmethod
    def _dec(cls, v):
        return Decimal(v)

class ProductListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    base_price_per_kg: Decimal
    weights_g: List[int]

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        return str(v)

class ProductDetail(ProductListItem):
    fillings: List[FillingBrief]

# --- администрирование каталога ---

class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NameStr
    description: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None
    image_url: Optional[Annotated[str, StringConstraints(max_length=2048)]] = None
    base_price_per_kg: Decimal = Field(gt=0, le=Decimal("100000"))
    weights_g: List[int] = Field(default_factory=list, max_length=20)
    filling_ids: List[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("weights_g")
    @classmethod
    def _weights_ok(cls, v: List[int]) -> List[int]:
        if len(v) != len(set(v)):
            raise ValueError("Дубликаты весов недопустимы")
        for w in v:
            if not (100 <= w <= 10000):
                raise ValueError("Вес должен быть в диапазоне 100–10000 г")
        return v

    @field_validator("image_url")
    @classmethod
    def _image_ok(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith("https://"):
            raise ValueError("image_url должен быть HTTPS-ссылкой")
        return v

class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[NameStr] = None
    description: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None
    image_url: Optional[Annotated[str, StringConstraints(max_length=2048)]] = None
    base_price_per_kg: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("100000"))
    weights_g: Optional[List[int]] = Field(default=None, max_length=20)
    filling_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("weights_g")
    @classmethod
    def _weights_ok(cls, v):
        if v is not None:
            if len(v) != len(set(v)):
                raise ValueError("Дубликаты весов недопустимы")
            for w in v:
                if not (100 <= w <= 10000):
                    raise ValueError("Вес должен быть в диапазоне 100–10000 г")
        return v

    @field_validator("image_url")
    @classmethod
    def _image_ok(cls, v):
        if v and not v.startswith("https://"):
            raise ValueError("image_url должен быть HTTPS-ссылкой")
        return v

class FillingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NameStr
    surcharge_per_kg: Decimal = Field(ge=0, le=Decimal("100000"))
    is_active: bool = True

class FillingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[NameStr] = None
    surcharge_per_kg: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("100000"))
    is_active: Optional[bool] = None
