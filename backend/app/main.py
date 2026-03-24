from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Seed admin user on startup using the app's get_db dependency so tests
    # can override the database with SQLite.
    from app.database import get_db
    from app.services.auth_service import seed_admin

    # Resolve get_db through the dependency override mechanism if present
    _get_db = app.dependency_overrides.get(get_db, get_db)
    db_gen = _get_db()
    db = next(db_gen)
    try:
        seed_admin(db)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    yield


app = FastAPI(
    title="Shopify QA AI",
    description="Automated visual & functional QA for Shopify storefronts",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.auth import router as auth_router  # noqa: E402

app.include_router(auth_router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    """Basic liveness probe.  Will be extended with DB/Redis/Celery checks in a later task."""
    return {"status": "ok"}
