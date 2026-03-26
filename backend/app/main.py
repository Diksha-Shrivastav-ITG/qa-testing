# from __future__ import annotations

# from contextlib import asynccontextmanager
# from typing import AsyncGenerator

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from app.config import settings


# @asynccontextmanager
# async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
#     # Seed admin user on startup using the app's get_db dependency so tests
#     # can override the database with SQLite.
#     from app.database import get_db
#     from app.services.auth_service import seed_admin

#     # Resolve get_db through the dependency override mechanism if present
#     _get_db = app.dependency_overrides.get(get_db, get_db)
#     db_gen = _get_db()
#     db = next(db_gen)
#     try:
#         seed_admin(db)
#     finally:
#         try:
#             next(db_gen)
#         except StopIteration:
#             pass

#     yield


# app = FastAPI(
#     title="Shopify QA AI",
#     description="Automated visual & functional QA for Shopify storefronts",
#     version="0.1.0",
#     lifespan=lifespan,
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.allowed_origins_list,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# from app.routers.auth import router as auth_router  # noqa: E402
# from app.routers import functional_tests  # noqa: E402
# from app.routers import issues  # noqa: E402
# from app.routers import projects  # noqa: E402
# from app.routers import reports  # noqa: E402
# from app.routers import runs  # noqa: E402

# app.include_router(auth_router)
# app.include_router(projects.router)
# app.include_router(runs.router)
# app.include_router(issues.router)
# app.include_router(reports.router)
# app.include_router(functional_tests.router)


# @app.get("/api/health", tags=["health"])
# async def health_check() -> dict:
#     """Basic liveness probe.  Will be extended with DB/Redis/Celery checks in a later task."""
#     return {"status": "ok"}



from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.database import get_db
    from app.services.auth_service import seed_admin

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


# ✅ FIRST create app
app = FastAPI(
    title="Shopify QA AI",
    description="Automated visual & functional QA for Shopify storefronts",
    version="0.1.0",
    lifespan=lifespan,
)

# ✅ THEN add CORS (only once)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # or settings.allowed_origins_list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers
from app.routers.auth import router as auth_router  # noqa: E402
from app.routers import functional_tests  # noqa: E402
from app.routers import issues  # noqa: E402
from app.routers import projects  # noqa: E402
from app.routers import reports  # noqa: E402
from app.routers import runs  # noqa: E402

app.include_router(auth_router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(issues.router)
app.include_router(reports.router)
app.include_router(functional_tests.router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}


import os
from fastapi.staticfiles import StaticFiles

_storage_path = os.environ.get("STORAGE_PATH", "/app/storage")
os.makedirs(_storage_path, exist_ok=True)
app.mount("/storage", StaticFiles(directory=_storage_path), name="storage")