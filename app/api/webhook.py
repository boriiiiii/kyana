"""
Webhook API routes — handles Meta/Instagram webhook verification and incoming messages.

Debounce pattern:
    When a message arrives, we do NOT respond immediately. Instead, we wait
    ``RESPONSE_DEBOUNCE_SECONDS`` after the *last* message from that sender.
    If more messages arrive during that window, the timer resets and we
    accumulate all messages before sending a single AI response.
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
from app.services import ollama_service, instagram_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])

# ── Debounce state (in-memory, per sender) ───────────────
# sender_id → pending asyncio.Task
_pending_tasks: dict[str, asyncio.Task] = {}
# sender_id → list of accumulated message texts
_message_queues: dict[str, list[str]] = {}


# ─── GET /webhook — Meta verification challenge ─────────

@router.get("/webhook")
async def verify_webhook(
    response: Response,
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
) -> Response:
    """Handle the one‑time verification challenge sent by Meta."""
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
    """Receive incoming Instagram messages via the Meta webhook."""
    body: dict = await request.json()
    logger.debug("Webhook payload: %s", body)

    entries: list[dict] = body.get("entry", [])
    for entry in entries:
        for event in entry.get("messaging", []):
            await _handle_messaging_event(event, db)

        for change in entry.get("changes", []):
            if change.get("field") == "messages":
                await _handle_messaging_event(change.get("value", {}), db)

    return {"status": "ok"}


# ─── Private helpers ─────────────────────────────────────

async def _handle_messaging_event(event: dict, db: Session) -> None:
    """Accumulate message and (re)start the debounce timer for this sender."""
    sender_id: str | None = event.get("sender", {}).get("id")
    message_data: dict | None = event.get("message")

    if not sender_id or not message_data:
        logger.debug("Skipping non-message event: %s", event)
        return

    text: str = message_data.get("text", "")
    if not text:
        logger.debug("Skipping non-text message from %s", sender_id)
        return

    # 1. Get or create conversation
    conversation = _get_or_create_conversation(db, sender_id)

    # 2. Log the inbound message immediately
    _log_message(db, conversation.id, MessageDirection.INBOUND, text)

    # 3. If manual mode → do nothing more
    if conversation.mode == ConversationMode.MANUAL:
        logger.info("Conversation %s is MANUAL — skipping AI", sender_id)
        return

    # 4. Accumulate message in queue
    _message_queues.setdefault(sender_id, []).append(text)

    # 5. Cancel any existing pending timer for this sender
    existing_task = _pending_tasks.get(sender_id)
    if existing_task and not existing_task.done():
        existing_task.cancel()
        logger.debug("Debounce: timer reset for %s (%d msg(s) queued)", sender_id, len(_message_queues[sender_id]))

    # 6. Start a fresh debounce timer
    debounce_secs = get_settings().response_debounce_seconds
    logger.info(
        "Debounce: waiting %ds for %s to finish typing (%d msg(s) so far)",
        debounce_secs, sender_id, len(_message_queues[sender_id]),
    )
    task = asyncio.create_task(
        _debounced_respond(sender_id, conversation.id, db, debounce_secs)
    )
    _pending_tasks[sender_id] = task


async def _debounced_respond(
    sender_id: str,
    conversation_id: int,
    db: Session,
    delay: int,
) -> None:
    """
    Wait `delay` seconds, then respond to all accumulated messages at once.
    If cancelled (new message arrived), exit silently.
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return  # New message came in → a new task will handle it

    # Collect and clear the queue
    messages = _message_queues.pop(sender_id, [])
    _pending_tasks.pop(sender_id, None)

    if not messages:
        return

    # Re-read conversation (mode may have changed during the wait)
    conversation = (
        db.query(ConversationState)
        .filter(ConversationState.sender_id == sender_id)
        .first()
    )
    if conversation is None or conversation.mode == ConversationMode.MANUAL:
        return

    # Combine all pending messages into one prompt
    combined_message = "\n".join(messages)
    if len(messages) > 1:
        logger.info(
            "Debounce: %d messages aggregated for %s → «%s»",
            len(messages), sender_id, combined_message[:120],
        )

    # Call AI
    history = _build_history(db, conversation_id, limit=6)
    ai_result = await ollama_service.generate_response(combined_message, history)

    # Handle needs_human
    if ai_result.needs_human:
        conversation.mode = ConversationMode.MANUAL
        db.commit()
        _log_message(
            db, conversation_id, MessageDirection.OUTBOUND,
            ai_result.response or "[flagged for human]",
            needs_human=True,
        )
        logger.warning(
            "🚨 ALERTE — IA pas sûre pour %s. Messages : «%s». Basculée en MANUEL.",
            sender_id, combined_message,
        )
        return

    # Create iCloud appointment + send reply
    asyncio.create_task(
        _delayed_reply(sender_id, ai_result.response, conversation_id, db, ai_result.book)
    )


async def _delayed_reply(
    sender_id: str,
    reply_text: str,
    conversation_id: int,
    db: Session,
    booking=None,
) -> None:
    """Create the iCloud event if needed, simulate delay, then send the reply."""
    from app.services.calendar_service import ICloudCalendar
    from datetime import datetime, date as _date, timedelta

    if booking is not None:
        try:
            cal = ICloudCalendar()
            rdv_date = _date.fromisoformat(booking.date)
            start_dt = datetime.combine(
                rdv_date,
                datetime.min.time().replace(hour=booking.hour, minute=booking.minute),
            )
            end_dt = start_dt + timedelta(minutes=booking.duration_minutes)
            cal.create_event(
                summary=booking.service,
                start=start_dt,
                end=end_dt,
                description="RDV posé via Instagram par Kyana IA",
                test_event=False,
            )
            logger.info(
                "✅ RDV créé dans iCloud : %s le %s à %sh%02d",
                booking.service, booking.date, booking.hour, booking.minute,
            )
        except Exception as e:
            logger.error("⚠️ Impossible de créer le RDV dans iCloud : %s", e)

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
    """Build Ollama-compatible history from the last *limit* messages."""
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
        role = "user" if msg.direction == MessageDirection.INBOUND else "assistant"
        history.append({"role": role, "content": msg.content})
    return history
