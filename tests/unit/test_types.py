from __future__ import annotations

from agents.types import AgentResponse, MessageType


class TestMessageType:
    def test_all_types_exist(self) -> None:
        assert MessageType.TYPICAL is not None
        assert MessageType.COURSE is not None
        assert MessageType.PLATFORM is not None
        assert MessageType.ESCALATE is not None

    def test_values_are_lowercase(self) -> None:
        assert MessageType.TYPICAL.value == "typical"
        assert MessageType.COURSE.value == "course"
        assert MessageType.PLATFORM.value == "platform"
        assert MessageType.ESCALATE.value == "escalate"


class TestAgentResponse:
    def test_create_with_text(self) -> None:
        response = AgentResponse(text="Hello", agent_type=MessageType.TYPICAL)
        assert response.text == "Hello"
        assert response.agent_type == MessageType.TYPICAL
        assert response.should_send is True

    def test_create_silent(self) -> None:
        response = AgentResponse.silent()
        assert response.text == ""
        assert response.should_send is False

    def test_create_escalate(self) -> None:
        response = AgentResponse.escalate()
        assert response.agent_type == MessageType.ESCALATE
        assert response.should_send is False
