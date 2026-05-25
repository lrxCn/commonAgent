"""Tests for the local memory write eval runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_memory_write_eval import evaluate_rows

_AGENT_DIR = Path(__file__).resolve().parents[1]
_SEED_PATH = _AGENT_DIR / "evals" / "memory_write_seed.json"


def test_memory_write_eval_runner_structured_row_passes_with_mock_store() -> None:
    rows = [
        {
            "id": "memory-write-fact-name-001",
            "category": "structured_fact_update",
            "input": "我叫张三",
            "context": {"user_id": "u1", "role_id": "role-sales", "tools": []},
            "expected_write": {
                "mode": "structured",
                "infer": False,
                "expected_record": {
                    "subject": "user",
                    "attribute": "name",
                    "value": "张三",
                    "raw_utterance": "我叫张三",
                },
                "expected_final_status": "stored",
            },
        }
    ]

    results = evaluate_rows(rows)

    assert results[0]["passed"] is True
    assert results[0]["checks"]["write.not_stored_empty"] is True
    assert results[0]["stored_count"] >= 1


def test_memory_write_eval_runner_regression_row_captures_infer_store_empty() -> None:
    rows = [
        {
            "id": "memory-write-regression-store-empty-001",
            "category": "regression_store_empty",
            "input": "我叫张三",
            "context": {"user_id": "u1", "role_id": "role-sales", "tools": []},
            "expected_write": {
                "mode": "structured",
                "infer": False,
                "forbidden_final_status": ["stored_empty"],
            },
        }
    ]

    results = evaluate_rows(rows)

    assert results[0]["passed"] is True
    assert results[0]["checks"]["write.not_stored_empty"] is True
    assert results[0]["checks"]["regression.infer_path_store_empty"] is True


def test_memory_write_eval_runner_json_cli_passes_seed() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_write_eval.py",
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


def test_memory_write_eval_runner_dry_run_skips_mock_writes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_write_eval.py",
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
