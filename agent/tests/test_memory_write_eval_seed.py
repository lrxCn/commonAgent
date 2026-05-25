"""Smoke tests for local memory_write eval seed structure."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.memory_write import MemoryWriteExpectation, StructuredMemoryRecord


_SEED_PATH = Path(__file__).resolve().parents[1] / "evals" / "memory_write_seed.json"
_REQUIRED_CATEGORIES = {
    "structured_fact_update",
    "inferred_general_chat",
    "regression_store_empty",
}


def _load_seed() -> list[dict]:
    payload = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def test_memory_write_seed_rows_validate_against_contract() -> None:
    rows = _load_seed()
    ids: set[str] = set()

    for row in rows:
        assert isinstance(row["id"], str) and row["id"]
        assert row["id"] not in ids
        ids.add(row["id"])
        assert isinstance(row["category"], str) and row["category"]
        assert isinstance(row["input"], str) and row["input"]
        assert isinstance(row["context"], dict)

        expected = row["expected_write"]
        record_payload = expected.get("expected_record")
        record = (
            StructuredMemoryRecord.model_validate(record_payload)
            if record_payload is not None
            else None
        )
        expectation = MemoryWriteExpectation(
            mode=expected["mode"],
            infer=expected["infer"],
            expected_record=record,
            expected_final_status=expected.get("expected_final_status"),
            forbidden_final_status=tuple(expected.get("forbidden_final_status", ())),
        )
        assert expectation.mode == expected["mode"]
        assert expectation.infer is expected["infer"]


def test_memory_write_seed_has_required_category_coverage() -> None:
    rows = _load_seed()
    covered = {row["category"] for row in rows}

    assert _REQUIRED_CATEGORIES.issubset(covered)


def test_memory_write_seed_includes_required_structured_fact_examples() -> None:
    rows = _load_seed()
    structured_inputs = {
        row["input"]
        for row in rows
        if row["category"] == "structured_fact_update"
    }

    assert {"我叫张三", "我出生于1997年", "我公司在天翔街188号"}.issubset(structured_inputs)


def test_structured_fact_rows_target_structured_mode_without_infer() -> None:
    rows = _load_seed()
    structured_rows = [
        row for row in rows if row["category"] == "structured_fact_update"
    ]

    assert len(structured_rows) >= 3
    for row in structured_rows:
        expected = row["expected_write"]
        assert expected["mode"] == "structured"
        assert expected["infer"] is False
        assert "expected_record" in expected
        record = StructuredMemoryRecord.model_validate(expected["expected_record"])
        assert record.raw_utterance == row["input"]


def test_inferred_general_chat_row_targets_infer_true() -> None:
    rows = _load_seed()
    inferred_rows = [
        row for row in rows if row["category"] == "inferred_general_chat"
    ]

    assert len(inferred_rows) >= 1
    for row in inferred_rows:
        expected = row["expected_write"]
        assert expected["mode"] == "inferred"
        assert expected["infer"] is True
        assert "expected_record" not in expected


def test_regression_store_empty_forbids_stored_empty() -> None:
    rows = _load_seed()
    regression_rows = [
        row for row in rows if row["category"] == "regression_store_empty"
    ]

    assert len(regression_rows) >= 1
    for row in regression_rows:
        expected = row["expected_write"]
        assert expected["mode"] == "structured"
        assert expected["infer"] is False
        assert "stored_empty" in expected.get("forbidden_final_status", [])
