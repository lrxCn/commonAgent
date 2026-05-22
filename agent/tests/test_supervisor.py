"""Supervisor prompt budgeting tests."""

from __future__ import annotations

import pytest

from contracts.llm import ModelUseCase
from gateway.schemas import ToolSpec
from graph.supervisor import (
    build_supervisor_agent,
    format_external_tools_for_prompt,
    invoke_answer_executor,
    reset_stream_token_sink,
    reset_supervisor_overrides,
    set_stream_token_sink,
)
from infrastructure.llm.gateway import get_llm_gateway
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _reset_settings_override() -> None:
    reset_supervisor_overrides()
    reset_settings()
    yield
    reset_supervisor_overrides()
    reset_settings()


def test_format_external_tools_for_prompt_caps_schema_budget() -> None:
    set_settings_override(
        Settings(  # type: ignore[arg-type]
            **_REQUIRED_ENV,
            TOOLS_SCHEMA_MAX_CHARS=180,
            _env_file=None,
        )
    )
    tool = ToolSpec(
        name="createApproval",
        description="Create a workflow approval.",
        parameters={
            "type": "object",
            "properties": {
                f"field_{index}": {"type": "string", "description": "x" * 40}
                for index in range(20)
            },
        },
        requires_approval=True,
    )

    block = format_external_tools_for_prompt([tool])

    assert len(block) <= 180
    assert "createApproval" in block
    assert "parameters schema" in block
    assert "field_19" not in block


def test_supervisor_gateway_policies_for_main_and_rag_answer() -> None:
    settings = Settings(**_REQUIRED_ENV, OPENAI_MODEL_NAME="main-model")  # type: ignore[arg-type]

    main = get_llm_gateway(settings).chat_policy(ModelUseCase.MAIN_ANSWER, streaming=True)
    rag = get_llm_gateway(settings).chat_policy(ModelUseCase.RAG_ANSWER)

    assert main.model_name == "main-model"
    assert main.streaming is True
    assert rag.model_name == "main-model"
    assert rag.streaming is False


def test_answer_executor_uses_rag_answer_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    set_settings_override(Settings(**_REQUIRED_ENV, OPENAI_MODEL_NAME="main-model"))  # type: ignore[arg-type]
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def invoke(self, _messages: list[object]) -> object:
            return type("Response", (), {"content": "answer"})()

    monkeypatch.setattr("infrastructure.llm.clients.ChatOpenAI", FakeChatOpenAI)

    assert invoke_answer_executor("system", []) == "answer"
    assert captured["model"] == "main-model"
    assert "streaming" not in captured


def test_build_supervisor_agent_uses_streaming_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    set_settings_override(Settings(**_REQUIRED_ENV, OPENAI_MODEL_NAME="main-model"))  # type: ignore[arg-type]
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("infrastructure.llm.clients.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("graph.supervisor.create_deep_agent", lambda **kwargs: kwargs)
    token = set_stream_token_sink(lambda _token: None)
    try:
        result = build_supervisor_agent(system_prompt="system")
    finally:
        reset_stream_token_sink(token)

    assert result["model"].__class__.__name__ == "FakeChatOpenAI"
    assert captured["model"] == "main-model"
    assert captured["streaming"] is True
    assert captured["callbacks"]
