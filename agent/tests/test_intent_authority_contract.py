"""IntentDecision -> TurnTypeDecision derived turn contract tests (task 59)."""

from __future__ import annotations

import pytest

from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from contracts.routing import TurnType
from intent.engine import classify_intent, turn_type_decision_from_intent


def _intent_for_route(route: IntentRoute, *, reasons: list[str] | None = None) -> IntentDecision:
    return IntentDecision(
        speech_act=SpeechAct.UNCLEAR,
        domain=IntentDomain.UNKNOWN,
        operation=IntentOperation.CLARIFY,
        route=route,
        confidence=0.5,
        risk=IntentRisk.MEDIUM,
        reasons=reasons or ["test_reason"],
        evidence=["input"],
        needs_clarification=False,
    )


@pytest.mark.parametrize(
    ("route", "turn_type"),
    [
        (IntentRoute.FACT_UPDATE, TurnType.FACT_UPDATE),
        (IntentRoute.MEMORY_QUERY, TurnType.MEMORY_QUERY),
        (IntentRoute.KNOWLEDGE_QUERY, TurnType.KNOWLEDGE_QUERY),
        (IntentRoute.CLIENT_ACTION, TurnType.CLIENT_ACTION),
        (IntentRoute.CHITCHAT, TurnType.CHITCHAT),
        (IntentRoute.AMBIGUOUS, TurnType.AMBIGUOUS),
        (IntentRoute.GENERAL_CHAT, TurnType.GENERAL_CHAT),
        (IntentRoute.SAFETY_REFUSAL, TurnType.SAFETY_REFUSAL),
    ],
)
def test_turn_type_decision_from_intent_maps_all_routes(
    route: IntentRoute,
    turn_type: TurnType,
) -> None:
    intent = _intent_for_route(route, reasons=["route_reason"])
    derived = turn_type_decision_from_intent(intent)

    assert derived.turn_type is turn_type
    assert derived.reason == "route_reason"


def test_turn_type_decision_from_intent_copies_turn_type_properties_only() -> None:
    intent = IntentDecision(
        speech_act=SpeechAct.QUESTION,
        domain=IntentDomain.USER_MEMORY,
        operation=IntentOperation.MEMORY_READ,
        route=IntentRoute.MEMORY_QUERY,
        confidence=0.94,
        risk=IntentRisk.LOW,
        reasons=["first_person_question", "ignored_secondary_reason"],
        evidence=["我是谁"],
    )

    derived = turn_type_decision_from_intent(intent)

    assert derived.turn_type == intent.turn_type
    assert derived.reason == intent.turn_type_reason
    assert derived.reason == "first_person_question"


def test_turn_type_decision_from_intent_uses_default_reason_when_empty() -> None:
    intent = IntentDecision(
        speech_act=SpeechAct.CHITCHAT,
        domain=IntentDomain.OPEN_CHAT,
        operation=IntentOperation.ANSWER,
        route=IntentRoute.CHITCHAT,
        confidence=0.9,
        risk=IntentRisk.LOW,
        reasons=[],
        evidence=["你好"],
    )

    derived = turn_type_decision_from_intent(intent)

    assert derived.turn_type is TurnType.CHITCHAT
    assert derived.reason == "intent_decision"


def test_classify_intent_then_derive_matches_intent_turn_type_fields() -> None:
    intent = classify_intent("我是谁")
    derived = turn_type_decision_from_intent(intent)

    assert derived.turn_type == intent.turn_type
    assert derived.reason == intent.turn_type_reason
    assert derived.turn_type is TurnType.MEMORY_QUERY
