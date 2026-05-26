"""Tests for Back DATABASE_URL resolution from Agent settings."""

from __future__ import annotations

import pytest

from settings.config import Settings
from settings.database_url import (
    replace_database_name,
    resolve_back_database_url,
    to_sqlalchemy_psycopg_url,
)


def test_replace_database_name() -> None:
    agent_url = "postgresql://postgres:secret@localhost:5432/common_agent"
    assert (
        replace_database_name(agent_url, "common_agent_back")
        == "postgresql://postgres:secret@localhost:5432/common_agent_back"
    )


def test_to_sqlalchemy_psycopg_url() -> None:
    assert (
        to_sqlalchemy_psycopg_url("postgresql://postgres:secret@localhost:5432/db")
        == "postgresql+psycopg://postgres:secret@localhost:5432/db"
    )


def test_resolve_back_database_url_from_agent() -> None:
    resolved = resolve_back_database_url(
        database_url=None,
        agent_database_url="postgresql://postgres:secret@localhost:5432/common_agent",
    )
    assert resolved == "postgresql+psycopg://postgres:secret@localhost:5432/common_agent_back"


def test_settings_requires_database_or_agent_url() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL or AGENT_DATABASE_URL"):
        Settings(
            _env_file=None,
            AGENT_URL="http://127.0.0.1:18080",
            SESSION_SECRET="test",
            DATABASE_URL=None,
            AGENT_DATABASE_URL=None,
        )


def test_settings_derives_from_agent_database_url() -> None:
    settings = Settings(
        AGENT_URL="http://127.0.0.1:18080",
        SESSION_SECRET="test",
        AGENT_DATABASE_URL="postgresql://postgres:secret@localhost:5432/common_agent",
    )
    assert (
        settings.DATABASE_URL
        == "postgresql+psycopg://postgres:secret@localhost:5432/common_agent_back"
    )
