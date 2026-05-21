"""Smoke tests for local eval seed structure."""

from __future__ import annotations

import json
from pathlib import Path


_SEED_PATH = Path(__file__).resolve().parents[1] / "evals" / "seed.json"
_REQUIRED_TURN_TYPES = {
    "fact_update",
    "chitchat",
    "knowledge_query",
    "ambiguous",
    "client_action",
}


def _load_seed() -> list[dict]:
    payload = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def test_seed_has_required_turn_type_coverage() -> None:
    rows = _load_seed()
    covered = {row["expected_path"]["turn_type"] for row in rows}
    assert _REQUIRED_TURN_TYPES.issubset(covered)


def test_seed_rows_have_answer_and_path_expectations() -> None:
    rows = _load_seed()
    ids: set[str] = set()
    for row in rows:
        assert isinstance(row["id"], str) and row["id"]
        assert row["id"] not in ids
        ids.add(row["id"])
        assert isinstance(row["input"], str) and row["input"]
        assert isinstance(row["context"], dict)
        assert isinstance(row["expected_answer"], dict)
        assert isinstance(row["expected_path"], dict)
        assert "kind" in row["expected_answer"]
        assert "turn_type" in row["expected_path"]
        assert "llm_call_count_max" in row["expected_path"]
        assert "rag_called" in row["expected_path"]


def test_client_action_seed_contains_tools_context() -> None:
    rows = _load_seed()
    action_row = next(row for row in rows if row["expected_path"]["turn_type"] == "client_action")
    tools = action_row["context"]["tools"]
    assert isinstance(tools, list) and tools
    assert tools[0]["name"] == "jumpPage"
