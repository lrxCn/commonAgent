"""Smoke tests for local intent eval seed structure."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.intent import IntentDecision, IntentFeedback


_SEED_PATH = Path(__file__).resolve().parents[1] / "evals" / "intent_seed.json"
_REQUIRED_ROUTES = {
    "fact_update",
    "memory_query",
    "knowledge_query",
    "client_action",
    "ambiguous",
    "general_chat",
    "chitchat",
    "safety_refusal",
}
_FIRST_PERSON_MEMORY_QUERIES = {
    "我是谁",
    "我叫什么",
    "我的名字是什么",
    "我公司在哪",
    "我喜欢什么",
}


def _load_seed() -> list[dict]:
    payload = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def test_intent_seed_rows_validate_against_contract() -> None:
    rows = _load_seed()
    ids: set[str] = set()

    for row in rows:
        assert isinstance(row["id"], str) and row["id"]
        assert row["id"] not in ids
        ids.add(row["id"])
        assert isinstance(row["input"], str) and row["input"]
        assert isinstance(row["context"], dict)

        expected = row["expected_intent"]
        expected_with_confidence = {"confidence": 0.9, **expected}
        decision = IntentDecision.model_validate(expected_with_confidence)
        assert decision.route == expected["route"]
        assert decision.turn_type.value == expected["route"]
        assert decision.to_trace_dict()["turn_type_reason"] == expected["reasons"][0]

        if "feedback" in row:
            feedback = row["feedback"]
            IntentFeedback.model_validate(
                {
                    "original_text": row["input"],
                    "predicted_route": feedback["predicted_route"],
                    "corrected_route": feedback.get("corrected_route"),
                    "failure_type": feedback["failure_type"],
                    "trace_id": feedback.get("trace_id"),
                    "thread_id": feedback.get("thread_id"),
                    "user_id": feedback.get("user_id"),
                    "note": feedback.get("note", ""),
                    "source": feedback.get("feedback_source", feedback.get("source", "review")),
                }
            )


def test_intent_seed_has_required_route_coverage() -> None:
    rows = _load_seed()
    covered = {row["expected_intent"]["route"] for row in rows}

    assert _REQUIRED_ROUTES.issubset(covered)


def test_intent_seed_includes_required_fact_update_examples() -> None:
    rows = _load_seed()
    fact_inputs = {
        row["input"]
        for row in rows
        if row["expected_intent"]["route"] == "fact_update"
    }

    assert {"我叫张三", "我的生日是1997年1月1日", "我公司在天翔街188号"}.issubset(fact_inputs)


def test_first_person_questions_are_memory_queries_not_fact_updates() -> None:
    rows = _load_seed()
    by_input = {row["input"]: row for row in rows}

    assert _FIRST_PERSON_MEMORY_QUERIES.issubset(by_input)
    for text in _FIRST_PERSON_MEMORY_QUERIES:
        expected = by_input[text]["expected_intent"]
        assert expected["speech_act"] == "question"
        assert expected["operation"] == "memory_read"
        assert expected["route"] == "memory_query"
        assert expected["route"] != "fact_update"


def test_seed_includes_feedback_regression_for_whoami_fact_update_false_positive() -> None:
    rows = _load_seed()
    feedback_rows = [
        row
        for row in rows
        if row.get("feedback", {}).get("failure_type") == "false_positive_fact_update"
    ]

    assert any(row["input"] == "我是谁" for row in feedback_rows)
    for row in feedback_rows:
        feedback = row["feedback"]
        assert feedback["predicted_route"] == "fact_update"
        assert feedback["corrected_route"] == row["expected_intent"]["route"]


def test_client_action_intent_rows_include_tools_context() -> None:
    rows = _load_seed()
    action_rows = [
        row
        for row in rows
        if row["expected_intent"]["route"] == "client_action"
    ]

    assert len(action_rows) >= 2
    for row in action_rows:
        tools = row["context"]["tools"]
        assert isinstance(tools, list) and tools
        assert tools[0]["name"] == "jumpPage"


def test_safety_refusal_rows_are_high_risk_rejections() -> None:
    rows = _load_seed()
    safety_rows = [
        row
        for row in rows
        if row["expected_intent"]["route"] == "safety_refusal"
    ]

    assert len(safety_rows) >= 2
    for row in safety_rows:
        expected = row["expected_intent"]
        assert expected["speech_act"] == "unsafe"
        assert expected["domain"] == "safety"
        assert expected["operation"] == "reject"
        assert expected["risk"] == "high"
