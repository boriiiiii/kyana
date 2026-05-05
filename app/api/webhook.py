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
    attachments: list = message_data.get("attachments", [])

    if not text and not attachments:
        logger.debug("Skipping non-text, non-attachment message from %s", sender_id)
        return

    if not text and attachments:
        attachment_type = attachments[0].get("type", "media") if attachments else "media"
        if attachment_type == "image":
            text = "[photo envoyée]"
        elif attachment_type == "audio":
            text = "[message vocal envoyé]"
        elif attachment_type == "video":
            text = "[vidéo envoyée]"
        else:
            text = f"[{attachment_type} envoyé]"
        logger.info("Média reçu de %s : %s", sender_id, text)

    # 1. Get or create conversation
    conversation = _get_or_create_conversation(db, sender_id)

    # 2. Log the inbound message immediately
    _log_message(db, conversation.id, MessageDirection.INBOUND, text)

    # 3. If manual mode → do nothing more
    if conversation.mode == ConversationMode.MANUAL:
        return

    # 4. Accumulate message in queue
    _message_queues.setdefault(sender_id, []).append(text)

    # 5. Cancel any existing pending timer for this sender
    pending_task = _pending_tasks.get(sender_id)
    if pending_task and not pending_task.done():
        pending_task.cancel()

    # 6. Start a fresh debounce timer
    debounce_secs = get_settings().response_debounce_seconds
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
    logger.info("Message recu [%s] : «%s»", sender_id, combined_message[:120])

    # Call AI — exclure les messages du batch courant de l'historique (ils sont déjà
    # dans combined_message, les inclure aussi dans history les doublerait)
    history = _build_history(db, conversation_id, limit=50, exclude_last=len(messages))
    ai_result = await ollama_service.generate_response(combined_message, history)

    # Handle needs_human — passe en MANUAL silencieusement (aucun message envoyé)
    if ai_result.needs_human:
        conversation.mode = ConversationMode.MANUAL
        db.commit()
        # On logue uniquement l'événement interne (dashboard), pas de message envoyé à la cliente
        _log_message(
            db, conversation_id, MessageDirection.OUTBOUND,
            ai_result.response or "[basculé en manuel — IA incertaine]",
            needs_human=True,
        )
        logger.warning(
            "ALERTE — IA incertaine pour %s (conversation id=%d) — basculée en MANUEL (aucun msg envoyé). "
            "Pour remettre en AUTO : PATCH /api/conversations/%d/mode  {\"mode\": \"auto\"}\n"
            "Messages reçus : «%s»",
            sender_id, conversation.id, conversation.id, combined_message,
        )
        return  # La vraie coiffeuse reprend la main, le client ne voit rien

    # Create iCloud appointment + send reply
    if ai_result.book is not None:
        # Injecte le sender_id comme identifiant Instagram (connu côté webhook, pas côté IA)
        ai_result.book.instagram_user = sender_id

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
    # Imports différés pour éviter les imports circulaires au niveau du module
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

            # Titre clair : "Retwist — Julie (@julie.insta)"
            name_parts = []
            if booking.first_name:
                name_parts.append(booking.first_name)
            if booking.instagram_user:
                name_parts.append(f"(@{booking.instagram_user})")
            client_label = " ".join(name_parts) if name_parts else "cliente Instagram"
            event_summary = f"{booking.service} — {client_label}"

            # Description : notes + identité
            desc_lines = []
            if booking.first_name:
                desc_lines.append(f"Prénom : {booking.first_name}")
            if booking.instagram_user:
                desc_lines.append(f"Instagram : @{booking.instagram_user}")
            if booking.notes:
                desc_lines.append(f"Notes : {booking.notes}")
            desc_lines.append("RDV posé via Kyana IA")
            description = "\n".join(desc_lines)

            cal.create_event(
                summary=event_summary,
                start=start_dt,
                end=end_dt,
                description=description,
                test_event=False,
            )
            logger.info(
                "RDV créé dans iCloud : %s le %s à %sh%02d",
                event_summary, booking.date, booking.hour, booking.minute,
            )
        except Exception as e:
            logger.error("Impossible de créer le RDV dans iCloud : %s", e)

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
    limit: int = 10,
    exclude_last: int = 0,
) -> list[dict[str, str]]:
    """Build Ollama-compatible history from the last *limit* messages.

    ``exclude_last`` messages are fetched but discarded from the tail — used to
    strip the current debounce batch (already in ``combined_message``) from the
    history so it doesn't appear twice in the Ollama context.
    """
    fetch_count = limit + exclude_last
    messages = (
        db.query(MessageLog)
        .filter(MessageLog.conversation_id == conversation_id)
        .order_by(MessageLog.created_at.desc())
        .limit(fetch_count)
        .all()
    )
    messages.reverse()

    if exclude_last:
        messages = messages[:-exclude_last] if len(messages) > exclude_last else []

    history: list[dict[str, str]] = []
    for msg in messages:
        role = "user" if msg.direction == MessageDirection.INBOUND else "assistant"
        history.append({"role": role, "content": msg.content})
    return history
