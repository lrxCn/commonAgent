"""Compatibility adapter tests for graph.turn_type.classify_turn_type()."""

from __future__ import annotations

from gateway.schemas import ToolSpec
from graph.turn_type import TurnType, classify_turn_type
from intent.engine import classify_intent, turn_type_decision_from_intent


def _jump_tool() -> ToolSpec:
    return ToolSpec(name="jumpPage", description="Navigate to a frontend page.")


def _expected(message: str, *, tools: list[ToolSpec] | None = None) -> tuple[TurnType, str]:
    intent = classify_intent(message, tools_context=tools)
    derived = turn_type_decision_from_intent(intent)
    return derived.turn_type, derived.reason


def test_adapter_matches_intent_authority_for_fact_update() -> None:
    decision = classify_turn_type("我公司在天翔街188号")
    expected_type, expected_reason = _expected("我公司在天翔街188号")

    assert decision.turn_type is expected_type is TurnType.FACT_UPDATE
    assert decision.reason == expected_reason


def test_first_person_job_question_is_memory_query_not_fact_update() -> None:
    decision = classify_turn_type("我是做什么的")
    expected_type, expected_reason = _expected("我是做什么的")

    assert decision.turn_type is expected_type is TurnType.MEMORY_QUERY
    assert decision.reason == expected_reason


def test_adapter_matches_intent_authority_for_chitchat() -> None:
    decision = classify_turn_type("谢谢")
    expected_type, expected_reason = _expected("谢谢")

    assert decision.turn_type is expected_type is TurnType.CHITCHAT
    assert decision.reason == expected_reason


def test_adapter_matches_intent_authority_for_knowledge_query() -> None:
    decision = classify_turn_type("报销制度是什么？")
    expected_type, expected_reason = _expected("报销制度是什么？")

    assert decision.turn_type is expected_type is TurnType.KNOWLEDGE_QUERY
    assert decision.reason == expected_reason


def test_adapter_matches_intent_authority_for_client_action() -> None:
    tools = [_jump_tool()]
    decision = classify_turn_type("打开 pageA", tools_context=tools)
    expected_type, expected_reason = _expected("打开 pageA", tools=tools)

    assert decision.turn_type is expected_type is TurnType.CLIENT_ACTION
    assert decision.reason == expected_reason


def test_adapter_matches_intent_authority_when_tool_unavailable() -> None:
    decision = classify_turn_type("打开 pageA", tools_context=[])
    expected_type, expected_reason = _expected("打开 pageA", tools=[])

    assert decision.turn_type is expected_type
    assert decision.reason == expected_reason


def test_adapter_matches_intent_authority_for_ambiguous_reference() -> None:
    decision = classify_turn_type("它需要什么材料")
    expected_type, expected_reason = _expected("它需要什么材料")

    assert decision.turn_type is expected_type is TurnType.AMBIGUOUS
    assert decision.reason == expected_reason


def test_adapter_matches_intent_authority_for_general_chat() -> None:
    decision = classify_turn_type("帮我写一段周会开场白")
    expected_type, expected_reason = _expected("帮我写一段周会开场白")

    assert decision.turn_type is expected_type is TurnType.GENERAL_CHAT
    assert decision.reason == expected_reason


def test_adapter_empty_message_returns_general_chat() -> None:
    decision = classify_turn_type("")

    assert decision.turn_type is TurnType.GENERAL_CHAT
    assert decision.reason == "empty"
