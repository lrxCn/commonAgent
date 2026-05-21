"""Unified LangSmith tracing: env wiring, traceable spans, safe metadata."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_MESSAGE_TRUNCATE = 500


def is_tracing_enabled() -> bool:
    """Whether LangChain/LangSmith export is active (``LANGCHAIN_TRACING_V2``)."""
    raw = os.environ.get("LANGCHAIN_TRACING_V2", "")
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _message_truncate_limit() -> int:
    raw = os.environ.get("LANGCHAIN_TRACE_MESSAGE_MAX_CHARS", "").strip()
    if not raw:
        return DEFAULT_MESSAGE_TRUNCATE
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_MESSAGE_TRUNCATE


def truncate_for_trace(text: str, *, limit: int | None = None) -> str:
    """Truncate long strings for trace payloads (not for model I/O)."""
    max_len = _message_truncate_limit() if limit is None else limit
    if max_len <= 0 or len(text) <= max_len:
        return text
    return f"{text[:max_len]}…({len(text)} chars)"


def redact_secrets(
    value: str,
    secrets: Sequence[str] | None = None,
) -> str:
    """Mask known secret substrings before they appear in trace metadata."""
    if not value or not secrets:
        return value
    redacted = value
    for secret in secrets:
        if secret and len(secret) >= 8 and secret in redacted:
            redacted = redacted.replace(secret, "***")
    return redacted


def _collect_secret_values() -> list[str]:
    try:
        from settings.config import get_settings

        settings = get_settings()
    except Exception:
        return []
    candidates = [
        settings.LANGSMITH_API_KEY,
        settings.LANGCHAIN_API_KEY or "",
        settings.OPENAI_API_KEY,
    ]
    return [s for s in candidates if s]


def configure_tracing_from_settings(settings: Any | None = None) -> bool:
    """
    Push Settings values into process env for LangChain/LangSmith clients.

    Returns whether tracing export is enabled.
    """
    if settings is None:
        from settings.config import get_settings

        settings = get_settings()

    os.environ["LANGCHAIN_TRACING_V2"] = (
        "true" if settings.LANGCHAIN_TRACING_V2 else "false"
    )
    if settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_TRACE_MESSAGE_MAX_CHARS"] = str(
        settings.LANGCHAIN_TRACE_MESSAGE_MAX_CHARS
    )
    return bool(settings.LANGCHAIN_TRACING_V2)


def attach_run_metadata(metadata: Mapping[str, Any]) -> None:
    """Merge metadata onto the current LangSmith run tree (no-op if absent)."""
    if not metadata:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree

        tree = get_current_run_tree()
        if tree is None:
            return
        existing = tree.metadata or {}
        tree.metadata = {**existing, **dict(metadata)}
    except Exception:
        pass


def build_path_contract_trace_metadata(
    path_metrics: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return trace metadata for passive path-contract observability."""
    from observability.path_contract import path_metrics_metadata

    return path_metrics_metadata(path_metrics)


def traceable(
    *,
    name: str,
    run_type: str = "chain",
    tags: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    process_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    process_outputs: Callable[[Any], Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator wrapping ``langsmith.traceable``.

    Export is controlled at runtime by ``LANGCHAIN_TRACING_V2`` (see ``configure_tracing_from_settings``).
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        from langsmith import traceable as ls_traceable

        kwargs: dict[str, Any] = {"name": name, "run_type": run_type}
        if tags:
            kwargs["tags"] = list(tags)
        if metadata:
            kwargs["metadata"] = dict(metadata)
        if process_inputs is not None:
            kwargs["process_inputs"] = process_inputs
        if process_outputs is not None:
            kwargs["process_outputs"] = process_outputs
        return ls_traceable(**kwargs)(fn)

    return decorator


# --- Safe process_inputs helpers for tagged spans ---


def _rewrite_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    from memory.mem0_client import format_mem0_for_system

    user_message = str(inputs.get("user_message") or "")
    memories = inputs.get("mem0_memories") or []
    mem0_text = str(inputs.get("mem0_text") or "")
    if not mem0_text.strip() and isinstance(memories, list) and memories:
        mem0_text = format_mem0_for_system(memories)
    facts_count_raw = inputs.get("mem0_facts_count")
    if isinstance(facts_count_raw, int):
        mem0_facts_count = facts_count_raw
    elif isinstance(memories, list):
        mem0_facts_count = len(memories)
    else:
        mem0_facts_count = 0
    recent = inputs.get("recent_messages") or []
    rewrite_skipped = bool(inputs.get("rewrite_skipped", False))
    rewrite_skip_reason = str(inputs.get("rewrite_skip_reason") or "")
    prompt_len = 0
    model_name = str(inputs.get("model_name") or "")
    max_tokens = None
    timeout_seconds = None
    if not rewrite_skipped:
        try:
            from rag.rewrite import build_rewrite_prompt
            from settings.config import get_settings

            settings = get_settings()
            model_name = model_name or (
                settings.REWRITE_MODEL_NAME or settings.OPENAI_MODEL_NAME
            )
            max_tokens = settings.REWRITE_MAX_TOKENS
            timeout_seconds = settings.REWRITE_TIMEOUT_SECONDS
            prompt_len = len(build_rewrite_prompt(user_message, mem0_text, recent))
        except Exception:
            prompt_len = 0
    secrets = _collect_secret_values()
    return {
        "span": "rewrite",
        "user_message": truncate_for_trace(redact_secrets(user_message, secrets)),
        "user_message_len": len(user_message),
        "rewrite.model_name": model_name,
        "rewrite.prompt_len": prompt_len,
        "rewrite.max_tokens": max_tokens,
        "rewrite.timeout_seconds": timeout_seconds,
        "mem0_text_len": len(mem0_text) if not rewrite_skipped else 0,
        "mem0_facts_count": mem0_facts_count if not rewrite_skipped else 0,
        "recent_message_count": len(recent),
        "rewrite_skipped": rewrite_skipped,
        "rewrite_skip_reason": rewrite_skip_reason,
    }


def _rag_router_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    message = str(inputs.get("message") or "")
    rewritten = inputs.get("rewritten_query")
    tools = inputs.get("tools_context")
    mode = inputs.get("mode")
    prompt_len = 0
    model_name = str(inputs.get("model_name") or "")
    max_tokens = None
    timeout_seconds = None
    try:
        from rag.router import build_router_classifier_prompt
        from settings.config import get_settings

        settings = get_settings()
        model_name = model_name or (
            settings.RAG_ROUTER_MODEL_NAME or settings.OPENAI_MODEL_NAME
        )
        max_tokens = settings.RAG_ROUTER_MAX_TOKENS
        timeout_seconds = settings.RAG_ROUTER_TIMEOUT_SECONDS
        prompt_len = len(build_router_classifier_prompt(message, rewritten, tools))
        mode = mode or settings.RAG_ROUTER_MODE
    except Exception:
        pass
    return {
        "span": "rag_router",
        "message_len": len(message),
        "rewritten_query_len": len(str(rewritten)) if rewritten is not None else 0,
        "tools_count": len(tools) if tools is not None else 0,
        "mode": mode,
        "rag_router.model_name": model_name,
        "rag_router.prompt_len": prompt_len,
        "rag_router.mode": mode,
        "rag_router.max_tokens": max_tokens,
        "rag_router.timeout_seconds": timeout_seconds,
    }


def _retrieve_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "span": "retrieve",
        "role_id": str(inputs.get("role_id") or ""),
        "query_len": len(str(inputs.get("query") or "")),
        "top_k": inputs.get("top_k"),
        "second_pass": bool(inputs.get("second_pass")),
    }


def _rerank_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    candidates = inputs.get("candidates") or []
    return {
        "span": "rerank",
        "rerank": True,
        "query_len": len(str(inputs.get("query") or "")),
        "candidate_count": len(candidates),
        "top_k": inputs.get("top_k"),
    }


def _supervisor_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    messages = inputs.get("messages") or []
    system_prompt = str(inputs.get("system_prompt") or "")
    executor = str(inputs.get("executor") or "deepagents_executor")
    executor_reason = str(inputs.get("executor_reason") or "")
    context_budget = inputs.get("context_budget") or {}
    if not isinstance(context_budget, Mapping):
        context_budget = {}
    secrets = _collect_secret_values()
    meta = {
        "span": "supervisor",
        "executor": executor,
        "executor_reason": executor_reason,
        "system_prompt_len": len(system_prompt),
        "mem0_count": 0,
        "rag_chunk_count": 0,
        "budget_truncated": False,
        "message_count": len(messages),
        "system_prompt_preview": truncate_for_trace(
            redact_secrets(system_prompt, secrets),
            limit=200,
        ),
    }
    for key in (
        "system_prompt_len",
        "mem0_count",
        "memory_profile_count",
        "mem0_free_text_count",
        "rag_chunk_count",
        "message_count",
        "message_chars",
        "budget_truncated",
    ):
        if key in context_budget:
            meta[key] = context_budget[key]
    return meta


def _chitchat_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    user_message = str(inputs.get("user_message") or "")
    model_name = str(inputs.get("model_name") or "")
    explicit_use_llm = "use_llm" in inputs
    use_llm = bool(inputs.get("use_llm", False))
    max_tokens = None
    timeout_seconds = None
    try:
        from settings.config import get_settings

        settings = get_settings()
        use_llm = settings.CHITCHAT_USE_LLM if not explicit_use_llm else use_llm
        model_name = model_name or (
            settings.CHITCHAT_MODEL_NAME or settings.OPENAI_MODEL_NAME
        )
        max_tokens = settings.CHITCHAT_MAX_TOKENS
        timeout_seconds = settings.CHITCHAT_TIMEOUT_SECONDS
    except Exception:
        pass
    return {
        "span": "chitchat",
        "executor": "small_chat_executor" if use_llm else "template_executor",
        "chitchat.use_llm": use_llm,
        "chitchat.model_name": model_name if use_llm else "",
        "chitchat.max_tokens": max_tokens if use_llm else None,
        "chitchat.timeout_seconds": timeout_seconds if use_llm else None,
        "user_message": truncate_for_trace(
            redact_secrets(user_message, _collect_secret_values())
        ),
        "user_message_len": len(user_message),
    }


def _guardrails_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    text = str(inputs.get("text") or "")
    direction = str(inputs.get("direction") or "unknown")
    return {
        "span": "guardrails",
        "guardrails.direction": direction,
        "text_len": len(text),
    }


def rewrite_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="rewrite",
        run_type="chain",
        tags=["rewrite"],
        metadata={"span": "rewrite"},
        process_inputs=_rewrite_process_inputs,
    )


def rag_router_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="rag_router",
        run_type="chain",
        tags=["rag_router"],
        metadata={"span": "rag_router"},
        process_inputs=_rag_router_process_inputs,
    )


def retrieve_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="retrieve",
        run_type="retriever",
        tags=["retrieve", "rag"],
        metadata={"span": "retrieve"},
        process_inputs=_retrieve_process_inputs,
    )


def rerank_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="rerank",
        run_type="chain",
        tags=["rerank", "retrieve"],
        metadata={"span": "rerank", "rerank": True},
        process_inputs=_rerank_process_inputs,
    )


def supervisor_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="supervisor",
        run_type="chain",
        tags=["supervisor"],
        metadata={"span": "supervisor"},
        process_inputs=_supervisor_process_inputs,
    )


def chitchat_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="chitchat",
        run_type="chain",
        tags=["chitchat"],
        metadata={"span": "chitchat"},
        process_inputs=_chitchat_process_inputs,
    )


def _inbound_guard_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return _guardrails_process_inputs({**inputs, "direction": "inbound"})


def _outbound_guard_process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return _guardrails_process_inputs({**inputs, "direction": "outbound"})


def inbound_guardrails_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="guardrails_inbound",
        run_type="tool",
        tags=["guardrails", "inbound"],
        metadata={"span": "guardrails", "guardrails.direction": "inbound"},
        process_inputs=_inbound_guard_process_inputs,
    )


def outbound_guardrails_traceable() -> Callable[[Callable[P, R]], Callable[P, R]]:
    return traceable(
        name="guardrails_outbound",
        run_type="tool",
        tags=["guardrails", "outbound"],
        metadata={"span": "guardrails", "guardrails.direction": "outbound"},
        process_inputs=_outbound_guard_process_inputs,
    )
