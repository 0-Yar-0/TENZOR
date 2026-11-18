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

async def test_admin_list_includes_inactive_product_with_fillings(client: AsyncClient, admin_headers):
    """Regression: eager-load filling to avoid an async lazy-load 500 in the admin list."""
    filling = await client.post("/api/v1/admin/fillings", json={
        "name": "Для списка", "surcharge_per_kg": "0", "is_active": False,
    }, headers=admin_headers)
    product = await client.post("/api/v1/admin/products", json={
        "name": "Черновик", "base_price_per_kg": "100.00",
        "weights_g": [1000], "filling_ids": [filling.json()["id"]], "is_active": False,
    }, headers=admin_headers)
    assert product.status_code == 201, product.text

    response = await client.get("/api/v1/admin/products", headers=admin_headers)
    assert response.status_code == 200, response.text
    draft = next(item for item in response.json()["items"] if item["id"] == product.json()["id"])
    assert draft["is_active"] is False
