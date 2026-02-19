"""
Pydantic schemas — request / response models for the API layer.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ─── AI Response ──────────────────────────────────────────

class AIResponse(BaseModel):
    """Structured output expected from the LLM (Ollama / Llama 3.1)."""

    response: str = Field(..., description="The AI-generated reply text")
    needs_human: bool = Field(
        False,
        description="True when the AI is unsure and a human should take over",
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
