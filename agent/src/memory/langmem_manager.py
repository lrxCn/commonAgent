"""LangMem memory store manager factory for inferred post-turn writes."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from contracts.llm import ModelUseCase
from infrastructure.llm.gateway import LlmGateway
from memory.store import get_pooled_store
from settings.config import get_settings

_INSTRUCTIONS_PATH = (
    Path(__file__).parent / "prompts" / "memory_extract_instructions.txt"
)

_manager: Any | None = None
_manager_factory_override: Callable[[], Any] | None = None


@lru_cache
def _load_extract_instructions() -> str:
    return _INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()


def set_memory_store_manager_factory(
    factory: Callable[[], Any] | None,
) -> None:
    """Replace manager construction for tests; pass None to clear."""
    global _manager, _manager_factory_override
    _manager_factory_override = factory
    _manager = None


def reset_memory_store_manager() -> None:
    """Clear cached manager and test overrides."""
    set_memory_store_manager_factory(None)


def get_memory_store_manager() -> Any:
    """Return a singleton ``create_memory_store_manager`` instance."""
    global _manager
    if _manager_factory_override is not None:
        return _manager_factory_override()
    if _manager is None:
        from langmem import create_memory_store_manager

        settings = get_settings()
        gateway = LlmGateway(settings)
        model = gateway.chat_model(ModelUseCase.MEMORY_EXTRACT)
        _manager = create_memory_store_manager(
            model,
            namespace=("users", "{user_id}", "facts"),
            instructions=_load_extract_instructions(),
            enable_inserts=True,
            enable_deletes=False,
            store=get_pooled_store(),
        )
    return _manager
