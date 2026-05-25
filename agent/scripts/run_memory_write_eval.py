#!/usr/bin/env python3
"""Run local memory-write evals over memory_write seed rows."""

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

from contracts.memory_write import StructuredMemoryRecord  # noqa: E402
from intent.engine import classify_intent  # noqa: E402
from intent.signals import extract_signals  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from memory.store import reset_pooled_store  # noqa: E402
from memory.write import (  # noqa: E402
    extract_and_store,
    reset_write_overrides,
    set_manager_invoke_fn,
    store_structured_record,
)
from memory.structured_record import build_structured_memory_record  # noqa: E402
from settings.config import Settings, reset_settings, set_settings_override  # noqa: E402

try:  # noqa: E402
    from sync_langsmith_dataset import load_seed
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from scripts.sync_langsmith_dataset import load_seed

_DEFAULT_SEED = _AGENT_DIR / "evals" / "memory_write_seed.json"
_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_local_eval",
    "OPENAI_API_KEY": "sk-local-eval",
    "DATABASE_URL": "postgresql://postgres:local@localhost:5432/common_agent",
}


def evaluate_rows(rows: list[dict[str, Any]], *, dry_run: bool = False) -> list[dict[str, Any]]:
    """Evaluate memory write seed rows with mocked Store/langmem by default."""
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

        category = str(row.get("category") or "")
        if category in {"structured_fact_update", "regression_store_empty"}:
            results.append(_evaluate_structured_row(row))
        elif category == "inferred_general_chat":
            results.append(_evaluate_inferred_row(row))
        else:
            results.append(
                {
                    "id": row["id"],
                    "passed": False,
                    "checks": {"category.supported": False},
                    "category": category,
                }
            )
    return results


def _evaluate_structured_row(row: dict[str, Any]) -> dict[str, Any]:
    expected = row["expected_write"]
    context = row.get("context") or {}
    user_id = str(context.get("user_id") or "eval-user")
    tools = context.get("tools") if isinstance(context, dict) else []
    text = str(row["input"])

    signals = extract_signals(text, tools_context=tools)
    decision = classify_intent(text, tools_context=tools)
    record = build_structured_memory_record(
        signals,
        decision,
        source_turn_id=f"eval:{row['id']}",
    )
    checks: dict[str, bool] = {
        "slot_fill.record": record is not None,
        "write.mode_structured": expected.get("mode") == "structured",
        "write.infer_false": expected.get("infer") is False,
    }
    if record is None:
        return _result(row, checks, status="", mode="structured", stored_count=0)

    expected_record = expected.get("expected_record") or {}
    checks.update(_record_checks(record, expected_record))

    _configure_mock_settings()
    write_result = store_structured_record(user_id, record)
    checks["write.stored_count"] = write_result.stored_count >= 1
    checks["write.not_stored_empty"] = write_result.status != "stored_empty"
    if expected.get("expected_final_status"):
        checks["write.status"] = write_result.status == expected["expected_final_status"]
    for forbidden in expected.get("forbidden_final_status", ()):
        checks[f"write.not_{forbidden}"] = write_result.status != forbidden

    if row.get("category") == "regression_store_empty":
        infer_result = _simulate_infer_store_empty(user_id=user_id, text=text)
        checks["regression.infer_path_store_empty"] = infer_result.status == "stored_empty"

    reset_write_overrides()
    reset_pooled_store()
    reset_settings()
    return _result(
        row,
        checks,
        status=write_result.status,
        mode="structured",
        stored_count=write_result.stored_count,
        record=record,
    )


def _evaluate_inferred_row(row: dict[str, Any]) -> dict[str, Any]:
    expected = row["expected_write"]
    context = row.get("context") or {}
    user_id = str(context.get("user_id") or "eval-user")
    text = str(row["input"])

    reset_settings()
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEMORY_STORE_MOCK": False,
                "QDRANT_MOCK": True,
            }
        )
    )  # type: ignore[arg-type]
    reset_write_overrides()
    invoke_mock = MagicMock(
        return_value=[
            {
                "namespace": ("users", user_id, "facts"),
                "key": "fact-1",
                "value": {"kind": "Memory", "content": {"content": "inferred preference"}},
            }
        ]
    )
    set_manager_invoke_fn(invoke_mock)
    write_result = extract_and_store(
        user_id,
        [
            HumanMessage(content=text),
            AIMessage(content="好的。"),
        ],
    )

    checks = {
        "write.mode_inferred": expected.get("mode") == "inferred",
        "write.manager_invoked": invoke_mock.call_count == 1,
        "write.stored_count": write_result.stored_count >= 1,
        "write.not_stored_empty": write_result.status != "stored_empty",
    }
    if expected.get("expected_final_status"):
        checks["write.status"] = write_result.status == expected["expected_final_status"]

    reset_write_overrides()
    reset_pooled_store()
    reset_settings()
    return _result(
        row,
        checks,
        status=write_result.status,
        mode="inferred",
        stored_count=write_result.stored_count,
    )


def _record_checks(
    record: StructuredMemoryRecord,
    expected_record: dict[str, Any],
) -> dict[str, bool]:
    checks = {
        "record.subject": record.subject == expected_record.get("subject", record.subject),
        "record.attribute": record.attribute == expected_record.get("attribute", record.attribute),
        "record.value": _values_match(record, expected_record),
        "record.raw_utterance": record.raw_utterance
        == expected_record.get("raw_utterance", record.raw_utterance),
    }
    return checks


def _values_match(record: StructuredMemoryRecord, expected_record: dict[str, Any]) -> bool:
    expected_value = str(expected_record.get("value") or "")
    if not expected_value:
        return True
    if record.attribute == "birthday":
        return record.value in {expected_value, expected_value.removesuffix("年")}
    return record.value == expected_value


def _simulate_infer_store_empty(*, user_id: str, text: str) -> Any:
    reset_settings()
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEMORY_STORE_MOCK": False,
                "QDRANT_MOCK": True,
            }
        )
    )  # type: ignore[arg-type]
    set_manager_invoke_fn(MagicMock(return_value=[]))
    return extract_and_store(
        user_id,
        [
            HumanMessage(content=text),
            AIMessage(content="已收到，我会把这个信息作为你的偏好/事实参考。"),
        ],
    )


def _configure_mock_settings() -> None:
    reset_settings()
    set_settings_override(
        Settings(
            **{
                **_REQUIRED_ENV,
                "MEMORY_STORE_MOCK": True,
                "QDRANT_MOCK": True,
            }
        )
    )  # type: ignore[arg-type]
    reset_write_overrides()
    reset_pooled_store()


def _result(
    row: dict[str, Any],
    checks: dict[str, bool],
    *,
    status: str,
    mode: str,
    stored_count: int,
    record: StructuredMemoryRecord | None = None,
) -> dict[str, Any]:
    return {
        "id": row["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "category": row.get("category", ""),
        "mode": mode,
        "status": status,
        "stored_count": stored_count,
        "record": record.model_dump(mode="json") if record is not None else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=_DEFAULT_SEED)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate seed rows without executing mock memory writes.",
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
            "memory_write_eval "
            f"mode={mode} rows={summary['rows']} "
            f"passed={summary['passed']} failed={summary['failed']}"
        )
        for item in results:
            status = "pass" if item["passed"] else "fail"
            print(f"{status}: {item['id']} category={item.get('category', '')}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
