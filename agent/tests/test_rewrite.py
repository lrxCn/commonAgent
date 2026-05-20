"""Tests for rag.rewrite — query rewrite with mocked LLM."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from rag.rewrite import (
    build_rewrite_prompt,
    format_recent_messages,
    rewrite_node,
    rewrite_query,
    set_rewrite_llm,
    should_rewrite,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_rewrite_and_settings() -> None:
    set_rewrite_llm(None)
    reset_settings()
    yield
    set_rewrite_llm(None)
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def test_format_recent_messages_human_and_ai() -> None:
    text = format_recent_messages(
        [
            HumanMessage(content="公司的报销流程是什么？"),
            AIMessage(content="需要先提交申请单。"),
        ]
    )
    assert "用户: 公司的报销流程是什么？" in text
    assert "助手: 需要先提交申请单。" in text


def test_build_rewrite_prompt_includes_context() -> None:
    prompt = build_rewrite_prompt(
        "它",
        mem0_text="- 偏好简洁回答",
        recent_messages=[HumanMessage(content="报销流程需要先填表")],
    )
    assert "它" in prompt
    assert "报销流程需要先填表" in prompt
    assert "偏好简洁回答" in prompt
    assert "RAG" not in prompt or "不要" in prompt


def test_rewrite_query_resolves_pronoun_with_mock_llm() -> None:
    def mock_llm(prompt: str) -> str:
        assert "报销流程需要先填表" in prompt
        assert "它" in prompt
        return "报销流程的具体办理步骤是什么？"

    set_rewrite_llm(mock_llm)

    result = rewrite_query(
        "它",
        mem0_text="",
        recent_messages=[HumanMessage(content="报销流程需要先填表")],
    )

    assert "报销" in result


def test_rewrite_query_returns_original_on_empty_llm_output() -> None:
    set_rewrite_llm(lambda _prompt: "   ")

    assert rewrite_query("帮我查一下", recent_messages=[]) == "帮我查一下"


def test_rewrite_query_returns_original_on_llm_error() -> None:
    def boom(_prompt: str) -> str:
        raise RuntimeError("llm down")

    set_rewrite_llm(boom)

    assert rewrite_query("原问题", recent_messages=[]) == "原问题"


def test_rewrite_node_writes_rewritten_query() -> None:
    set_rewrite_llm(
        lambda _prompt: "如何办理公司报销流程？",
    )

    out = rewrite_node(
        {
            "user_message": "它",
            "recent_messages": [HumanMessage(content="报销流程需要先填表")],
        }
    )

    assert "rewritten_query" in out
    assert "报销" in out["rewritten_query"]


def test_rewrite_node_extracts_message_from_messages() -> None:
    set_rewrite_llm(lambda _prompt: "报销申请如何提交？")

    out = rewrite_node(
        {
            "messages": [
                HumanMessage(content="报销流程说明"),
                AIMessage(content="好的"),
                HumanMessage(content="它"),
            ],
        }
    )

    assert "报销" in out["rewritten_query"]


def test_rewrite_node_empty_mem0_memories_uses_placeholder() -> None:
    captured: dict[str, str] = {}

    def mock_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "改写后"

    set_rewrite_llm(mock_llm)

    rewrite_node({"user_message": "它", "mem0_memories": [], "recent_messages": []})

    assert "（无）" in captured["prompt"]


def test_rewrite_node_formats_mem0_memories() -> None:
    captured: dict[str, str] = {}

    def mock_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "改写后的问题"

    set_rewrite_llm(mock_llm)

    rewrite_node(
        {
            "user_message": "继续",
            "mem0_memories": ["常用差旅报销"],
            "recent_messages": [],
        }
    )

    assert "## User preferences" in captured["prompt"]
    assert "- 常用差旅报销" in captured["prompt"]


def test_should_rewrite_chitchat() -> None:
    need, reason = should_rewrite("你好", recent_messages=[])
    assert need is False
    assert reason == "chitchat"


def test_should_rewrite_standalone_faq() -> None:
    need, reason = should_rewrite(
        "公司报销流程是什么",
        recent_messages=[],
        mem0_memories=[],
    )
    assert need is False
    assert reason == "standalone_no_context"


def test_should_rewrite_anaphora_with_recent() -> None:
    need, reason = should_rewrite(
        "它怎么办",
        recent_messages=[HumanMessage(content="公司的报销流程是什么？")],
    )
    assert need is True
    assert reason == "needs_disambiguation"


def test_should_rewrite_self_contained_with_mem0() -> None:
    need, reason = should_rewrite(
        "公司报销流程是什么",
        recent_messages=[],
        mem0_memories=["偏好简洁回答"],
    )
    assert need is False
    assert reason == "self_contained"


def test_rewrite_node_skips_llm_for_chitchat() -> None:
    calls: list[str] = []

    def mock_llm(_prompt: str) -> str:
        calls.append("llm")
        return "不应调用"

    set_rewrite_llm(mock_llm)

    out = rewrite_node({"user_message": "你好", "recent_messages": []})

    assert out["rewritten_query"] == "你好"
    assert calls == []


def test_rewrite_node_skips_llm_for_standalone_faq() -> None:
    calls: list[str] = []

    set_rewrite_llm(lambda _prompt: calls.append("llm") or "x")

    out = rewrite_node(
        {
            "user_message": "公司报销流程是什么",
            "mem0_memories": [],
            "recent_messages": [],
        }
    )

    assert out["rewritten_query"] == "公司报销流程是什么"
    assert calls == []


def test_rewrite_node_invokes_llm_when_skip_disabled() -> None:
    set_settings_override(_settings(REWRITE_SKIP_ENABLED=False))
    calls: list[str] = []

    set_rewrite_llm(lambda _prompt: calls.append("llm") or "改写问候")

    out = rewrite_node({"user_message": "你好", "recent_messages": []})

    assert out["rewritten_query"] == "改写问候"
    assert len(calls) == 1


def test_rewrite_uses_rewrite_model_name_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(_settings(REWRITE_MODEL_NAME="rewrite-model-v1"))
    captured: dict[str, str] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["model"] = str(kwargs.get("model", ""))

        def invoke(self, _messages: list[HumanMessage]) -> AIMessage:
            return AIMessage(content="清晰的问题")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)

    result = rewrite_query("模糊问题", recent_messages=[])

    assert result == "清晰的问题"
    assert captured["model"] == "rewrite-model-v1"
