"""Операции с каталогом."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import conflict, not_found, unprocessable
from app.models.catalog import Filling, Product, ProductFilling, ProductWeight

async def list_products(
    session: AsyncSession, q: str | None, page: int, page_size: int
) -> tuple[list[Product], int]:
    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.options(selectinload(Product.weights), selectinload(Product.product_fillings))
        .order_by(Product.name, Product.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.scalars(stmt)).all())
    return rows, total

async def get_product(session: AsyncSession, product_id: uuid.UUID, include_inactive: bool = False) -> Product:
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.weights),
            selectinload(Product.product_fillings).selectinload(ProductFilling.filling),
        )
    )
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    product = await session.scalar(stmt)
    if not product:
        raise not_found("Изделие не найдено", "PRODUCT_NOT_FOUND")
    return product

async def create_product(session: AsyncSession, data: dict) -> Product:
    weights = data.pop("weights_g", [])
    filling_ids = data.pop("filling_ids", [])
    product = Product(id=uuid.uuid4(), **data)
    session.add(product)
    await session.flush()
    for w in weights:
        session.add(ProductWeight(product_id=product.id, weight_g=w))
    if filling_ids:
        await _attach_fillings(session, product.id, filling_ids)
    await session.commit()
    return await get_product(session, product.id, include_inactive=True)

async def update_product(session: AsyncSession, product_id: uuid.UUID, data: dict) -> Product:
    product = await get_product(session, product_id, include_inactive=True)
    weights = data.pop("weights_g", None)
    filling_ids = data.pop("filling_ids", None)

    for k, v in data.items():
        if v is not None:
            setattr(product, k, v)

    if weights is not None:
        await session.execute(delete(ProductWeight).where(ProductWeight.product_id == product_id))
        for w in weights:
            session.add(ProductWeight(product_id=product_id, weight_g=w))

    if filling_ids is not None:
        await session.execute(delete(ProductFilling).where(ProductFilling.product_id == product_id))
        if filling_ids:
            await _attach_fillings(session, product_id, filling_ids)

    await session.commit()
    return await get_product(session, product_id, include_inactive=True)

async def _attach_fillings(session: AsyncSession, product_id: uuid.UUID, filling_ids: list[str]) -> None:
    seen: set[str] = set()
    for fid in filling_ids:
        if fid in seen:
            raise unprocessable("Дубликаты начинок недопустимы", "DUPLICATE_FILLING")
        seen.add(fid)
        try:
            uid = uuid.UUID(fid)
        except ValueError:
            raise unprocessable(f"Некорректный UUID начинки: {fid}", "INVALID_UUID")
        filling = await session.get(Filling, uid)
        if not filling:
            raise unprocessable(f"Начинка не найдена: {fid}", "FILLING_NOT_FOUND")
        session.add(ProductFilling(product_id=product_id, filling_id=uid))

async def list_fillings_admin(session: AsyncSession) -> list[Filling]:
    return list((await session.scalars(select(Filling).order_by(Filling.name))).all())

async def create_filling(session: AsyncSession, data: dict) -> Filling:
    f = Filling(id=uuid.uuid4(), **data)
    session.add(f)
    await session.commit()
    await session.refresh(f)
    return f

async def update_filling(session: AsyncSession, filling_id: uuid.UUID, data: dict) -> Filling:
    f = await session.get(Filling, filling_id)
    if not f:
        raise not_found("Начинка не найдена", "FILLING_NOT_FOUND")
    for k, v in data.items():
        if v is not None:
            setattr(f, k, v)
    await session.commit()
    await session.refresh(f)
    return f

async def validate_configuration(
    session: AsyncSession, product_id: uuid.UUID, filling_id: uuid.UUID, weight_g: int
) -> tuple[Product, Filling]:
    """Проверяет доступность изделия, веса и начинки. Возвращает объекты."""
    product = await session.scalar(
        select(Product)
        .where(Product.id == product_id, Product.is_active.is_(True))
        .options(
            selectinload(Product.weights),
            selectinload(Product.product_fillings).selectinload(ProductFilling.filling),
        )
    )
    if not product:
        raise conflict("Изделие недоступно", "ITEM_UNAVAILABLE", {"product_id": str(product_id)})

    available_weights = {pw.weight_g for pw in product.weights}
    if weight_g not in available_weights:
        raise unprocessable("Недопустимый вес изделия", "INVALID_CONFIGURATION",
                            {"weight_g": weight_g, "allowed": sorted(available_weights)})

    fillings_map = {pf.filling_id: pf.filling for pf in product.product_fillings if pf.filling.is_active}
    filling = fillings_map.get(filling_id)
    if not filling:
        raise unprocessable("Недопустимая начинка", "INVALID_CONFIGURATION",
                            {"filling_id": str(filling_id)})
    return product, filling
