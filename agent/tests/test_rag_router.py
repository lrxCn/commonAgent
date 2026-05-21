"""Tests for rag.router — rule-first RAG routing."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from gateway.schemas import ToolSpec
from rag.router import (
    RuleDecision,
    build_router_classifier_prompt,
    classify_with_llm,
    classify_with_rules,
    is_pure_client_tool_intent,
    parse_need_rag_json,
    rag_router_node,
    set_router_classifier,
    should_retrieve,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}

_JUMP_TOOLS = [
    ToolSpec(
        name="jumpPage",
        description="Navigate to a page.",
        parameters={
            "type": "object",
            "properties": {"page": {"type": "string"}},
            "required": ["page"],
        },
    )
]


@pytest.fixture(autouse=True)
def _clean_router_and_settings() -> None:
    set_router_classifier(None)
    reset_settings()
    yield
    set_router_classifier(None)
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("message", "rewritten", "tools", "expected"),
    [
        ("你好", None, None, False),
        ("报销制度是什么", None, None, True),
        ("打开 pageA", None, _JUMP_TOOLS, False),
        ("打开 pageA", "跳转到 pageA 页面", _JUMP_TOOLS, False),
        ("报销制度是什么", "公司的报销制度有哪些规定", None, True),
        ("打开 pageA 并说明报销制度", None, _JUMP_TOOLS, True),
        ("我公司在天翔街188号", "我公司在天翔街188号", None, False),
        ("我生活在哈尔滨", "我生活在哈尔滨", None, False),
    ],
)
def test_should_retrieve_rules_mode_table(
    message: str,
    rewritten: str | None,
    tools: list[ToolSpec] | None,
    expected: bool,
) -> None:
    assert should_retrieve(message, rewritten, tools, mode="rules") is expected


def test_classify_with_rules_decisions() -> None:
    assert classify_with_rules("你好") is RuleDecision.SKIP
    assert classify_with_rules("报销制度是什么") is RuleDecision.RETRIEVE
    assert classify_with_rules("打开 pageA", tools_context=_JUMP_TOOLS) is RuleDecision.SKIP
    assert classify_with_rules("我公司在天翔街188号") is RuleDecision.SKIP
    assert classify_with_rules("我生活在哈尔滨") is RuleDecision.SKIP
    assert classify_with_rules("帮我看看") is RuleDecision.UNCERTAIN


@pytest.mark.parametrize(
    "turn_type",
    ["fact_update", "chitchat", "client_action"],
)
def test_classify_with_rules_skips_conclusive_skip_turn_types(turn_type: str) -> None:
    assert (
        classify_with_rules(
            "报销制度是什么",
            rewritten_query="报销制度是什么",
            tools_context=_JUMP_TOOLS,
            turn_type=turn_type,
        )
        is RuleDecision.SKIP
    )


def test_classify_with_rules_retrieves_for_knowledge_query_turn_type() -> None:
    assert (
        classify_with_rules(
            "你好",
            rewritten_query="你好",
            turn_type="knowledge_query",
        )
        is RuleDecision.RETRIEVE
    )


def test_hybrid_skips_llm_for_turn_type_skip_decisions() -> None:
    calls: list[str] = []
    set_router_classifier(lambda _prompt: calls.append("llm") or '{"need_rag": true}')

    for turn_type in ("fact_update", "chitchat", "client_action"):
        result = should_retrieve(
            "报销制度是什么",
            rewritten_query="报销制度是什么",
            tools_context=_JUMP_TOOLS,
            mode="hybrid",
            turn_type=turn_type,
        )
        assert result is False

    assert calls == []


def test_hybrid_retrieves_without_llm_for_knowledge_query_turn_type() -> None:
    calls: list[str] = []
    set_router_classifier(lambda _prompt: calls.append("llm") or '{"need_rag": false}')

    result = should_retrieve(
        "你好",
        rewritten_query="你好",
        mode="hybrid",
        turn_type="knowledge_query",
    )

    assert result is True
    assert calls == []


def test_hybrid_skips_llm_for_user_fact_statement() -> None:
    calls: list[str] = []
    set_router_classifier(lambda _prompt: calls.append("llm") or '{"need_rag": true}')

    result = should_retrieve(
        "我公司在天翔街188号",
        rewritten_query="我公司在天翔街188号",
        mode="hybrid",
    )

    assert result is False
    assert calls == []


def test_hybrid_skips_llm_for_living_city_statement() -> None:
    calls: list[str] = []
    set_router_classifier(lambda _prompt: calls.append("llm") or '{"need_rag": true}')

    result = should_retrieve(
        "我生活在哈尔滨",
        rewritten_query="我生活在哈尔滨",
        mode="hybrid",
    )

    assert result is False
    assert calls == []


def test_parse_need_rag_json() -> None:
    assert parse_need_rag_json('{"need_rag": true}') is True
    assert parse_need_rag_json('{"need_rag": false}') is False
    assert parse_need_rag_json('说明\n{"need_rag": false}') is False
    assert parse_need_rag_json("not json") is None


def test_hybrid_uses_llm_when_rules_uncertain() -> None:
    set_router_classifier(lambda _prompt: '{"need_rag": false}')

    result = should_retrieve("帮我看看", mode="hybrid")

    assert result is False


def test_hybrid_falls_back_to_retrieve_on_classifier_failure() -> None:
    set_router_classifier(lambda _prompt: "invalid")

    assert should_retrieve("帮我看看", mode="hybrid") is True


def test_classify_with_llm_parses_json() -> None:
    set_router_classifier(lambda _prompt: '{"need_rag": false}')

    assert (
        classify_with_llm("随便一句", rewritten_query="随便一句", tools_context=_JUMP_TOOLS)
        is False
    )


def test_rag_router_node_sets_rag_skipped() -> None:
    out = rag_router_node(
        {
            "user_message": "你好",
            "rewritten_query": "你好",
        }
    )
    assert out == {"rag_skipped": True}

    out2 = rag_router_node(
        {
            "message": "报销制度是什么",
            "rewritten_query": "报销制度是什么",
        }
    )
    assert out2 == {"rag_skipped": False}

    out3 = rag_router_node(
        {
            "message": "我公司在天翔街188号",
            "rewritten_query": "我公司在天翔街188号",
        }
    )
    assert out3 == {"rag_skipped": True}


def test_rag_router_node_uses_turn_type_before_legacy_rules() -> None:
    calls: list[str] = []
    set_router_classifier(lambda _prompt: calls.append("llm") or '{"need_rag": false}')

    out = rag_router_node(
        {
            "message": "你好",
            "rewritten_query": "你好",
            "turn_type": "knowledge_query",
        }
    )

    assert out == {"rag_skipped": False}
    assert calls == []


def test_build_router_classifier_prompt_lists_tools() -> None:
    prompt = build_router_classifier_prompt(
        "打开 pageA",
        "跳转到 pageA",
        _JUMP_TOOLS,
    )
    assert "jumpPage" in prompt
    assert "打开 pageA" in prompt


def test_is_pure_client_tool_requires_nav_tool() -> None:
    assert is_pure_client_tool_intent("打开 pageA", _JUMP_TOOLS) is True
    assert is_pure_client_tool_intent("打开 pageA", None) is False


def test_settings_rag_router_mode_validation() -> None:
    with pytest.raises(ValueError, match="RAG_ROUTER_MODE"):
        Settings(**{**_REQUIRED_ENV, "RAG_ROUTER_MODE": "invalid"})  # type: ignore[arg-type]


def test_settings_default_hybrid_mode() -> None:
    settings = _settings()
    assert settings.RAG_ROUTER_MODE == "hybrid"


def test_router_uses_model_limits_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(
        _settings(
            RAG_ROUTER_MODEL_NAME="router-model-v1",
            RAG_ROUTER_MAX_TOKENS=12,
            RAG_ROUTER_TIMEOUT_SECONDS=2.5,
        )
    )
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["model"] = kwargs.get("model")
            captured["max_completion_tokens"] = kwargs.get("max_completion_tokens")
            captured["timeout"] = kwargs.get("timeout")
            captured["max_retries"] = kwargs.get("max_retries")

        def invoke(self, _messages: list[object]) -> AIMessage:
            return AIMessage(content='{"need_rag": false}')

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)

    result = classify_with_llm("帮我看看", rewritten_query="帮我看看")

    assert result is False
    assert captured["model"] == "router-model-v1"
    assert captured["max_completion_tokens"] == 12
    assert captured["timeout"] == 2.5
    assert captured["max_retries"] == 0


def test_classify_with_llm_returns_true_on_exception() -> None:
    def boom(_prompt: str) -> str:
        raise RuntimeError("router down")

    set_router_classifier(boom)

    assert classify_with_llm("帮我看看", rewritten_query="帮我看看") is True
