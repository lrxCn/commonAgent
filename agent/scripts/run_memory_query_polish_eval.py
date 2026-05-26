#!/usr/bin/env python3
"""Run local memory_query polish evals over polish seed rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR / "src"))

from contracts.memory_query_polish import (  # noqa: E402
    build_polish_input,
    validate_polish_output,
)
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from memory.query import answer_memory_query  # noqa: E402
from memory.query_polish import (  # noqa: E402
    polish_memory_query_reply,
    set_memory_query_polish_llm,
)
from settings.config import Settings, reset_settings, set_settings_override  # noqa: E402

try:  # noqa: E402
    from sync_langsmith_dataset import load_seed
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from scripts.sync_langsmith_dataset import load_seed

_DEFAULT_SEED = _AGENT_DIR / "evals" / "memory_query_polish_seed.json"
_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_local_eval",
    "OPENAI_API_KEY": "sk-local-eval",
    "DATABASE_URL": "postgresql://postgres:local@localhost:5432/common_agent",
}


def _thread_messages(raw_messages: list[dict[str, Any]]) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for item in raw_messages:
        if item["role"] == "user":
            messages.append(HumanMessage(content=str(item["content"])))
        else:
            messages.append(AIMessage(content=str(item["content"])))
    return messages


def _build_polish_input(row: dict[str, Any]):
    context = row.get("context") or {}
    messages = _thread_messages(list(context.get("thread_messages") or []))
    result = answer_memory_query(
        str(row["input"]),
        user_memories=context.get("user_memories"),
        messages=messages or None,
    )
    return build_polish_input(str(row["input"]), result), result


def evaluate_rows(rows: list[dict[str, Any]], *, dry_run: bool = False) -> list[dict[str, Any]]:
    """Evaluate polish validation and fallback behavior for seed rows."""
    results: list[dict[str, Any]] = []
    for row in rows:
        if dry_run:
            results.append(
                {
                    "id": row["id"],
                    "passed": True,
                    "checks": {"dry_run": True},
                    "category": row.get("category", ""),
                }
            )
            continue
        results.append(_evaluate_row(row))
    return results


def _evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
    polish_input, deterministic = _build_polish_input(row)
    checks: dict[str, bool] = {
        "deterministic.reply": polish_input.draft_reply == row["deterministic_reply"],
        "deterministic.missing_reason": polish_input.missing_reason == row.get("missing_reason", ""),
    }

    for index, forbidden in enumerate(row.get("forbidden_outputs") or []):
        ok, _reason = validate_polish_output(
            str(forbidden),
            draft_reply=polish_input.draft_reply,
            evidence=polish_input.evidence,
            missing_reason=polish_input.missing_reason,
        )
        checks[f"forbidden[{index}].rejected"] = not ok

    example = row.get("example_polished_reply")
    if isinstance(example, str) and example:
        ok, _reason = validate_polish_output(
            example,
            draft_reply=polish_input.draft_reply,
            evidence=polish_input.evidence,
            missing_reason=polish_input.missing_reason,
        )
        checks["example.accepted"] = ok

    disabled = polish_memory_query_reply(polish_input, use_llm=False)
    checks["disabled.passthrough"] = disabled.reply == polish_input.draft_reply

    category = str(row.get("category") or "")
    _configure_mock_settings()
    try:
        if category.startswith("polish_forbidden_"):
            tampered = str(row["forbidden_outputs"][0])
            set_memory_query_polish_llm(_llm_returning(tampered))
            outcome = polish_memory_query_reply(polish_input, use_llm=True)
            checks["tamper.fallback_to_draft"] = outcome.reply == polish_input.draft_reply
            checks["tamper.validation_failed"] = outcome.fallback_reason != ""
        elif category.startswith("polish_hit_") or category == "polish_thread_fallback":
            if isinstance(example, str) and example:
                set_memory_query_polish_llm(_llm_returning(example))
                outcome = polish_memory_query_reply(polish_input, use_llm=True)
                checks["mock.success"] = outcome.reply == example
                checks["mock.changed"] = outcome.changed
        elif category.startswith("polish_missing_"):
            if isinstance(example, str) and example:
                set_memory_query_polish_llm(_llm_returning(example))
                outcome = polish_memory_query_reply(polish_input, use_llm=True)
                checks["missing.mock.success"] = outcome.reply == example
    finally:
        set_memory_query_polish_llm(None)
        reset_settings()

    return {
        "id": row["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "category": category,
        "deterministic_reply": deterministic.reply,
    }


def _llm_returning(text: str):
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content=text)
    return mock


def _configure_mock_settings() -> None:
    reset_settings()
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEMORY_QUERY_POLISH_USE_LLM": True,
                "MEMORY_QUERY_POLISH_MODEL_NAME": "Qwen/Qwen2.5-7B-Instruct",
            }
        )
    )  # type: ignore[arg-type]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=_DEFAULT_SEED)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate seed rows without executing polish checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_seed(args.seed)
    results = evaluate_rows(rows, dry_run=args.dry_run)
    passed = sum(1 for item in results if item["passed"])
    summary = {
        "rows": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "dry_run": args.dry_run,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        mode = "dry-run" if args.dry_run else "mock"
        print(
            "memory_query_polish_eval "
            f"mode={mode} rows={summary['rows']} "
            f"passed={summary['passed']} failed={summary['failed']}"
        )
        for item in results:
            status = "pass" if item["passed"] else "fail"
            print(f"{status}: {item['id']} category={item.get('category', '')}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
