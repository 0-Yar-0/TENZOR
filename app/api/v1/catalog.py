"""Публичный каталог."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import SessionDep
from app.schemas.catalog import FillingBrief, ProductDetail, ProductListItem
from app.schemas.common import Page
from app.services import catalog_service

router = APIRouter()

def _to_list_item(p) -> ProductListItem:
    return ProductListItem(
        id=str(p.id),
        name=p.name,
        description=p.description,
        image_url=p.image_url,
        base_price_per_kg=p.base_price_per_kg,
        weights_g=sorted({w.weight_g for w in p.weights}),
    )

@router.get("/products", response_model=Page[ProductListItem])
async def list_products(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=150)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    rows, total = await catalog_service.list_products(session, q, page, page_size)
    items = [_to_list_item(p) for p in rows if p.weights]
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product(product_id: uuid.UUID, session: SessionDep):
    p = await catalog_service.get_product(session, product_id)
    fillings = [
        FillingBrief(
            id=str(pf.filling.id),
            name=pf.filling.name,
            surcharge_per_kg=pf.filling.surcharge_per_kg,
        )
        for pf in p.product_fillings
        if pf.filling.is_active
    ]
    if not p.weights or not fillings:
        from app.core.errors import not_found
        raise not_found("Изделие не найдено", "PRODUCT_NOT_FOUND")
    return ProductDetail(
        id=str(p.id),
        name=p.name,
        description=p.description,
        image_url=p.image_url,
        base_price_per_kg=p.base_price_per_kg,
        weights_g=sorted({w.weight_g for w in p.weights}),
        fillings=fillings,
    )
