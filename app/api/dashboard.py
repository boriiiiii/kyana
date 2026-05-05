"""
Dashboard API routes — conversation management for the future Next.js frontend.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.conversation import (
    ConversationMode,
    ConversationState,
    MessageLog,
)
from app.models.database import get_db
from app.models.schemas import (
    ConversationModeUpdate,
    ConversationOut,
    DashboardStats,
    MessageOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])


# ─── GET /api/stats ──────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)) -> DashboardStats:
    """Return high‑level stats for the dashboard."""
    total = db.query(func.count(ConversationState.id)).scalar() or 0
    auto = (
        db.query(func.count(ConversationState.id))
        .filter(ConversationState.mode == ConversationMode.AUTO)
        .scalar()
        or 0
    )
    manual = (
        db.query(func.count(ConversationState.id))
        .filter(ConversationState.mode == ConversationMode.MANUAL)
        .scalar()
        or 0
    )
    messages = db.query(func.count(MessageLog.id)).scalar() or 0
    needs_human_count = (
        db.query(func.count(MessageLog.id))
        .filter(MessageLog.needs_human.is_(True))
        .scalar()
        or 0
    )
    return DashboardStats(
        total_conversations=total,
        auto_conversations=auto,
        manual_conversations=manual,
        total_messages=messages,
        needs_human_count=needs_human_count,
    )


# ─── GET /api/conversations ─────────────────────────────

@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
) -> list[ConversationOut]:
    """List all conversations, newest first, with a preview of the last message."""
    conversations = (
        db.query(ConversationState)
        .order_by(ConversationState.last_message_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    results: list[ConversationOut] = []
    for conv in conversations:
        last_msg = (
            db.query(MessageLog)
            .filter(MessageLog.conversation_id == conv.id)
            .order_by(MessageLog.created_at.desc())
            .first()
        )
        preview = last_msg.content[:80] if last_msg else None
        results.append(
            ConversationOut(
                id=conv.id,
                sender_id=conv.sender_id,
                mode=conv.mode.value,
                last_message_at=conv.last_message_at,
                created_at=conv.created_at,
                last_message_preview=preview,
            )
        )
    return results


# ─── GET /api/conversations/{id}/messages ────────────────

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> list[MessageOut]:
    """Return message history for a given conversation."""
    conv = db.query(ConversationState).get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(MessageLog)
        .filter(MessageLog.conversation_id == conversation_id)
        .order_by(MessageLog.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [MessageOut.model_validate(m) for m in messages]


# ─── PATCH /api/conversations/by-sender/{sender_id}/mode ─

@router.patch(
    "/conversations/by-sender/{sender_id}/mode",
    response_model=ConversationOut,
)
def update_conversation_mode_by_sender(
    sender_id: str,
    payload: ConversationModeUpdate,
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Toggle mode by Instagram sender_id (the ID visible in logs)."""
    conv = (
        db.query(ConversationState)
        .filter(ConversationState.sender_id == sender_id)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.mode = ConversationMode(payload.mode.value)
    db.commit()
    db.refresh(conv)
    logger.info("Conversation %s switched to %s", sender_id, conv.mode.value)
    return ConversationOut.model_validate(conv)


# ─── PATCH /api/conversations/{id}/mode ──────────────────

@router.patch(
    "/conversations/{conversation_id}/mode",
    response_model=ConversationOut,
)
def update_conversation_mode(
    conversation_id: int,
    payload: ConversationModeUpdate,
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Toggle a conversation between AUTO and MANUAL mode."""
    conv = db.query(ConversationState).get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.mode = ConversationMode(payload.mode.value)
    db.commit()
    db.refresh(conv)
    logger.info(
        "Conversation %s switched to %s", conversation_id, conv.mode.value
    )
    return ConversationOut.model_validate(conv)
