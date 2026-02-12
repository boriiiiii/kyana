"""
Instagram Graph API service — send messages and verify webhooks.
"""

import asyncio
import logging
import random

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v19.0"


# ─── Send a message via the Instagram Messaging API ──────

async def send_message(recipient_id: str, text: str) -> bool:
    """
    Send a text message to an Instagram user via the Graph API.

    Returns ``True`` on success, ``False`` otherwise.
    """
    settings = get_settings()
    url = f"{GRAPH_API_URL}/{settings.fb_page_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    headers = {
        "Authorization": f"Bearer {settings.insta_access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info(
                "Message sent to %s (status=%s)", recipient_id, resp.status_code
            )
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
        logger.info("Webhook verified successfully")
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
    delay = random.uniform(30, 120)
    logger.info("Simulating human delay: %.1f s", delay)
    await asyncio.sleep(delay)
