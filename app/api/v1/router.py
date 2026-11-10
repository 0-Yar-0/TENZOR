"""Сборка v1-роутера."""
from fastapi import APIRouter

from app.api.v1 import auth, catalog, orders, staff

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(orders.router, tags=["orders"])
api_router.include_router(staff.router, tags=["staff", "admin"])
