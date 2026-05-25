"""Freeze dual-track intent behavior: legacy turn_type vs IntentDecision.route.

Task 58 establishes the divergence matrix before IntentDecision becomes the sole
authority. Runtime code is unchanged; this file records current legacy output,
target behavior, and which divergences are intentional corrections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from contracts.intent import IntentRoute
from contracts.routing import TurnType
from gateway.schemas import ToolSpec
from graph.turn_type import classify_turn_type
from intent.engine import classify_intent


def _jump_tool() -> ToolSpec:
    return ToolSpec(
        name="jumpPage",
        description="Navigate to an in-app page.",
        parameters={
            "type": "object",
            "properties": {"page": {"type": "string"}},
            "required": ["page"],
        },
        requires_approval=False,
    )


@dataclass(frozen=True)
class DualTrackCase:
    """One row in the turn_type vs IntentDecision divergence matrix."""

    message: str
    target_route: IntentRoute
    target_turn_type: TurnType
    legacy_turn_type: TurnType
    legacy_reason: str
    expected_divergence: bool
    correction_note: str = ""
    tools_context: tuple[ToolSpec, ...] = ()


# Target behavior follows IntentDecision.route (future single authority).
# legacy_* fields freeze current classify_turn_type() output for migration audit.
DUAL_TRACK_MATRIX: tuple[DualTrackCase, ...] = (
    DualTrackCase(
        message="我是谁",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
        legacy_turn_type=TurnType.FACT_UPDATE,
        legacy_reason="fact_statement_rule",
        expected_divergence=True,
        correction_note="第一人称疑问：旧 turn_type 误判 fact_update，目标为 memory_query",
    ),
    DualTrackCase(
        message="我叫什么",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
        legacy_turn_type=TurnType.GENERAL_CHAT,
        legacy_reason="default_general_chat",
        expected_divergence=True,
        correction_note="第一人称疑问：旧 turn_type 未识别记忆读取，目标为 memory_query",
    ),
    DualTrackCase(
        message="我的名字是什么",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
        legacy_turn_type=TurnType.KNOWLEDGE_QUERY,
        legacy_reason="knowledge_intent_rule",
        expected_divergence=True,
        correction_note="第一人称姓名疑问：旧 turn_type 误判 knowledge_query，目标为 memory_query",
    ),
    DualTrackCase(
        message="我公司在哪",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
        legacy_turn_type=TurnType.FACT_UPDATE,
        legacy_reason="fact_statement_rule",
        expected_divergence=True,
        correction_note="第一人称公司位置疑问：旧 turn_type 误判 fact_update，目标为 memory_query",
    ),
    DualTrackCase(
        message="我喜欢什么",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
        legacy_turn_type=TurnType.GENERAL_CHAT,
        legacy_reason="default_general_chat",
        expected_divergence=True,
        correction_note="第一人称偏好疑问：旧 turn_type 未识别记忆读取，目标为 memory_query",
    ),
    DualTrackCase(
        message="我叫张三",
        target_route=IntentRoute.FACT_UPDATE,
        target_turn_type=TurnType.FACT_UPDATE,
        legacy_turn_type=TurnType.FACT_UPDATE,
        legacy_reason="fact_statement_rule",
        expected_divergence=False,
    ),
    DualTrackCase(
        message="我公司在天翔街188号",
        target_route=IntentRoute.FACT_UPDATE,
        target_turn_type=TurnType.FACT_UPDATE,
        legacy_turn_type=TurnType.FACT_UPDATE,
        legacy_reason="fact_statement_rule",
        expected_divergence=False,
    ),
    DualTrackCase(
        message="报销制度是什么",
        target_route=IntentRoute.KNOWLEDGE_QUERY,
        target_turn_type=TurnType.KNOWLEDGE_QUERY,
        legacy_turn_type=TurnType.KNOWLEDGE_QUERY,
        legacy_reason="knowledge_intent_rule",
        expected_divergence=False,
    ),
    DualTrackCase(
        message="打开 pageA",
        target_route=IntentRoute.CLIENT_ACTION,
        target_turn_type=TurnType.CLIENT_ACTION,
        legacy_turn_type=TurnType.CLIENT_ACTION,
        legacy_reason="client_action_rule",
        expected_divergence=False,
        tools_context=(_jump_tool(),),
    ),
    DualTrackCase(
        message="它需要什么材料",
        target_route=IntentRoute.AMBIGUOUS,
        target_turn_type=TurnType.AMBIGUOUS,
        legacy_turn_type=TurnType.AMBIGUOUS,
        legacy_reason="anaphora_or_continuation_rule",
        expected_divergence=False,
    ),
    DualTrackCase(
        message="你好",
        target_route=IntentRoute.CHITCHAT,
        target_turn_type=TurnType.CHITCHAT,
        legacy_turn_type=TurnType.CHITCHAT,
        legacy_reason="chitchat_rule",
        expected_divergence=False,
    ),
)


def _tools(case: DualTrackCase) -> list[ToolSpec] | None:
    if not case.tools_context:
        return None
    return list(case.tools_context)


@pytest.mark.parametrize("case", DUAL_TRACK_MATRIX, ids=lambda case: case.message)
def test_dual_track_matrix_matches_frozen_legacy_and_target(case: DualTrackCase) -> None:
    tools = _tools(case)
    legacy = classify_turn_type(case.message, tools_context=tools)
    intent = classify_intent(case.message, tools_context=tools)

    assert intent.route == case.target_route
    assert intent.turn_type == case.target_turn_type
    assert legacy.turn_type == case.legacy_turn_type
    assert legacy.reason == case.legacy_reason

    diverges = legacy.turn_type.value != intent.route
    assert diverges == case.expected_divergence

    if case.expected_divergence:
        assert legacy.turn_type != case.target_turn_type
        assert case.correction_note


def test_first_person_questions_target_memory_query_not_fact_update() -> None:
    questions = [
        case
        for case in DUAL_TRACK_MATRIX
        if case.target_route == IntentRoute.MEMORY_QUERY
    ]
    assert len(questions) == 5

    for case in questions:
        intent = classify_intent(case.message)
        legacy = classify_turn_type(case.message)

        assert intent.route == IntentRoute.MEMORY_QUERY
        assert intent.turn_type == TurnType.MEMORY_QUERY
        assert legacy.turn_type != TurnType.MEMORY_QUERY


def test_aligned_samples_have_no_divergence() -> None:
    aligned = [case for case in DUAL_TRACK_MATRIX if not case.expected_divergence]
    assert len(aligned) == 6

    for case in aligned:
        tools = _tools(case)
        legacy = classify_turn_type(case.message, tools_context=tools)
        intent = classify_intent(case.message, tools_context=tools)

        assert legacy.turn_type.value == intent.route
        assert legacy.turn_type == case.target_turn_type


def test_matrix_covers_required_task_samples() -> None:
    required = {
        "我是谁",
        "我叫什么",
        "我的名字是什么",
        "我公司在哪",
        "我喜欢什么",
        "我叫张三",
        "我公司在天翔街188号",
        "报销制度是什么",
        "打开 pageA",
        "它需要什么材料",
        "你好",
    }
    covered = {case.message for case in DUAL_TRACK_MATRIX}
    assert required == covered


def test_divergence_summary_for_migration_audit() -> None:
    """Stable audit payload for later tasks comparing authority cutover impact."""

    rows: list[dict[str, Any]] = []
    for case in DUAL_TRACK_MATRIX:
        tools = _tools(case)
        legacy = classify_turn_type(case.message, tools_context=tools)
        intent = classify_intent(case.message, tools_context=tools)
        rows.append(
            {
                "input": case.message,
                "legacy_turn_type": legacy.turn_type.value,
                "legacy_reason": legacy.reason,
                "intent_route": intent.route,
                "target_route": case.target_route.value,
                "target_turn_type": case.target_turn_type.value,
                "diverges": legacy.turn_type.value != intent.route,
                "expected_divergence": case.expected_divergence,
                "correction_note": case.correction_note,
            }
        )

    divergent = [row for row in rows if row["diverges"]]
    assert len(divergent) == 5
    assert {row["input"] for row in divergent} == {
        "我是谁",
        "我叫什么",
        "我的名字是什么",
        "我公司在哪",
        "我喜欢什么",
    }
    for row in divergent:
        assert row["target_route"] == "memory_query"
        assert row["legacy_turn_type"] != "memory_query"
