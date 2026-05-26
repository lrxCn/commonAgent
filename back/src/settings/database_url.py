"""Helpers to derive Back DATABASE_URL from Agent Postgres settings."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def replace_database_name(database_url: str, database_name: str) -> str:
    """Return a copy of ``database_url`` with the path/database segment replaced."""
    parsed = urlparse(database_url.strip())
    return urlunparse(parsed._replace(path=f"/{database_name.lstrip('/')}"))


def to_sqlalchemy_psycopg_url(database_url: str) -> str:
    """Normalize plain ``postgresql://`` URLs for SQLAlchemy + psycopg3."""
    url = database_url.strip()
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def resolve_back_database_url(
    *,
    database_url: str | None,
    agent_database_url: str | None,
    back_database_name: str = "common_agent_back",
) -> str:
    """Resolve the Back SQLAlchemy URL from explicit or Agent-derived settings."""
    if database_url and database_url.strip():
        return to_sqlalchemy_psycopg_url(database_url)

    if not agent_database_url or not agent_database_url.strip():
        msg = (
            "Set DATABASE_URL or AGENT_DATABASE_URL "
            "(use the same Postgres credentials as agent/.env)."
        )
        raise ValueError(msg)

    derived = replace_database_name(agent_database_url, back_database_name)
    return to_sqlalchemy_psycopg_url(derived)
