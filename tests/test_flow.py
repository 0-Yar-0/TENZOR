"""Интеграционный сценарий: регистрация → каталог → заказ → статусы."""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.time import earliest_pickup_date

pytestmark = pytest.mark.asyncio

async def _make_catalog(client: AsyncClient, admin_headers) -> tuple[str, str]:
    r = await client.post("/api/v1/admin/fillings", json={
        "name": "Шоколад", "surcharge_per_kg": "200.00", "is_active": True
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    filling_id = r.json()["id"]

    r = await client.post("/api/v1/admin/products", json={
        "name": "Торт",
        "description": "Вкусный",
        "base_price_per_kg": "1200.00",
        "weights_g": [1000, 1500],
        "filling_ids": [filling_id],
        "is_active": True,
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()["id"], filling_id

async def test_full_flow(client: AsyncClient, admin_headers, staff_headers, client_headers):
    product_id, filling_id = await _make_catalog(client, admin_headers)

    # каталог виден гостем
    r = await client.get("/api/v1/products")
    assert r.status_code == 200
    assert any(p["id"] == product_id for p in r.json()["items"])

    # quote
    items = [{"product_id": product_id, "filling_id": filling_id, "weight_g": 1500, "quantity": 2}]
    r = await client.post("/api/v1/orders/quote", json={"items": items}, headers=client_headers)
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["total"] == "4200.00"
    assert q["items"][0]["unit_price"] == "2100.00"

    # создание
    pickup = earliest_pickup_date().isoformat()
    idem = str(uuid.uuid4())
    r = await client.post("/api/v1/orders", json={
        "items": items,
        "expected_total": "4200.00",
        "phone": "+79991234567",
        "pickup_date": pickup,
        "comment": "С днём рождения",
    }, headers={**client_headers, "Idempotency-Key": idem})
    assert r.status_code == 201, r.text
    order = r.json()
    order_id = order["id"]
    assert order["status"] == "NEW"
    assert order["version"] == 1
    assert order["total"] == "4200.00"
    assert len(order["history"]) == 1

    # идемпотентный повтор
    r2 = await client.post("/api/v1/orders", json={
        "items": items,
        "expected_total": "4200.00",
        "phone": "+79991234567",
        "pickup_date": pickup,
        "comment": "С днём рождения",
    }, headers={**client_headers, "Idempotency-Key": idem})
    assert r2.status_code == 200
    assert r2.json()["id"] == order_id

    # тот же ключ с другим телом → 409
    r3 = await client.post("/api/v1/orders", json={
        "items": items,
        "expected_total": "4200.00",
        "phone": "+79990000000",
        "pickup_date": pickup,
    }, headers={**client_headers, "Idempotency-Key": idem})
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    # сотрудник подтверждает
    r = await client.post(f"/api/v1/staff/orders/{order_id}/status", json={
        "version": 1, "target_status": "CONFIRMED"
    }, headers=staff_headers)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2

    # пропуск стадии → 409
    r = await client.post(f"/api/v1/staff/orders/{order_id}/status", json={
        "version": 2, "target_status": "READY"
    }, headers=staff_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_TRANSITION"

    # устаревшая версия → 409
    r = await client.post(f"/api/v1/staff/orders/{order_id}/status", json={
        "version": 1, "target_status": "IN_PRODUCTION"
    }, headers=staff_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"
