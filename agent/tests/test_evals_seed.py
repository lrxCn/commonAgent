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


def test_rag_seed_rows_have_fixture_and_retrieval_expectations() -> None:
    rows = _load_seed()
    rag_rows = [
        row
        for row in rows
        if row["expected_answer"].get("requires_rag")
    ]
    assert len(rag_rows) >= 2
    assert any("role_filter" in row.get("eval_tags", []) for row in rag_rows)
    for row in rag_rows:
        assert isinstance(row.get("kb_fixture"), list) and row["kb_fixture"]
        answer = row["expected_answer"]
        assert isinstance(answer.get("expected_doc_ids"), list) and answer["expected_doc_ids"]
        assert isinstance(answer.get("forbidden_doc_ids"), list)
        for fixture in row["kb_fixture"]:
            assert fixture["role_id"]
            assert fixture["doc_id"]
            assert fixture["doc_name"]
            assert fixture["version"]
            assert fixture["content"]
