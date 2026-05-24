"""Tests for the local intent eval runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_intent_eval import evaluate_rows

_AGENT_DIR = Path(__file__).resolve().parents[1]
_SEED_PATH = _AGENT_DIR / "evals" / "intent_seed.json"


def test_intent_eval_runner_evaluates_expected_control_plane_fields() -> None:
    rows = [
        {
            "id": "intent-memory-whoami-001",
            "input": "我是谁",
            "context": {"user_id": "u1", "role_id": "role-sales", "tools": []},
            "expected_intent": {
                "speech_act": "question",
                "domain": "user_memory",
                "operation": "memory_read",
                "route": "memory_query",
                "risk": "low",
                "reasons": ["first_person_question", "memory_profile_target"],
                "evidence": ["我是谁"],
                "needs_clarification": False,
                "confidence_min": 0.9,
                "policy.fast_path_allowed": False,
                "executor.selected": "memory_query_executor",
                "fallback.allowed": False,
            },
        }
    ]

    results = evaluate_rows(rows)

    assert results[0]["passed"] is True
    assert results[0]["checks"] == {
        "intent.route": True,
        "intent.speech_act": True,
        "intent.domain": True,
        "intent.operation": True,
        "intent.confidence_min": True,
        "policy.fast_path_allowed": True,
        "executor.selected": True,
        "fallback.allowed": True,
    }


def test_intent_eval_runner_json_cli_dry_path() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_intent_eval.py",
            "--seed",
            str(_SEED_PATH),
            "--json",
        ],
        cwd=_AGENT_DIR,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["rows"] >= 1
    assert payload["failed"] == 0
    assert any(item["id"] == "intent-feedback-whoami-fp-fact-update-001" for item in payload["results"])


def test_langsmith_sync_supports_intent_seed_dry_run_without_network_client() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/sync_langsmith_dataset.py",
            "--dataset-name",
            "common-agent-intent-seed",
            "--seed",
            str(_SEED_PATH),
            "--dry-run",
        ],
        cwd=_AGENT_DIR,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "dry-run dataset=common-agent-intent-seed" in result.stdout
    assert "intent-feedback-whoami-fp-fact-update-001" in result.stdout
