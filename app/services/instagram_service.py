"""
Instagram Graph API service — send messages and verify webhooks.

Uses the new Instagram API (with Instagram Login) endpoints.
"""

import asyncio
import logging
import random

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.instagram.com/v25.0"


# ─── Send a message via the Instagram Messaging API ──────

async def send_message(recipient_id: str, text: str) -> bool:
    """
    Send a text message to an Instagram user via the Instagram Graph API.

    Returns ``True`` on success, ``False`` otherwise.
    """
    settings = get_settings()
    url = f"{GRAPH_API_URL}/{settings.insta_account_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    headers = {
        "Authorization": f"Bearer {settings.insta_access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return True

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Instagram API error %s: %s",
            exc.response.status_code,
            exc.response.text,
        )
        return False

    except httpx.RequestError as exc:
        logger.error("Instagram API request failed: %s", exc)
        return False


# ─── Webhook verification ────────────────────────────────

def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    """
    Validate the Meta webhook verification challenge.

    Returns the ``challenge`` string if the token matches, ``None`` otherwise.
    """
    settings = get_settings()
    if mode == "subscribe" and token == settings.insta_verify_token:
        return challenge
    logger.warning("Webhook verification failed (mode=%s)", mode)
    return None


# ─── Human delay simulation ──────────────────────────────

async def simulate_human_delay() -> None:
    """
    Wait a random amount of time (30 – 120 s) to mimic a human typing.

    For the MVP this uses ``asyncio.sleep``; in production this would be
    replaced by a task‑queue delay (Celery / ARQ).
    """
    # delay = random.uniform(30, 120)
    delay = 5
    await asyncio.sleep(delay)
