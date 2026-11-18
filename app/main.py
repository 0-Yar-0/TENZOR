"""Точка входа FastAPI."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, http_error_handler
from app.db.session import engine

_settings = get_settings()

app = FastAPI(
    title="Кондитерская — API",
    version="1.0.0",
    description="Веб-система управления заказами кондитерской. MVP.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]

app.include_router(api_router)

@app.get("/health/live", tags=["health"])
async def health_live():
    return {"status": "ok"}

@app.get("/health/ready", tags=["health"])
async def health_ready():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
