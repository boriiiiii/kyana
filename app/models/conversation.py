"""
SQLAlchemy ORM models — ConversationState and MessageLog.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ConversationMode(str, enum.Enum):
    """Whether the conversation is handled by AI or by a human."""

    AUTO = "auto"
    MANUAL = "manual"


class MessageDirection(str, enum.Enum):
    """Direction of a message relative to the bot."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ConversationState(Base):
    """Tracks the current state (auto / manual) for each Instagram sender."""

    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    mode: Mapped[ConversationMode] = mapped_column(
        Enum(ConversationMode),
        default=ConversationMode.AUTO,
        nullable=False,
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    messages: Mapped[list["MessageLog"]] = relationship(
        "MessageLog", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ConversationState sender={self.sender_id!r} mode={self.mode.value}>"


class MessageLog(Base):
    """Stores every message exchanged in a conversation."""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation_states.id"), nullable=False
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    conversation: Mapped["ConversationState"] = relationship(
        "ConversationState", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<MessageLog dir={self.direction.value} needs_human={self.needs_human}>"
