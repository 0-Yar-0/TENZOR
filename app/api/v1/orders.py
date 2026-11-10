"""Заказы: quote, создание, клиентские операции."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.core.deps import ClientUser, SessionDep
from app.core.errors import bad_request, unprocessable
from app.schemas.common import Page
from app.schemas.order import (
    CancelIn, OrderBrief, OrderCreateIn, OrderOut, QuoteIn, QuoteOut,
)
from app.services import order_service

router = APIRouter()

@router.post("/orders/quote", response_model=QuoteOut)
async def quote(payload: QuoteIn, user: ClientUser, session: SessionDep):
    data = await order_service.quote(session, [i.model_dump() for i in payload.items])
    return QuoteOut(**data)

@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreateIn,
    user: ClientUser,
    session: SessionDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if not idempotency_key:
        raise bad_request("Заголовок Idempotency-Key обязателен", "MISSING_IDEMPOTENCY_KEY")
    try:
        key_uuid = uuid.UUID(idempotency_key)
    except ValueError:
        raise bad_request("Idempotency-Key должен быть UUID", "INVALID_IDEMPOTENCY_KEY")

    order, created = await order_service.create_order(session, user, key_uuid, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return OrderOut(**order_service.order_to_dict(order))

@router.get("/orders/my", response_model=Page[OrderBrief])
async def my_orders(
    user: ClientUser,
    session: SessionDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    rows, total = await order_service.list_client_orders(session, user, status_filter, page, page_size)
    return Page(
        items=[OrderBrief(**order_service.order_to_brief(o)) for o in rows],
        page=page, page_size=page_size, total=total,
    )

@router.get("/orders/my/{order_id}", response_model=OrderOut)
async def my_order(order_id: uuid.UUID, user: ClientUser, session: SessionDep):
    order = await order_service.get_client_order(session, order_id, user)
    return OrderOut(**order_service.order_to_dict(order))

@router.post("/orders/my/{order_id}/cancel", response_model=OrderOut)
async def cancel_my_order(order_id: uuid.UUID, payload: CancelIn, user: ClientUser, session: SessionDep):
    order = await order_service.client_cancel(session, order_id, user, payload.version)
    return OrderOut(**order_service.order_to_dict(order))
