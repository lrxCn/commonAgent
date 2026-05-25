"""Intent authority alignment: legacy adapter vs IntentDecision.route.

Task 58 froze the pre-cutover dual-track matrix. After task 61,
``classify_turn_type()`` delegates to the same intent authority as the graph.
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
class AuthorityCase:
    """One row in the intent authority target matrix."""

    message: str
    target_route: IntentRoute
    target_turn_type: TurnType
    tools_context: tuple[ToolSpec, ...] = ()


AUTHORITY_MATRIX: tuple[AuthorityCase, ...] = (
    AuthorityCase(
        message="我是谁",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
    ),
    AuthorityCase(
        message="我叫什么",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
    ),
    AuthorityCase(
        message="我的名字是什么",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
    ),
    AuthorityCase(
        message="我公司在哪",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
    ),
    AuthorityCase(
        message="我喜欢什么",
        target_route=IntentRoute.MEMORY_QUERY,
        target_turn_type=TurnType.MEMORY_QUERY,
    ),
    AuthorityCase(
        message="我叫张三",
        target_route=IntentRoute.FACT_UPDATE,
        target_turn_type=TurnType.FACT_UPDATE,
    ),
    AuthorityCase(
        message="我公司在天翔街188号",
        target_route=IntentRoute.FACT_UPDATE,
        target_turn_type=TurnType.FACT_UPDATE,
    ),
    AuthorityCase(
        message="报销制度是什么",
        target_route=IntentRoute.KNOWLEDGE_QUERY,
        target_turn_type=TurnType.KNOWLEDGE_QUERY,
    ),
    AuthorityCase(
        message="打开 pageA",
        target_route=IntentRoute.CLIENT_ACTION,
        target_turn_type=TurnType.CLIENT_ACTION,
        tools_context=(_jump_tool(),),
    ),
    AuthorityCase(
        message="它需要什么材料",
        target_route=IntentRoute.AMBIGUOUS,
        target_turn_type=TurnType.AMBIGUOUS,
    ),
    AuthorityCase(
        message="你好",
        target_route=IntentRoute.CHITCHAT,
        target_turn_type=TurnType.CHITCHAT,
    ),
)


def _tools(case: AuthorityCase) -> list[ToolSpec] | None:
    if not case.tools_context:
        return None
    return list(case.tools_context)


@pytest.mark.parametrize("case", AUTHORITY_MATRIX, ids=lambda case: case.message)
def test_adapter_and_intent_share_single_authority(case: AuthorityCase) -> None:
    tools = _tools(case)
    adapter = classify_turn_type(case.message, tools_context=tools)
    intent = classify_intent(case.message, tools_context=tools)

    assert intent.route == case.target_route
    assert intent.turn_type == case.target_turn_type
    assert adapter.turn_type == intent.turn_type
    assert adapter.reason == intent.turn_type_reason


def test_first_person_questions_target_memory_query_not_fact_update() -> None:
    questions = [
        case for case in AUTHORITY_MATRIX if case.target_route == IntentRoute.MEMORY_QUERY
    ]
    assert len(questions) == 5

    for case in questions:
        adapter = classify_turn_type(case.message)
        intent = classify_intent(case.message)

        assert intent.route == IntentRoute.MEMORY_QUERY
        assert intent.turn_type == TurnType.MEMORY_QUERY
        assert adapter.turn_type is TurnType.MEMORY_QUERY


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
    covered = {case.message for case in AUTHORITY_MATRIX}
    assert required == covered


def test_adapter_intent_alignment_summary() -> None:
    """Stable audit payload confirming no dual-track divergence remains."""

    rows: list[dict[str, Any]] = []
    for case in AUTHORITY_MATRIX:
        tools = _tools(case)
        adapter = classify_turn_type(case.message, tools_context=tools)
        intent = classify_intent(case.message, tools_context=tools)
        rows.append(
            {
                "input": case.message,
                "adapter_turn_type": adapter.turn_type.value,
                "adapter_reason": adapter.reason,
                "intent_route": intent.route,
                "target_route": case.target_route.value,
                "target_turn_type": case.target_turn_type.value,
                "diverges": adapter.turn_type.value != intent.route,
            }
        )

    assert all(not row["diverges"] for row in rows)
