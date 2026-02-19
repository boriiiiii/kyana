"""
Kyana — Instagram AI Assistant for a freelance hairdresser.

FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import dashboard, webhook
from app.core.config import get_settings
from app.models.database import Base, engine

# ─── Logging ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ───────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup."""
    logger.info("Creating database tables…")
    Base.metadata.create_all(bind=engine)
    logger.info("Kyana is ready 💇‍♀️")
    yield
    logger.info("Shutting down…")


# ─── App ──────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title="Kyana",
    description=(
        "Assistant IA incognito pour coiffeuse indépendante — "
        "gère les MPs Instagram de manière naturelle."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS — allow the Next.js frontend in dev ────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────

app.include_router(webhook.router)
app.include_router(dashboard.router)


# ─── Health check ────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok", "app": settings.app_name}


@app.get("/privacy", tags=["system"])
async def privacy_policy() -> HTMLResponse:
    """Basic privacy policy page required by Meta."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html><head><title>Kyana — Privacy Policy</title></head>
    <body style="font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px;">
    <h1>Privacy Policy — Kyana</h1>
    <p>Kyana is an internal AI assistant tool. It processes Instagram direct messages
    solely to provide automated responses on behalf of the account owner.</p>
    <ul>
        <li>We do not share personal data with third parties.</li>
        <li>Messages are stored temporarily for conversation context.</li>
        <li>No data is sold or used for advertising.</li>
    </ul>
    <p>Contact: the account owner via Instagram DM.</p>
    </body></html>
    """)

