#!/usr/bin/env python3
"""Run local deterministic intent/path evals over intent seed rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR / "src"))

from contracts.intent import IntentDecision, IntentRoute  # noqa: E402
from intent.engine import classify_intent  # noqa: E402
from intent.fallback import intent_fallback_decision  # noqa: E402
from intent.policy import decide_fast_path_policy_for_message  # noqa: E402
try:  # noqa: E402
    from sync_langsmith_dataset import load_seed
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from scripts.sync_langsmith_dataset import load_seed

_DEFAULT_SEED = _AGENT_DIR / "evals" / "intent_seed.json"
_EVAL_EXPECTATION_KEYS = {
    "confidence_min",
    "policy.fast_path_allowed",
    "executor.selected",
    "fallback.allowed",
}


def evaluate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate deterministic intent decisions against seed expectations."""
    results: list[dict[str, Any]] = []
    for row in rows:
        expected_payload = dict(row["expected_intent"])
        expected_contract = {
            key: value
            for key, value in expected_payload.items()
            if key not in _EVAL_EXPECTATION_KEYS
        }
        expected = IntentDecision.model_validate({"confidence": 0.9, **expected_contract})
        context = row.get("context") or {}
        tools = context.get("tools") if isinstance(context, dict) else []
        predicted = classify_intent(str(row["input"]), tools_context=tools)
        policy = decide_fast_path_policy_for_message(predicted, str(row["input"]), tools_context=tools)
        fallback = intent_fallback_decision(
            predicted,
            original_route=str(predicted.route),
        )
        checks = _check_expected(
            predicted=predicted,
            expected=expected,
            expected_payload=expected_payload,
            policy_fast_path_allowed=policy.fast_path_allowed,
            executor_selected=_executor_for_route(predicted.route),
            fallback_allowed=fallback is not None,
        )
        results.append(
            {
                "id": row["id"],
                "passed": all(checks.values()),
                "checks": checks,
                "predicted": predicted.to_trace_dict(),
                "expected": expected.to_trace_dict(),
                "policy": policy.to_trace_dict(),
                "executor": {"selected": _executor_for_route(predicted.route)},
                "fallback": (
                    fallback.to_trace_dict()
                    if fallback is not None
                    else {"fallback.triggered": False}
                ),
            }
        )
    return results


def _check_expected(
    *,
    predicted: IntentDecision,
    expected: IntentDecision,
    expected_payload: dict[str, Any],
    policy_fast_path_allowed: bool,
    executor_selected: str,
    fallback_allowed: bool,
) -> dict[str, bool]:
    expected_confidence = float(expected_payload.get("confidence_min", 0.0))
    expected_policy = expected_payload.get("policy.fast_path_allowed")
    expected_executor = expected_payload.get("executor.selected")
    expected_fallback = expected_payload.get("fallback.allowed")
    checks = {
        "intent.route": predicted.route == expected.route,
        "intent.speech_act": predicted.speech_act == expected.speech_act,
        "intent.domain": predicted.domain == expected.domain,
        "intent.operation": predicted.operation == expected.operation,
        "intent.confidence_min": float(predicted.confidence) >= expected_confidence,
        "policy.fast_path_allowed": (
            True
            if expected_policy is None
            else policy_fast_path_allowed is bool(expected_policy)
        ),
        "executor.selected": (
            True if expected_executor is None else executor_selected == str(expected_executor)
        ),
        "fallback.allowed": (
            True if expected_fallback is None else fallback_allowed is bool(expected_fallback)
        ),
    }
    return checks


def _executor_for_route(route: str | IntentRoute) -> str:
    value = str(getattr(route, "value", route))
    return {
        IntentRoute.FACT_UPDATE.value: "fact_update_confirm",
        IntentRoute.MEMORY_QUERY.value: "memory_query_executor",
        IntentRoute.KNOWLEDGE_QUERY.value: "rag_answer_executor",
        IntentRoute.CLIENT_ACTION.value: "action_executor",
        IntentRoute.CHITCHAT.value: "chitchat_executor",
        IntentRoute.AMBIGUOUS.value: "deepagents_executor",
        IntentRoute.GENERAL_CHAT.value: "deepagents_executor",
        IntentRoute.SAFETY_REFUSAL.value: "safety_refusal",
    }.get(value, "deepagents_executor")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=_DEFAULT_SEED)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_seed(args.seed)
    results = evaluate_rows(rows)
    passed = sum(1 for item in results if item["passed"])
    summary = {
        "rows": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"intent_eval rows={summary['rows']} passed={summary['passed']} failed={summary['failed']}")
        for item in results:
            status = "pass" if item["passed"] else "fail"
            route = item["predicted"]["route"]
            print(f"{status}: {item['id']} route={route}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
