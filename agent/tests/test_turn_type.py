"""Tests for unified turn type classification."""

from __future__ import annotations

from gateway.schemas import ToolSpec
from graph.turn_type import TurnType, classify_turn_type


def _jump_tool() -> ToolSpec:
    return ToolSpec(name="jumpPage", description="Navigate to a frontend page.")


def test_classifies_fact_update() -> None:
    decision = classify_turn_type("我公司在天翔街188号")

    assert decision.turn_type is TurnType.FACT_UPDATE
    assert decision.reason == "fact_statement_rule"


def test_legacy_turn_type_can_misclassify_fact_like_question() -> None:
    decision = classify_turn_type("我是做什么的")

    assert decision.turn_type is TurnType.FACT_UPDATE
    assert decision.reason == "fact_statement_rule"


def test_classifies_chitchat() -> None:
    decision = classify_turn_type("谢谢")

    assert decision.turn_type is TurnType.CHITCHAT
    assert decision.reason == "chitchat_rule"


def test_classifies_knowledge_query() -> None:
    decision = classify_turn_type("报销制度是什么？")

    assert decision.turn_type is TurnType.KNOWLEDGE_QUERY
    assert decision.reason == "knowledge_intent_rule"


def test_classifies_client_action_when_tool_available() -> None:
    decision = classify_turn_type("打开 pageA", tools_context=[_jump_tool()])

    assert decision.turn_type is TurnType.CLIENT_ACTION
    assert decision.reason == "client_action_rule"


def test_client_action_without_tool_falls_back_to_general_chat() -> None:
    decision = classify_turn_type("打开 pageA", tools_context=[])

    assert decision.turn_type is TurnType.GENERAL_CHAT
    assert decision.reason == "default_general_chat"


def test_classifies_ambiguous_reference() -> None:
    decision = classify_turn_type("它需要什么材料")

    assert decision.turn_type is TurnType.AMBIGUOUS
    assert decision.reason == "anaphora_or_continuation_rule"


def test_classifies_general_chat() -> None:
    decision = classify_turn_type("帮我写一段周会开场白")

    assert decision.turn_type is TurnType.GENERAL_CHAT
    assert decision.reason == "default_general_chat"
