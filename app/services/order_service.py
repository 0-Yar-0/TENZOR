"""Бизнес-логика заказов: расчёт, создание, идемпотентность, переходы."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import AppError, bad_request, conflict, forbidden, not_found, unprocessable
from app.core.time import is_pickup_date_valid
from app.models.order import (
    ALLOWED_TRANSITIONS, IdempotencyRecord, Order, OrderItem, OrderStatus, OrderStatusHistory,
)
from app.models.user import User, UserRole
from app.schemas.order import OrderCreateIn
from app.services import catalog_service
from app.services.pricing import line_total, money_str, round_money, unit_price

_settings = get_settings()

# ---------- quote ----------

async def quote(session: AsyncSession, items: list[dict]) -> dict:
    if not items:
        raise unprocessable("Корзина пуста", "EMPTY_CART")
    normalized = _normalize_items(items)
    result_items: list[dict] = []
    total = Decimal("0.00")
    for it in normalized:
        product, filling = await catalog_service.validate_configuration(
            session, it["product_id"], it["filling_id"], it["weight_g"]
        )
        up = unit_price(it["weight_g"], product.base_price_per_kg, filling.surcharge_per_kg)
        lt = line_total(up, it["quantity"])
        total += lt
        result_items.append({
            "product_id": str(product.id),
            "filling_id": str(filling.id),
            "product_name": product.name,
            "filling_name": filling.name,
            "weight_g": it["weight_g"],
            "quantity": it["quantity"],
            "base_price_per_kg": money_str(product.base_price_per_kg),
            "surcharge_per_kg": money_str(filling.surcharge_per_kg),
            "unit_price": money_str(up),
            "line_total": money_str(lt),
        })
    return {"items": result_items, "total": money_str(total), "currency": "RUB"}

def _normalize_items(items: list[dict]) -> list[dict]:
    """Слияние одинаковых конфигураций; ограничение 20 строк / 20 шт."""
    if len(items) > 20:
        raise unprocessable("Не более 20 строк в корзине", "CART_TOO_LARGE")
    merged: dict[tuple[str, str, int], int] = {}
    for it in items:
        pid = str(it["product_id"])
        fid = str(it["filling_id"])
        w = int(it["weight_g"])
        q = int(it["quantity"])
        if not (1 <= q <= 20):
            raise unprocessable("Количество должно быть 1–20", "INVALID_QUANTITY")
        key = (pid, fid, w)
        merged[key] = merged.get(key, 0) + q
        if merged[key] > 20:
            raise unprocessable("Суммарное количество конфигурации не более 20", "INVALID_QUANTITY")
    if len(merged) > 20:
        raise unprocessable("Не более 20 строк в корзине", "CART_TOO_LARGE")
    return [
        {"product_id": uuid.UUID(pid), "filling_id": uuid.UUID(fid), "weight_g": w, "quantity": q}
        for (pid, fid, w), q in merged.items()
    ]

# ---------- создание заказа ----------

def _body_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def _normalized_body_for_hash(data: OrderCreateIn) -> dict:
    items = sorted(
        [{"product_id": str(i.product_id), "filling_id": str(i.filling_id),
          "weight_g": i.weight_g, "quantity": i.quantity} for i in data.items],
        key=lambda x: (x["product_id"], x["filling_id"], x["weight_g"]),
    )
    return {
        "items": items,
        "expected_total": data.expected_total,
        "phone": data.phone,
        "pickup_date": data.pickup_date.isoformat(),
        "comment": data.comment or "",
    }

async def create_order(
    session: AsyncSession,
    client: User,
    idempotency_key: uuid.UUID,
    data: OrderCreateIn,
) -> tuple[Order, bool]:
    """Возвращает (order, created). created=False при идемпотентном повторе."""
    if not is_pickup_date_valid(data.pickup_date):
        from app.core.time import earliest_pickup_date
        raise unprocessable(
            "Слишком ранняя дата самовывоза",
            "INVALID_PICKUP_DATE",
            {"min_date": earliest_pickup_date().isoformat()},
        )

    body_hash = _body_hash(_normalized_body_for_hash(data))

    # Проверяем существующий ключ до начала тяжёлой работы
    existing = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.client_id == client.id,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != body_hash:
            raise conflict("Ключ идемпотентности уже использован с другим телом запроса",
                           "IDEMPOTENCY_KEY_REUSED")
        order = await get_order_full(session, existing.order_id)
        return order, False

    normalized = _normalize_items([i.model_dump() for i in data.items])

    try:
        async with session.begin_nested():
            # Блокируем строки каталога в стабильном порядке, чтобы не было дедлока
            for it in sorted(normalized, key=lambda x: (str(x["product_id"]), str(x["filling_id"]), x["weight_g"])):
                await session.execute(
                    text("SELECT id FROM products WHERE id = :pid FOR UPDATE"),
                    {"pid": str(it["product_id"])},
                )
                await session.execute(
                    text("SELECT id FROM fillings WHERE id = :fid FOR UPDATE"),
                    {"fid": str(it["filling_id"])},
                )

            items_out: list[dict] = []
            total = Decimal("0.00")
            for it in normalized:
                product, filling = await catalog_service.validate_configuration(
                    session, it["product_id"], it["filling_id"], it["weight_g"]
                )
                up = unit_price(it["weight_g"], product.base_price_per_kg, filling.surcharge_per_kg)
                lt = line_total(up, it["quantity"])
                total += lt
                items_out.append({
                    "product": product, "filling": filling,
                    "weight_g": it["weight_g"], "quantity": it["quantity"],
                    "unit_price": up, "line_total": lt,
                })

            total = round_money(total)
            expected = Decimal(data.expected_total)
            if total != expected:
                raise conflict(
                    "Цена изменилась с момента расчёта",
                    "PRICE_CHANGED",
                    {"expected_total": money_str(expected), "actual_total": money_str(total)},
                )

            order = Order(
                id=uuid.uuid4(),
                client_id=client.id,
                phone=data.phone,
                pickup_date=data.pickup_date,
                comment=data.comment,
                status=OrderStatus.NEW.value,
                total=total,
                version=1,
            )
            session.add(order)
            await session.flush()

            for row in items_out:
                p, f = row["product"], row["filling"]
                session.add(OrderItem(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    product_id=p.id,
                    filling_id=f.id,
                    product_name=p.name,
                    filling_name=f.name,
                    weight_g=row["weight_g"],
                    quantity=row["quantity"],
                    base_price_per_kg=p.base_price_per_kg,
                    surcharge_per_kg=f.surcharge_per_kg,
                    unit_price=row["unit_price"],
                    line_total=row["line_total"],
                ))

            session.add(OrderStatusHistory(
                id=uuid.uuid4(),
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.NEW.value,
                actor_id=client.id,
                actor_name=client.name,
                reason=None,
            ))

            session.add(IdempotencyRecord(
                id=uuid.uuid4(),
                client_id=client.id,
                key=idempotency_key,
                request_hash=body_hash,
                order_id=order.id,
            ))

        await session.commit()
    except AppError:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        # гонка одинаковых ключей
        if "uq_idempotency_client_key" in str(exc) or "duplicate key" in str(exc).lower():
            existing = await session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.client_id == client.id,
                    IdempotencyRecord.key == idempotency_key,
                )
            )
            if existing:
                if existing.request_hash != body_hash:
                    raise conflict("Ключ идемпотентности уже использован с другим телом запроса",
                                   "IDEMPOTENCY_KEY_REUSED")
                order = await get_order_full(session, existing.order_id)
                return order, False
        raise

    order = await get_order_full(session, order.id)
    return order, True

# ---------- чтение ----------

def _order_query():
    return select(Order).options(
        selectinload(Order.items),
        selectinload(Order.history),
    )

async def get_order_full(session: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await session.scalar(_order_query().where(Order.id == order_id))
    if not order:
        raise not_found("Заказ не найден", "ORDER_NOT_FOUND")
    return order

async def get_client_order(session: AsyncSession, order_id: uuid.UUID, client: User) -> Order:
    order = await get_order_full(session, order_id)
    if order.client_id != client.id:
        raise not_found("Заказ не найден", "ORDER_NOT_FOUND")
    return order

async def list_client_orders(
    session: AsyncSession, client: User, status: str | None, page: int, page_size: int
) -> tuple[list[Order], int]:
    stmt = select(Order).where(Order.client_id == client.id)
    if status:
        stmt = stmt.where(Order.status == status)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.options(selectinload(Order.items), selectinload(Order.history))
        .order_by(Order.created_at.desc(), Order.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.scalars(stmt)).all())
    return rows, total

async def list_staff_orders(
    session: AsyncSession,
    status: str | None,
    pickup_date_from: date | None,
    pickup_date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[list[Order], int]:
    if pickup_date_from and pickup_date_to and pickup_date_from > pickup_date_to:
        raise unprocessable("Начало диапазона дат позже конца", "INVALID_DATE_RANGE")
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if pickup_date_from:
        stmt = stmt.where(Order.pickup_date >= pickup_date_from)
    if pickup_date_to:
        stmt = stmt.where(Order.pickup_date <= pickup_date_to)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.options(selectinload(Order.items), selectinload(Order.history))
        .order_by(Order.created_at.desc(), Order.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.scalars(stmt)).all())
    return rows, total

# ---------- переходы ----------

async def client_cancel(session: AsyncSession, order_id: uuid.UUID, client: User, version: int) -> Order:
    order = await get_order_full(session, order_id)
    if order.client_id != client.id:
        raise not_found("Заказ не найден", "ORDER_NOT_FOUND")
    if order.status != OrderStatus.NEW.value:
        raise conflict("Клиент может отменить только новый заказ", "INVALID_TRANSITION",
                       {"status": order.status})
    return await _apply_transition(
        session, order, version, OrderStatus.CANCELLED,
        actor=client, reason="Отменён клиентом",
    )

async def staff_transition(
    session: AsyncSession,
    order_id: uuid.UUID,
    actor: User,
    version: int,
    target: str,
    reason: str | None,
) -> Order:
    order = await get_order_full(session, order_id)
    target_status = OrderStatus(target)
    current = OrderStatus(order.status)
    if target_status not in ALLOWED_TRANSITIONS[current]:
        raise conflict("Этот переход статуса недоступен", "INVALID_TRANSITION",
                       {"status": current.value, "target": target_status.value})
    if target_status == OrderStatus.CANCELLED:
        if not reason or not reason.strip():
            raise unprocessable("Причина отмены обязательна", "REASON_REQUIRED")
    return await _apply_transition(
        session, order, version, target_status, actor=actor, reason=reason,
    )

async def _apply_transition(
    session: AsyncSession,
    order: Order,
    version: int,
    target: OrderStatus,
    actor: User,
    reason: str | None,
) -> Order:
    from_status = OrderStatus(order.status)

    # BR-10: условное обновление по id и version
    result = await session.execute(
        text(
            "UPDATE orders SET status = :st, version = version + 1, updated_at = now() "
            "WHERE id = :oid AND version = :ver RETURNING version"
        ),
        {"st": target.value, "oid": str(order.id), "ver": version},
    )
    row = result.first()
    if not row:
        current = await session.scalar(
            select(Order).where(Order.id == order.id)
        )
        raise conflict(
            "Версия заказа устарела",
            "VERSION_CONFLICT",
            {
                "current_version": current.version if current else None,
                "current_status": current.status if current else None,
            },
        )

    trimmed = reason.strip() if reason else None
    session.add(OrderStatusHistory(
        id=uuid.uuid4(),
        order_id=order.id,
        from_status=from_status.value,
        to_status=target.value,
        actor_id=actor.id,
        actor_name=actor.name,
        reason=trimmed,
    ))
    await session.commit()
    return await get_order_full(session, order.id)

# ---------- представление ----------

def order_to_dict(order: Order) -> dict:
    return {
        "id": str(order.id),
        "status": order.status,
        "version": order.version,
        "pickup_date": order.pickup_date,
        "phone": order.phone,
        "comment": order.comment,
        "total": money_str(order.total),
        "currency": "RUB",
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": [
            {
                "product_id": str(i.product_id),
                "filling_id": str(i.filling_id),
                "product_name": i.product_name,
                "filling_name": i.filling_name,
                "weight_g": i.weight_g,
                "quantity": i.quantity,
                "base_price_per_kg": money_str(i.base_price_per_kg),
                "surcharge_per_kg": money_str(i.surcharge_per_kg),
                "unit_price": money_str(i.unit_price),
                "line_total": money_str(i.line_total),
            }
            for i in order.items
        ],
        "history": [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "actor_id": str(h.actor_id),
                "actor_name": h.actor_name,
                "reason": h.reason,
                "created_at": h.created_at,
            }
            for h in order.history
        ],
        "pickup_location": {
            "address": _settings.pickup_address,
            "hours": _settings.pickup_hours,
        },
    }

def order_to_brief(order: Order) -> dict:
    return {
        "id": str(order.id),
        "status": order.status,
        "version": order.version,
        "pickup_date": order.pickup_date,
        "total": money_str(order.total),
        "currency": "RUB",
        "created_at": order.created_at,
        "items_count": len(order.items),
    }
