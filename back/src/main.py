"""Uvicorn entrypoint: ``uv run uvicorn main:app`` from ``back/`` with PYTHONPATH=src."""

from __future__ import annotations

from api.app import app
from settings.config import get_settings

__all__ = ["app"]


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.BACK_HOST,
        port=settings.BACK_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
