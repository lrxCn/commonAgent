#!/usr/bin/env python3
"""Migrate Back KB meta from legacy (doc_id, role_id) rows to multi-role schema (M2).

Usage:
  cd back && uv run python scripts/migrate_kb_multi_role.py --dry-run
  cd back && uv run python scripts/migrate_kb_multi_role.py --apply

PostgreSQL apply delegates to Alembic ``002_kb_multi_role``. SQLite apply uses the
embedded DDL path for local tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACK_ROOT = Path(__file__).resolve().parent.parent
if str(_BACK_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_BACK_ROOT / "src"))

from alembic.config import Config  # noqa: E402

from db.session import create_engine_from_url  # noqa: E402
from services.kb_migration import (  # noqa: E402
    apply_postgres_kb_migration,
    format_migration_plan,
)
from settings.config import get_settings  # noqa: E402


def _build_alembic_cfg(database_url: str) -> Config:
    cfg = Config(str(_BACK_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACK_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.set_main_option("prepend_sys_path", str(_BACK_ROOT / "src"))
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="KB multi-role Postgres data migration")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview merge plan without writing (default)",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Apply migration (PostgreSQL uses Alembic 002_kb_multi_role)",
    )
    args = parser.parse_args()

    settings = get_settings()
    database_url = settings.DATABASE_URL
    if not database_url:
        print("DATABASE_URL is not configured", file=sys.stderr)
        return 1

    engine = create_engine_from_url(database_url)
    try:
        result = apply_postgres_kb_migration(
            engine,
            dry_run=not args.apply,
            alembic_cfg=_build_alembic_cfg(database_url) if args.apply else None,
        )
    finally:
        engine.dispose()

    print(result.message)
    if result.plan is not None:
        print()
        print(format_migration_plan(result.plan))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
