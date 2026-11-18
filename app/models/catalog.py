"""Каталог: изделия, веса, начинки и связи."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    base_price_per_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    weights: Mapped[list[ProductWeight]] = relationship(back_populates="product", cascade="all, delete-orphan")
    product_fillings: Mapped[list[ProductFilling]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("base_price_per_kg > 0", name="ck_products_base_price_positive"),
    )

class ProductWeight(Base):
    __tablename__ = "product_weights"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    weight_g: Mapped[int] = mapped_column(Integer, primary_key=True)

    product: Mapped[Product] = relationship(back_populates="weights")

    __table_args__ = (
        CheckConstraint("weight_g BETWEEN 100 AND 10000", name="ck_weights_range"),
    )

class Filling(Base):
    __tablename__ = "fillings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    surcharge_per_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("surcharge_per_kg >= 0", name="ck_fillings_surcharge_nonnegative"),
    )

class ProductFilling(Base):
    __tablename__ = "product_fillings"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    filling_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fillings.id", ondelete="RESTRICT"), primary_key=True
    )

    product: Mapped[Product] = relationship(back_populates="product_fillings")
    filling: Mapped[Filling] = relationship()
