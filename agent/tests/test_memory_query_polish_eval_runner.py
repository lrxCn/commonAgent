"""Tests for the local memory_query polish eval runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_memory_query_polish_eval import evaluate_rows

_AGENT_DIR = Path(__file__).resolve().parents[1]
_SEED_PATH = _AGENT_DIR / "evals" / "memory_query_polish_seed.json"


def test_memory_query_polish_eval_runner_forbidden_tamper_falls_back() -> None:
    rows = [
        {
            "id": "memory-query-polish-forbidden-fact-tamper-001",
            "category": "polish_forbidden_fact_tamper",
            "input": "我叫什么",
            "context": {"user_memories": ["用户叫刘日兴"]},
            "deterministic_reply": "我记录到你叫刘日兴。",
            "evidence": [
                {"field": "name", "value": "刘日兴", "source": "memory_profile"},
            ],
            "missing_reason": "",
            "expected_polish_constraints": ["fallback_to_deterministic_reply"],
            "forbidden_outputs": ["你叫王五。"],
        }
    ]

    results = evaluate_rows(rows)

    assert results[0]["passed"] is True
    assert results[0]["checks"]["tamper.fallback_to_draft"] is True
    assert results[0]["checks"]["tamper.validation_failed"] is True


def test_memory_query_polish_eval_runner_hit_row_accepts_example() -> None:
    rows = [
        {
            "id": "memory-query-polish-name-hit-001",
            "category": "polish_hit_name",
            "input": "我叫什么",
            "context": {"user_memories": ["用户叫刘日兴"]},
            "deterministic_reply": "我记录到你叫刘日兴。",
            "evidence": [
                {"field": "name", "value": "刘日兴", "source": "memory_profile"},
            ],
            "missing_reason": "",
            "expected_polish_constraints": ["must_preserve_evidence_values"],
            "forbidden_outputs": ["王五"],
            "example_polished_reply": "我记得你的名字是刘日兴。",
        }
    ]

    results = evaluate_rows(rows)

    assert results[0]["passed"] is True
    assert results[0]["checks"]["example.accepted"] is True
    assert results[0]["checks"]["mock.success"] is True


def test_memory_query_polish_eval_runner_json_cli_passes_seed() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_query_polish_eval.py",
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
    assert payload["rows"] >= 8
    assert payload["failed"] == 0


def test_memory_query_polish_eval_runner_dry_run_skips_checks() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_query_polish_eval.py",
            "--seed",
            str(_SEED_PATH),
            "--dry-run",
            "--json",
        ],
        cwd=_AGENT_DIR,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["failed"] == 0
    assert all(item["checks"]["dry_run"] for item in payload["results"])
