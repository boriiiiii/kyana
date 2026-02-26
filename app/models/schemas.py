"""
Pydantic schemas — request / response models for the API layer.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ─── AI Response ──────────────────────────────────────────

class BookingRequest(BaseModel):
    """Données de réservation retournées par l'IA quand elle crée un RDV."""

    service: str = Field(..., description="Nom de la prestation (ex: 'Retwist')")
    date: str = Field(..., description="Date au format YYYY-MM-DD")
    hour: int = Field(..., ge=0, le=23, description="Heure de début (0-23)")
    minute: int = Field(0, ge=0, le=59, description="Minute de début (0-59)")
    duration_minutes: int = Field(60, ge=15, le=480, description="Durée en minutes")


class AIResponse(BaseModel):
    """Structured output expected from the LLM (Ollama / Llama 3.1)."""

    response: str = Field(..., description="The AI-generated reply text")
    needs_human: bool = Field(
        False,
        description="True uniquement pour insulte/réclamation grave — jamais pour un RDV",
    )
    book: BookingRequest | None = Field(
        None,
        description="Si l'IA veut poser un RDV, renseigne ce champ",
    )


# ─── Conversations ───────────────────────────────────────

class ConversationModeEnum(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class ConversationOut(BaseModel):
    """Public representation of a conversation (for dashboard)."""

    id: int
    sender_id: str
    mode: ConversationModeEnum
    last_message_at: datetime
    created_at: datetime
    last_message_preview: str | None = None

    model_config = {"from_attributes": True}


class ConversationModeUpdate(BaseModel):
    """Payload to toggle conversation mode."""

    mode: ConversationModeEnum


# ─── Messages ────────────────────────────────────────────

class MessageDirectionEnum(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageOut(BaseModel):
    """Public representation of a logged message."""

    id: int
    conversation_id: int
    direction: MessageDirectionEnum
    content: str
    needs_human: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Webhook ─────────────────────────────────────────────

class WebhookVerification(BaseModel):
    """Query params for Meta webhook verification challenge."""

    hub_mode: str = Field(..., alias="hub.mode")
    hub_verify_token: str = Field(..., alias="hub.verify_token")
    hub_challenge: str = Field(..., alias="hub.challenge")


# ─── Dashboard ───────────────────────────────────────────

class DashboardStats(BaseModel):
    """High-level stats for the dashboard."""

    total_conversations: int = 0
    auto_conversations: int = 0
    manual_conversations: int = 0
    total_messages: int = 0
    needs_human_count: int = 0
