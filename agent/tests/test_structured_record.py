"""Tests for deterministic structured memory slot fill."""

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
from contracts.memory_write import ExtractionMethod, MemorySubject
from intent.engine import classify_intent
from intent.signals import extract_signals
from memory.profile import normalize_memory_profile
from memory.structured_record import build_structured_memory_record, canonical_fact_text


def _fact_update_decision(*, confidence: float = 0.94) -> IntentDecision:
    return IntentDecision(
        speech_act=SpeechAct.STATEMENT,
        domain=IntentDomain.USER_MEMORY,
        operation=IntentOperation.MEMORY_WRITE,
        route=IntentRoute.FACT_UPDATE,
        confidence=confidence,
        risk=IntentRisk.LOW,
        reasons=["first_person_fact_statement", "explicit_name_value"],
        evidence=["我叫张三"],
        needs_clarification=False,
    )


@pytest.mark.parametrize(
    ("message", "expected_subject", "expected_attribute", "expected_value"),
    [
        ("我叫张三", MemorySubject.USER, "name", "张三"),
        ("我出生于1997年", MemorySubject.USER, "birthday", "1997"),
        ("我生活在哈尔滨", MemorySubject.USER, "city", "哈尔滨"),
        ("我公司在天翔街188号", MemorySubject.ORG, "company.address", "天翔街188号"),
        ("我喜欢简短回答", MemorySubject.USER, "preference", "简短回答"),
        ("我的职业是软件工程师", MemorySubject.USER, "job", "软件工程师"),
    ],
)
def test_slot_fill_maps_prd_first_batch_examples(
    message: str,
    expected_subject: MemorySubject,
    expected_attribute: str,
    expected_value: str,
) -> None:
    signals = extract_signals(message)
    decision = classify_intent(message)
    assert decision.route == IntentRoute.FACT_UPDATE

    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-1:turn-1",
    )

    assert record is not None
    assert record.subject == expected_subject
    assert record.attribute == expected_attribute
    assert record.value == expected_value
    assert record.raw_utterance == message
    assert record.confidence == pytest.approx(decision.confidence)
    assert record.extraction_method == ExtractionMethod.SLOT_FILL_V1.value


@pytest.mark.parametrize(
    ("message", "expected_canonical"),
    [
        ("我叫张三", "用户的名字是张三"),
        ("我出生于1997年", "用户出生于1997年"),
        ("我生活在哈尔滨", "用户生活在哈尔滨"),
        ("我公司在天翔街188号", "公司地址是天翔街188号"),
        ("我喜欢简短回答", "用户喜欢简洁回答"),
        ("我的职业是软件工程师", "用户的职业是软件工程师"),
    ],
)
def test_canonical_fact_text_is_stable_for_profile_normalization(
    message: str,
    expected_canonical: str,
) -> None:
    signals = extract_signals(message)
    decision = classify_intent(message)
    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-1:turn-1",
    )
    assert record is not None

    canonical = canonical_fact_text(record)
    assert canonical == expected_canonical

    normalized = normalize_memory_profile([canonical])
    assert not normalized.profile.is_empty()


def test_city_attribute_wins_over_address_for_user_location() -> None:
    signals = extract_signals("我生活在哈尔滨")
    assert "city" in signals.fact_attributes
    assert "address" in signals.fact_attributes

    record = build_structured_memory_record(
        signals,
        classify_intent("我生活在哈尔滨"),
        source_turn_id="thread-1:turn-2",
    )

    assert record is not None
    assert record.attribute == "city"
    assert record.value == "哈尔滨"


@pytest.mark.parametrize(
    "message",
    [
        "我是谁",
        "我叫什么",
        "我的名字是什么",
        "我",
        "你好",
    ],
)
def test_questions_and_missing_values_return_none(message: str) -> None:
    signals = extract_signals(message)
    decision = classify_intent(message)

    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-1:turn-1",
    )

    assert record is None


def test_non_fact_update_intent_returns_none() -> None:
    signals = extract_signals("我是谁")
    decision = classify_intent("我是谁")
    assert decision.route == IntentRoute.MEMORY_QUERY

    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-1:turn-1",
    )

    assert record is None


def test_missing_explicit_values_returns_none_even_with_attributes() -> None:
    signals = extract_signals("我叫什么")
    decision = _fact_update_decision()

    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-1:turn-1",
    )

    assert record is None


def test_blank_source_turn_id_returns_none() -> None:
    signals = extract_signals("我叫张三")
    decision = classify_intent("我叫张三")

    assert (
        build_structured_memory_record(
            signals,
            decision,
            source_turn_id="   ",
        )
        is None
    )


def test_build_from_classify_intent_matches_memory_write_seed_name_row() -> None:
    message = "我叫张三"
    signals = extract_signals(message)
    decision = classify_intent(message)

    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id="thread-1:turn-1",
    )

    assert record is not None
    assert record.model_dump(mode="json") == {
        "subject": "user",
        "attribute": "name",
        "value": "张三",
        "raw_utterance": message,
        "confidence": decision.confidence,
        "source_turn_id": "thread-1:turn-1",
        "extraction_method": "slot_fill_v1",
    }
