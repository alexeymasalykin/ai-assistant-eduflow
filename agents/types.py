from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MessageType(str, Enum):
    """Classification of incoming messages."""

    TYPICAL = "typical"
    COURSE = "course"
    PLATFORM = "platform"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class AgentResponse:
    """Response from any agent in the system."""

    text: str
    agent_type: MessageType = MessageType.TYPICAL
    should_send: bool = True

    @classmethod
    def silent(cls) -> AgentResponse:
        """No response needed (confirmations like 'ok', 'thanks')."""
        return cls(text="", should_send=False)

    @classmethod
    def escalate(cls) -> AgentResponse:
        """Escalate to human manager."""
        return cls(text="", agent_type=MessageType.ESCALATE, should_send=False)
