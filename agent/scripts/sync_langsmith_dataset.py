#!/usr/bin/env python3
"""Sync local eval seed JSON into a LangSmith dataset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from langsmith import Client

_AGENT_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_ENV = _AGENT_DIR / ".env"
_DEFAULT_SEED = _AGENT_DIR / "evals" / "seed.json"


def load_agent_env(env_path: Path | None = None) -> Path | None:
    path = env_path or _DEFAULT_ENV
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))
    if not os.environ.get("LANGCHAIN_API_KEY") and os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGCHAIN_API_KEY", os.environ["LANGSMITH_API_KEY"])
    return path


def load_seed(seed_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("seed file must contain a JSON array")
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each seed row must be a JSON object")
        rows.append(item)
    return rows


def get_or_create_dataset(
    client: Client,
    dataset_name: str,
    *,
    seed_path: Path = _DEFAULT_SEED,
) -> Any:
    for dataset in client.list_datasets(dataset_name=dataset_name):
        return dataset
    return client.create_dataset(
        dataset_name=dataset_name,
        description=f"commonAgent local eval seed synced from {seed_path.name}",
    )


def example_payload(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs = {
        "input": row["input"],
        "context": row["context"],
    }
    if "kb_fixture" in row:
        inputs["kb_fixture"] = row["kb_fixture"]
    if "expected_intent" in row:
        outputs = {"expected_intent": row["expected_intent"]}
    else:
        outputs = {
            "expected_answer": row["expected_answer"],
            "expected_path": row["expected_path"],
        }
    metadata = {
        "id": row["id"],
        "seed_version": "local-json-v1",
    }
    if "eval_tags" in row:
        metadata["eval_tags"] = row["eval_tags"]
    if "feedback" in row:
        metadata["feedback"] = row["feedback"]
    return inputs, outputs, metadata


def dry_run_dataset(*, dataset_name: str, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        example_payload(row)
        print(f"dry-run: {row['id']}")
    print(f"dry-run dataset={dataset_name} rows={len(rows)}")
    return 0


def sync_dataset(
    *,
    client: Client,
    dataset_name: str,
    rows: list[dict[str, Any]],
    dry_run: bool,
    seed_path: Path = _DEFAULT_SEED,
) -> int:
    if dry_run:
        return dry_run_dataset(dataset_name=dataset_name, rows=rows)

    dataset = get_or_create_dataset(client, dataset_name, seed_path=seed_path)
    dataset_id = str(dataset.id)
    existing = {
        (example.metadata or {}).get("id"): example
        for example in client.list_examples(dataset_id=dataset_id)
        if (example.metadata or {}).get("id")
    }

    created = 0
    updated = 0
    for row in rows:
        inputs, outputs, metadata = example_payload(row)
        current = existing.get(row["id"])
        if current is None:
            client.create_example(
                dataset_id=dataset_id,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
            )
            created += 1
            continue
        client.update_example(
            example_id=current.id,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
        )
        updated += 1

    print(f"dataset={dataset_name} created={created} updated={updated}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", required=True, help="Target LangSmith dataset name.")
    parser.add_argument(
        "--seed",
        type=Path,
        default=_DEFAULT_SEED,
        help=f"Path to local seed JSON (default: {_DEFAULT_SEED})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_agent_env()
    rows = load_seed(args.seed)
    if args.dry_run:
        return dry_run_dataset(dataset_name=args.dataset_name, rows=rows)
    client = Client()
    return sync_dataset(
        client=client,
        dataset_name=args.dataset_name,
        rows=rows,
        dry_run=bool(args.dry_run),
        seed_path=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
