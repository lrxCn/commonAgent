"""User long-term memory read path via LangGraph Store."""

from __future__ import annotations

import asyncio
import logging

from langgraph.store.base import BaseStore, Item, SearchItem

from contracts.memory_store import facts_namespace, profile_namespace
from contracts.memory_write import ExtractionMethod, MemorySubject, StructuredMemoryRecord
from memory.store import get_pooled_store
from memory.structured_record import canonical_fact_text
from settings.config import Settings, get_settings

_PROFILE_ATTRIBUTE_ORDER: tuple[str, ...] = (
    "name",
    "birthday",
    "birth_year",
    "city",
    "job",
    "company.address",
    "preference",
)

logger = logging.getLogger(__name__)


class MemoryUserIdError(ValueError):
    """Raised when user_id is missing or blank for memory reads."""


def _require_user_id(user_id: str | None) -> str:
    if user_id is None or not str(user_id).strip():
        raise MemoryUserIdError("user_id is required to fetch user memories")
    return str(user_id).strip()


def _memory_store_mock_enabled(settings: Settings) -> bool:
    """Return True when Store reads should be skipped."""
    return settings.MEMORY_STORE_MOCK


def _memory_read_limit(settings: Settings) -> int:
    return settings.MEMORY_READ_LIMIT


def profile_value_to_canonical_fact(attribute: str, value: str) -> str:
    """Render a profile field as canonical fact text for downstream memory_profile."""
    subject = (
        MemorySubject.ORG
        if attribute == "company.address"
        else MemorySubject.USER
    )
    record = StructuredMemoryRecord(
        subject=subject,
        attribute="birthday" if attribute == "birth_year" else attribute,
        value=value,
        raw_utterance=value,
        confidence=1.0,
        source_turn_id="profile-read",
        extraction_method=ExtractionMethod.SLOT_FILL_V1.value,
    )
    return canonical_fact_text(record)


def profile_facts_to_strings(
    store: BaseStore,
    user_id: str,
    *,
    limit: int,
) -> list[str]:
    """Load profile namespace entries and render canonical fact strings."""
    namespace = profile_namespace(user_id)
    items = store.search(namespace, limit=max(limit, 1))
    by_attribute: dict[str, Item | SearchItem] = {}
    for item in items:
        attribute = _profile_attribute(item)
        if attribute:
            by_attribute[attribute] = item

    facts: list[str] = []
    seen: set[str] = set()
    for attribute in _PROFILE_ATTRIBUTE_ORDER:
        item = by_attribute.get(attribute)
        if item is None:
            continue
        fact = _profile_fact_text(item)
        if fact and fact not in seen:
            facts.append(fact)
            seen.add(fact)
    for attribute in sorted(by_attribute):
        if attribute in _PROFILE_ATTRIBUTE_ORDER:
            continue
        fact = _profile_fact_text(by_attribute[attribute])
        if fact and fact not in seen:
            facts.append(fact)
            seen.add(fact)
    return facts[:limit]


def search_collection_facts(
    store: BaseStore,
    user_id: str,
    *,
    query: str | None = None,
    limit: int,
) -> list[str]:
    """Semantic (or list) search over inferred free-text facts."""
    namespace = facts_namespace(user_id)
    normalized_query = (query or "").strip()
    if normalized_query:
        try:
            items = store.search(namespace, query=normalized_query, limit=max(limit, 1))
        except Exception:
            logger.warning(
                "semantic user memory search failed; falling back to unfiltered facts",
                exc_info=True,
            )
            items = store.search(namespace, limit=max(limit, 1))
    else:
        items = store.search(namespace, limit=max(limit, 1))

    facts: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _collection_fact_text(item)
        if text and text not in seen:
            facts.append(text)
            seen.add(text)
    return facts[:limit]


def fetch_user_memories(
    user_id: str,
    *,
    query: str | None = None,
    store: BaseStore | None = None,
) -> list[str]:
    """Load merged profile + collection facts for ``user_id`` from LangGraph Store."""
    uid = _require_user_id(user_id)
    settings = get_settings()
    if _memory_store_mock_enabled(settings):
        return []

    active_store = store or get_pooled_store()
    limit = _memory_read_limit(settings)

    profile_facts = profile_facts_to_strings(active_store, uid, limit=limit)
    remaining = max(limit - len(profile_facts), 0)
    collection_facts: list[str] = []
    if remaining > 0:
        collection_facts = search_collection_facts(
            active_store,
            uid,
            query=query,
            limit=remaining,
        )

    merged: list[str] = []
    seen: set[str] = set()
    for fact in [*profile_facts, *collection_facts]:
        if fact not in seen:
            merged.append(fact)
            seen.add(fact)
    return merged[:limit]


async def afetch_user_memories(
    user_id: str,
    *,
    query: str | None = None,
) -> list[str]:
    """Async wrapper around :func:`fetch_user_memories` (thread offload)."""
    return await asyncio.to_thread(fetch_user_memories, user_id, query=query)


def _profile_fact_text(item: Item | SearchItem) -> str:
    payload = getattr(item, "value", None)
    if isinstance(payload, dict):
        canonical = payload.get("canonical")
        if canonical is not None and str(canonical).strip():
            return str(canonical).strip()
    attribute = _profile_attribute(item)
    value = _profile_value(item)
    if attribute and value:
        return profile_value_to_canonical_fact(attribute, value)
    return ""


def _profile_attribute(item: Item | SearchItem) -> str:
    return str(getattr(item, "key", "") or "").strip()


def _profile_value(item: Item | SearchItem) -> str:
    payload = getattr(item, "value", None)
    if isinstance(payload, dict):
        raw = payload.get("value")
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def _collection_fact_text(item: Item | SearchItem) -> str:
    payload = getattr(item, "value", None)
    if isinstance(payload, dict):
        for key in ("text", "memory", "content"):
            raw = payload.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return ""
