"""Smoke tests for local memory_query polish eval seed structure."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from memory.query import answer_memory_query

_SEED_PATH = Path(__file__).resolve().parents[1] / "evals" / "memory_query_polish_seed.json"
_REQUIRED_CATEGORIES = {
    "polish_hit_name",
    "polish_hit_company_address",
    "polish_hit_preference",
    "polish_missing_name",
    "polish_missing_profile",
    "polish_thread_fallback",
    "polish_forbidden_fact_tamper",
    "polish_forbidden_uncertainty",
}
_REQUIRED_FIELDS = (
    "input",
    "deterministic_reply",
    "evidence",
    "expected_polish_constraints",
    "forbidden_outputs",
)


def _load_seed() -> list[dict]:
    payload = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def _thread_messages(raw_messages: list[dict]) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for item in raw_messages:
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        else:
            messages.append(AIMessage(content=item["content"]))
    return messages


def test_memory_query_polish_seed_rows_have_required_fields() -> None:
    rows = _load_seed()
    ids: set[str] = set()

    for row in rows:
        assert isinstance(row["id"], str) and row["id"]
        assert row["id"] not in ids
        ids.add(row["id"])
        assert isinstance(row["category"], str) and row["category"]
        assert isinstance(row["context"], dict)
        for field in _REQUIRED_FIELDS:
            assert field in row
        assert isinstance(row["expected_polish_constraints"], list)
        assert row["expected_polish_constraints"]
        assert isinstance(row["forbidden_outputs"], list)
        assert row["forbidden_outputs"]
        assert isinstance(row["evidence"], list)
        assert isinstance(row["missing_reason"], str)


def test_memory_query_polish_seed_has_required_category_coverage() -> None:
    rows = _load_seed()
    covered = {row["category"] for row in rows}

    assert _REQUIRED_CATEGORIES.issubset(covered)


def test_memory_query_polish_seed_deterministic_replies_match_current_behavior() -> None:
    rows = _load_seed()

    for row in rows:
        context = row["context"]
        messages = _thread_messages(context.get("thread_messages", []))
        result = answer_memory_query(
            row["input"],
            user_memories=context.get("user_memories"),
            messages=messages or None,
        )

        assert result.reply == row["deterministic_reply"], row["id"]
        assert result.missing_reason == row["missing_reason"], row["id"]
        assert len(result.evidence) == len(row["evidence"]), row["id"]
        for actual, expected in zip(result.evidence, row["evidence"], strict=True):
            assert actual.field == expected["field"], row["id"]
            assert actual.value == expected["value"], row["id"]
            assert actual.source == expected["source"], row["id"]


def test_memory_query_polish_seed_positive_rows_allow_example_replies() -> None:
    rows = _load_seed()
    positive_categories = {
        "polish_hit_name",
        "polish_hit_company_address",
        "polish_hit_preference",
        "polish_missing_name",
        "polish_missing_profile",
        "polish_thread_fallback",
    }

    positive_rows = [row for row in rows if row["category"] in positive_categories]
    assert len(positive_rows) >= 6
    for row in positive_rows:
        example = row.get("example_polished_reply")
        assert isinstance(example, str) and example
        for evidence in row["evidence"]:
            assert evidence["value"] in example or evidence["value"] in row["deterministic_reply"]


def test_memory_query_polish_seed_forbidden_rows_target_validation_failures() -> None:
    rows = _load_seed()
    forbidden_rows = [
        row
        for row in rows
        if row["category"].startswith("polish_forbidden_")
    ]

    assert len(forbidden_rows) >= 2
    for row in forbidden_rows:
        constraints = row["expected_polish_constraints"]
        assert "fallback_to_deterministic_reply" in constraints
        assert row["forbidden_outputs"]
