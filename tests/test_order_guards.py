"""Негативные и пограничные проверки заказов."""
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.time import earliest_pickup_date, local_today

pytestmark = pytest.mark.asyncio

async def _catalog(client, admin_headers):
    r = await client.post("/api/v1/admin/fillings", json={
        "name": "Крем", "surcharge_per_kg": "0.00", "is_active": True
    }, headers=admin_headers)
    fid = r.json()["id"]
    r = await client.post("/api/v1/admin/products", json={
        "name": "Пирожное", "base_price_per_kg": "1000.00",
        "weights_g": [1000], "filling_ids": [fid], "is_active": True,
    }, headers=admin_headers)
    return r.json()["id"], fid

async def test_pickup_date_too_early(client, admin_headers, client_headers):
    pid, fid = await _catalog(client, admin_headers)
    items = [{"product_id": pid, "filling_id": fid, "weight_g": 1000, "quantity": 1}]
    r = await client.post("/api/v1/orders", json={
        "items": items, "expected_total": "1000.00",
        "phone": "+79991234567",
        "pickup_date": local_today().isoformat(),
    }, headers={**client_headers, "Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_PICKUP_DATE"

async def test_price_changed(client, admin_headers, client_headers):
    pid, fid = await _catalog(client, admin_headers)
    items = [{"product_id": pid, "filling_id": fid, "weight_g": 1000, "quantity": 1}]
    # ожидаем другую сумму
    r = await client.post("/api/v1/orders", json={
        "items": items, "expected_total": "999.00",
        "phone": "+79991234567",
        "pickup_date": earliest_pickup_date().isoformat(),
    }, headers={**client_headers, "Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PRICE_CHANGED"

async def test_invalid_phone(client, admin_headers, client_headers):
    pid, fid = await _catalog(client, admin_headers)
    items = [{"product_id": pid, "filling_id": fid, "weight_g": 1000, "quantity": 1}]
    r = await client.post("/api/v1/orders", json={
        "items": items, "expected_total": "1000.00",
        "phone": "123",
        "pickup_date": earliest_pickup_date().isoformat(),
    }, headers={**client_headers, "Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 422

async def test_quantity_limit(client, admin_headers, client_headers):
    pid, fid = await _catalog(client, admin_headers)
    items = [{"product_id": pid, "filling_id": fid, "weight_g": 1000, "quantity": 21}]
    r = await client.post("/api/v1/orders/quote", json={"items": items}, headers=client_headers)
    assert r.status_code == 422
