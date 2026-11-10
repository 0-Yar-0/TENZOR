"""Тесты каталога и прав."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_client_cannot_admin(client: AsyncClient, client_headers):
    r = await client.post("/api/v1/admin/fillings", json={
        "name": "X", "surcharge_per_kg": "0", "is_active": True
    }, headers=client_headers)
    assert r.status_code == 403

async def test_hidden_product_404(client: AsyncClient, admin_headers):
    # создаём неактивную начинку и изделие без активных начинок
    r = await client.post("/api/v1/admin/fillings", json={
        "name": "Скрытая", "surcharge_per_kg": "0", "is_active": False
    }, headers=admin_headers)
    fid = r.json()["id"]
    r = await client.post("/api/v1/admin/products", json={
        "name": "Скрытое", "base_price_per_kg": "100.00",
        "weights_g": [1000], "filling_ids": [fid], "is_active": True,
    }, headers=admin_headers)
    pid = r.json()["id"]
    r = await client.get(f"/api/v1/products/{pid}")
    assert r.status_code == 404
