"""CLI entry: ``uv run python -m db.seed`` from ``back/``."""

from __future__ import annotations

from db.seed import run_seed
from db.session import create_engine_from_url, get_session_factory
from settings.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine_from_url(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    run_seed(session_factory, settings.ADMIN_SEED_PASSWORD)
    print("Demo seed completed.")


if __name__ == "__main__":
    main()
