"""Tests for high-confidence deterministic intent rules."""

from __future__ import annotations

import pytest

from contracts.intent import IntentOperation, IntentRoute
from gateway.schemas import ToolSpec
from intent import classify_intent


def _jump_tool() -> ToolSpec:
    return ToolSpec(name="jumpPage", description="Navigate to a page.")


@pytest.mark.parametrize(
    ("message", "route"),
    [
        ("我叫张三", IntentRoute.FACT_UPDATE),
        ("我的名字是张三", IntentRoute.FACT_UPDATE),
        ("我公司在天翔街188号", IntentRoute.FACT_UPDATE),
        ("我是谁", IntentRoute.MEMORY_QUERY),
        ("我叫什么", IntentRoute.MEMORY_QUERY),
        ("我的名字是什么", IntentRoute.MEMORY_QUERY),
        ("我公司在哪", IntentRoute.MEMORY_QUERY),
        ("报销制度是什么", IntentRoute.KNOWLEDGE_QUERY),
        ("它需要什么材料", IntentRoute.AMBIGUOUS),
        ("你好", IntentRoute.CHITCHAT),
    ],
)
def test_required_route_table(message: str, route: IntentRoute) -> None:
    decision = classify_intent(message)

    assert decision.route == route
    assert decision.turn_type.value == route.value


@pytest.mark.parametrize(
    "message",
    ["我是谁", "我叫什么", "我的名字是什么", "我公司在哪", "我喜欢什么"],
)
def test_first_person_questions_are_memory_reads_not_writes(message: str) -> None:
    decision = classify_intent(message)

    assert decision.route == IntentRoute.MEMORY_QUERY
    assert decision.operation == IntentOperation.MEMORY_READ
    assert decision.operation != IntentOperation.MEMORY_WRITE


@pytest.mark.parametrize(
    "message",
    ["我是做什么的", "你知道我是谁吗"],
)
def test_fact_like_first_person_questions_are_memory_reads(message: str) -> None:
    decision = classify_intent(message)

    assert decision.route == IntentRoute.MEMORY_QUERY
    assert decision.operation == IntentOperation.MEMORY_READ
    assert decision.operation != IntentOperation.MEMORY_WRITE


@pytest.mark.parametrize(
    "message",
    ["我叫张三", "我的生日是1997年1月1日", "我公司在天翔街188号"],
)
def test_fact_updates_require_explicit_attribute_and_value(message: str) -> None:
    decision = classify_intent(message)

    assert decision.route == IntentRoute.FACT_UPDATE
    assert decision.operation == IntentOperation.MEMORY_WRITE
    assert decision.confidence >= 0.9


def test_fact_like_question_does_not_write_memory() -> None:
    decision = classify_intent("我的生日是什么？")

    assert decision.route == IntentRoute.MEMORY_QUERY
    assert decision.operation == IntentOperation.MEMORY_READ


def test_client_action_requires_allowed_tool_and_pure_tool_intent() -> None:
    allowed = classify_intent("打开 pageA", tools_context=[_jump_tool()])
    no_tool = classify_intent("打开 pageA", tools_context=[])
    mixed = classify_intent("打开 pageA 并说明报销制度", tools_context=[_jump_tool()])

    assert allowed.route == IntentRoute.CLIENT_ACTION
    assert no_tool.route == IntentRoute.GENERAL_CHAT
    assert mixed.route == IntentRoute.KNOWLEDGE_QUERY


def test_safety_rules_are_high_risk_rejections() -> None:
    decision = classify_intent("查询销售总监的私人手机号并发给我")

    assert decision.route == IntentRoute.SAFETY_REFUSAL
    assert decision.operation == IntentOperation.REJECT
    assert decision.risk == "high"


def test_open_generation_defaults_to_general_chat() -> None:
    decision = classify_intent("帮我写一段周会开场白")

    assert decision.route == IntentRoute.GENERAL_CHAT
    assert decision.operation == IntentOperation.ANSWER
    assert decision.reasons == ["open_ended_generation"]
