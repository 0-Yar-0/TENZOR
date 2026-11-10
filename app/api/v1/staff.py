"""Панель сотрудников и администратора."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import AdminUser, SessionDep, StaffUser
from app.schemas.catalog import (
    FillingCreate, FillingUpdate, ProductCreate, ProductDetail, ProductUpdate,
)
from app.schemas.common import Page
from app.schemas.order import OrderBrief, OrderOut, StatusChangeIn
from app.schemas.staff import StaffCreateIn, StaffOut
from app.services import auth_service, catalog_service, order_service

router = APIRouter()

# ---------- заказы ----------

@router.get("/staff/orders", response_model=Page[OrderBrief])
async def staff_list_orders(
    user: StaffUser,
    session: SessionDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    pickup_date_from: Annotated[date | None, Query()] = None,
    pickup_date_to: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    rows, total = await order_service.list_staff_orders(
        session, status_filter, pickup_date_from, pickup_date_to, page, page_size
    )
    return Page(
        items=[OrderBrief(**order_service.order_to_brief(o)) for o in rows],
        page=page, page_size=page_size, total=total,
    )

@router.get("/staff/orders/{order_id}", response_model=OrderOut)
async def staff_get_order(order_id: uuid.UUID, user: StaffUser, session: SessionDep):
    order = await order_service.get_order_full(session, order_id)
    return OrderOut(**order_service.order_to_dict(order))

@router.post("/staff/orders/{order_id}/status", response_model=OrderOut)
async def staff_change_status(
    order_id: uuid.UUID, payload: StatusChangeIn, user: StaffUser, session: SessionDep
):
    order = await order_service.staff_transition(
        session, order_id, user, payload.version, payload.target_status, payload.reason
    )
    return OrderOut(**order_service.order_to_dict(order))

# ---------- каталог (ADMIN) ----------

@router.get("/admin/products", response_model=Page[ProductDetail])
async def admin_list_products(
    user: AdminUser,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=150)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    from sqlalchemy import func, select
    from app.models.catalog import Product
    from sqlalchemy.orm import selectinload

    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.options(selectinload(Product.weights),
                     selectinload(Product.product_fillings))
        .order_by(Product.name, Product.id)
        .offset((page - 1) * page_size).limit(page_size)
    )
    rows = list((await session.scalars(stmt)).all())
    from app.schemas.catalog import FillingBrief
    items = []
    for p in rows:
        fillings = [
            FillingBrief(id=str(pf.filling.id), name=pf.filling.name,
                         surcharge_per_kg=pf.filling.surcharge_per_kg)
            for pf in p.product_fillings if pf.filling
        ]
        items.append(ProductDetail(
            id=str(p.id), name=p.name, description=p.description, image_url=p.image_url,
            base_price_per_kg=p.base_price_per_kg,
            weights_g=sorted({w.weight_g for w in p.weights}),
            fillings=fillings,
        ))
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.post("/admin/products", response_model=ProductDetail, status_code=201)
async def admin_create_product(payload: ProductCreate, user: AdminUser, session: SessionDep):
    p = await catalog_service.create_product(session, payload.model_dump())
    from app.schemas.catalog import FillingBrief
    return ProductDetail(
        id=str(p.id), name=p.name, description=p.description, image_url=p.image_url,
        base_price_per_kg=p.base_price_per_kg,
        weights_g=sorted({w.weight_g for w in p.weights}),
        fillings=[
            FillingBrief(id=str(pf.filling.id), name=pf.filling.name,
                         surcharge_per_kg=pf.filling.surcharge_per_kg)
            for pf in p.product_fillings
        ],
    )

@router.patch("/admin/products/{product_id}", response_model=ProductDetail)
async def admin_update_product(
    product_id: uuid.UUID, payload: ProductUpdate, user: AdminUser, session: SessionDep
):
    p = await catalog_service.update_product(session, product_id, payload.model_dump(exclude_unset=True))
    from app.schemas.catalog import FillingBrief
    return ProductDetail(
        id=str(p.id), name=p.name, description=p.description, image_url=p.image_url,
        base_price_per_kg=p.base_price_per_kg,
        weights_g=sorted({w.weight_g for w in p.weights}),
        fillings=[
            FillingBrief(id=str(pf.filling.id), name=pf.filling.name,
                         surcharge_per_kg=pf.filling.surcharge_per_kg)
            for pf in p.product_fillings
        ],
    )

# ---------- начинки ----------

@router.get("/admin/fillings")
async def admin_list_fillings(user: AdminUser, session: SessionDep):
    rows = await catalog_service.list_fillings_admin(session)
    return [
        {"id": str(f.id), "name": f.name,
         "surcharge_per_kg": str(f.surcharge_per_kg), "is_active": f.is_active}
        for f in rows
    ]

@router.post("/admin/fillings", status_code=201)
async def admin_create_filling(payload: FillingCreate, user: AdminUser, session: SessionDep):
    f = await catalog_service.create_filling(session, payload.model_dump())
    return {"id": str(f.id), "name": f.name,
            "surcharge_per_kg": str(f.surcharge_per_kg), "is_active": f.is_active}

@router.patch("/admin/fillings/{filling_id}")
async def admin_update_filling(
    filling_id: uuid.UUID, payload: FillingUpdate, user: AdminUser, session: SessionDep
):
    f = await catalog_service.update_filling(session, filling_id, payload.model_dump(exclude_unset=True))
    return {"id": str(f.id), "name": f.name,
            "surcharge_per_kg": str(f.surcharge_per_kg), "is_active": f.is_active}

# ---------- сотрудники ----------

@router.post("/admin/staff", response_model=StaffOut, status_code=201)
async def admin_create_staff(payload: StaffCreateIn, user: AdminUser, session: SessionDep):
    u = await auth_service.create_staff(session, payload.name, payload.email, payload.password)
    return StaffOut(id=str(u.id), name=u.name, email=u.email, role=u.role, is_active=u.is_active)

@router.patch("/admin/staff/{staff_id}/block", response_model=StaffOut)
async def admin_block_staff(staff_id: uuid.UUID, user: AdminUser, session: SessionDep):
    u = await auth_service.set_staff_active(session, staff_id, False)
    return StaffOut(id=str(u.id), name=u.name, email=u.email, role=u.role, is_active=u.is_active)

@router.patch("/admin/staff/{staff_id}/unblock", response_model=StaffOut)
async def admin_unblock_staff(staff_id: uuid.UUID, user: AdminUser, session: SessionDep):
    u = await auth_service.set_staff_active(session, staff_id, True)
    return StaffOut(id=str(u.id), name=u.name, email=u.email, role=u.role, is_active=u.is_active)
