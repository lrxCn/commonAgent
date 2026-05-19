"""Uvicorn entrypoint: `uv run uvicorn main:app` or `uv run python -m main`."""

from __future__ import annotations

from gateway.app import app
from settings.config import get_settings

__all__ = ["app"]


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.AGENT_HOST,
        port=settings.AGENT_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
