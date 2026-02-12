"""
Webhook API routes — handles Meta/Instagram webhook verification and incoming messages.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.models.conversation import (
    ConversationMode,
    ConversationState,
    MessageDirection,
    MessageLog,
)
from app.models.database import get_db
from app.services import gemini_service, instagram_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])


# ─── GET /webhook — Meta verification challenge ─────────

@router.get("/webhook")
async def verify_webhook(
    response: Response,
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
) -> Response:
    """
    Handle the one‑time verification challenge sent by Meta
    when you register the webhook URL.
    """
    challenge = instagram_service.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge is not None:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


# ─── POST /webhook — incoming Instagram messages ────────

@router.post("/webhook", status_code=200)
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Receive incoming Instagram messages via the Meta webhook.

    Flow per message:
    1. Look up (or create) the conversation state.
    2. If mode is *manual* → log and skip.
    3. Call Gemini for a response.
    4. If ``needs_human`` → switch to manual, alert, skip.
    5. Simulate human delay, then send the reply.
    6. Log everything.
    """
    body: dict = await request.json()
    logger.debug("Webhook payload: %s", body)

    entries: list[dict] = body.get("entry", [])
    for entry in entries:
        messaging_events: list[dict] = entry.get("messaging", [])
        for event in messaging_events:
            await _handle_messaging_event(event, db)

    return {"status": "ok"}


# ─── Private helpers ─────────────────────────────────────

async def _handle_messaging_event(event: dict, db: Session) -> None:
    """Process a single messaging event from the webhook payload."""
    sender_id: str | None = event.get("sender", {}).get("id")
    message_data: dict | None = event.get("message")

    if not sender_id or not message_data:
        logger.debug("Skipping non‑message event: %s", event)
        return

    text: str = message_data.get("text", "")
    if not text:
        logger.debug("Skipping non‑text message from %s", sender_id)
        return

    # 1. Get or create conversation
    conversation = _get_or_create_conversation(db, sender_id)

    # 2. Log the inbound message
    _log_message(db, conversation.id, MessageDirection.INBOUND, text)

    # 3. If manual mode → do nothing more
    if conversation.mode == ConversationMode.MANUAL:
        logger.info("Conversation %s is MANUAL — skipping AI", sender_id)
        return

    # 4. Build lightweight history for Gemini context
    history = _build_history(db, conversation.id, limit=6)

    # 5. Generate AI response
    ai_result = await gemini_service.generate_response(text, history)

    # 6. If the AI flags doubt → switch to manual
    if ai_result.needs_human:
        conversation.mode = ConversationMode.MANUAL
        db.commit()
        _log_message(
            db, conversation.id, MessageDirection.OUTBOUND,
            ai_result.response or "[flagged for human]",
            needs_human=True,
        )
        logger.warning(
            "🚨 ALERTE — IA pas sûre pour %s. Message client : « %s ». "
            "Conversation basculée en MANUEL.",
            sender_id,
            text,
        )
        return

    # 7. Simulate a human delay then reply
    asyncio.create_task(
        _delayed_reply(sender_id, ai_result.response, conversation.id, db)
    )


async def _delayed_reply(
    sender_id: str,
    reply_text: str,
    conversation_id: int,
    db: Session,
) -> None:
    """Wait, then send the reply and log it."""
    await instagram_service.simulate_human_delay()
    success = await instagram_service.send_message(sender_id, reply_text)
    if success:
        _log_message(db, conversation_id, MessageDirection.OUTBOUND, reply_text)
    else:
        logger.error("Failed to send reply to %s", sender_id)


def _get_or_create_conversation(db: Session, sender_id: str) -> ConversationState:
    """Return existing conversation or create a new one in AUTO mode."""
    conv = (
        db.query(ConversationState)
        .filter(ConversationState.sender_id == sender_id)
        .first()
    )
    if conv is None:
        conv = ConversationState(sender_id=sender_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        logger.info("New conversation created for %s", sender_id)
    return conv


def _log_message(
    db: Session,
    conversation_id: int,
    direction: MessageDirection,
    content: str,
    needs_human: bool = False,
) -> MessageLog:
    """Persist a message to the database."""
    msg = MessageLog(
        conversation_id=conversation_id,
        direction=direction,
        content=content,
        needs_human=needs_human,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _build_history(
    db: Session,
    conversation_id: int,
    limit: int = 6,
) -> list[dict[str, str]]:
    """
    Build a Gemini‑compatible conversation history from the last *limit*
    messages (oldest → newest).
    """
    messages = (
        db.query(MessageLog)
        .filter(MessageLog.conversation_id == conversation_id)
        .order_by(MessageLog.created_at.desc())
        .limit(limit)
        .all()
    )
    messages.reverse()

    history: list[dict[str, str]] = []
    for msg in messages:
        role = "user" if msg.direction == MessageDirection.INBOUND else "model"
        history.append({"role": role, "parts": [msg.content]})
    return history
