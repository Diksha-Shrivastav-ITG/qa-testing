from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title="Shopify QA AI",
    description="Automated visual & functional QA for Shopify storefronts",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    """Basic liveness probe.  Will be extended with DB/Redis/Celery checks in a later task."""
    return {"status": "ok"}
