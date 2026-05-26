#!/usr/bin/env python3
"""Migrate Qdrant KB payloads from legacy role_id to role_ids[] (M2).

Usage:
  cd agent && uv run python scripts/migrate_kb_role_ids.py --dry-run
  cd agent && uv run python scripts/migrate_kb_role_ids.py --apply

Requires live Qdrant (respects QDRANT_HOST/PORT/COLLECTION from .env).
Legacy ``role_id`` is retained until M3 cleanup (task 98).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR / "src"))

from qdrant_client import QdrantClient  # noqa: E402

from rag.kb_payload_migration import (  # noqa: E402
    apply_qdrant_payload_migration,
    format_qdrant_migration_plan,
)
from settings.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="KB Qdrant role_ids[] payload migration")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview payload updates without writing (default)",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Write role_ids[] to Qdrant points",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.QDRANT_MOCK:
        print("QDRANT_MOCK=true; configure real Qdrant to run this script", file=sys.stderr)
        return 1

    client = QdrantClient(url=settings.qdrant_url)
    collection = settings.QDRANT_COLLECTION_KB

    if not client.collection_exists(collection):
        print(f"collection {collection!r} does not exist", file=sys.stderr)
        return 1

    result = apply_qdrant_payload_migration(
        client,
        collection,
        dry_run=not args.apply,
    )

    print(result.message)
    if result.plan is not None:
        print()
        print(format_qdrant_migration_plan(result.plan))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
