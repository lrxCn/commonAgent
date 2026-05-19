"""LangGraph nodes for the Supervisor main pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import RunnableConfig

from gateway.schemas import RequestContext, ToolSpec
from graph.state import AgentState
from graph.supervisor import (
    DEFAULT_SUPERVISOR_INSTRUCTIONS,
    build_supervisor_instructions,
    extract_latest_ai_text,
    invoke_supervisor,
)
from guardrails.inbound import check_inbound
from memory.assembly import build_context
from memory.history import get_rolling_summary, load_thread_messages
from memory.mem0_client import fetch_user_memories, format_mem0_for_system
from rag.retriever import RagChunk
from rag.rewrite import rewrite_node
from rag.router import rag_router_node
from rag.retriever import rag_retrieval_node
from settings.config import get_settings


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def get_request_context(state: AgentState, config: RunnableConfig | None = None) -> RequestContext:
    """Resolve per-turn request context (invoke input is authoritative)."""
    raw = state.get("context")
    if isinstance(raw, RequestContext):
        return raw
    if isinstance(raw, dict) and raw:
        return RequestContext.model_validate(raw)

    configurable = (config or {}).get("configurable") or {}
    nested = configurable.get("context")
    if isinstance(nested, dict) and nested:
        return RequestContext.model_validate(nested)
    msg = "context is required on each invoke (user_id, role_id, tools)"
    raise ValueError(msg)


def _thread_id(config: RunnableConfig | None) -> str:
    configurable = (config or {}).get("configurable") or {}
    thread_id = _text(configurable.get("thread_id"))
    if not thread_id:
        raise ValueError("configurable.thread_id is required")
    return thread_id


def _extract_user_message(state: AgentState) -> str:
    if state.get("user_message"):
        return _text(state["user_message"])

    messages = state.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return _text(message.content)
    return ""


def inbound_guard_node(state: AgentState) -> dict[str, object]:
    """Run inbound guardrails on the current user message."""
    text = _extract_user_message(state)
    guard = check_inbound(text, settings=get_settings())
    if guard.allowed:
        return {"inbound_blocked": False, "user_message": text}

    block_message = guard.message or "Message blocked by inbound guardrails."
    return {
        "inbound_blocked": True,
        "inbound_block_message": block_message,
        "messages": [AIMessage(content=block_message)],
    }


def route_after_inbound(state: AgentState) -> Literal["load_memory", "__end__"]:
    if state.get("inbound_blocked"):
        return "__end__"
    return "load_memory"


def load_memory_node(state: AgentState, config: RunnableConfig) -> dict[str, object]:
    """Fetch mem0 and checkpoint history in parallel (thread pool)."""
    ctx = get_request_context(state, config)
    thread_id = _thread_id(config)

    with ThreadPoolExecutor(max_workers=3) as pool:
        mem0_future = pool.submit(fetch_user_memories, ctx.user_id)
        history_future = pool.submit(load_thread_messages, thread_id)
        summary_future = pool.submit(get_rolling_summary, thread_id)
        mem0_memories = mem0_future.result()
        checkpoint_messages = history_future.result()
        rolling_summary = summary_future.result()

    updates: dict[str, object] = {
        "mem0_memories": mem0_memories,
        "mem0_text": format_mem0_for_system(mem0_memories),
        "rolling_summary": rolling_summary,
        "context": ctx.model_dump(),
    }

    incoming = list(state.get("messages") or [])
    if not incoming and checkpoint_messages:
        updates["messages"] = checkpoint_messages
    elif checkpoint_messages and incoming:
        if len(incoming) == 1 and isinstance(incoming[0], HumanMessage):
            updates["messages"] = [*checkpoint_messages, incoming[0]]

    return updates


def rewrite_graph_node(state: AgentState) -> dict[str, str]:
    """Delegate to rag.rewrite.rewrite_node with graph state."""
    payload: dict[str, object] = {
        "user_message": _extract_user_message(state),
        "mem0_text": state.get("mem0_text") or "",
        "mem0_memories": state.get("mem0_memories") or [],
        "messages": state.get("messages") or [],
    }
    return rewrite_node(cast(Any, payload))


def rag_router_graph_node(state: AgentState, config: RunnableConfig) -> dict[str, bool]:
    """Delegate to rag router with tools from request context."""
    ctx = get_request_context(state, config)
    payload: dict[str, object] = {
        "user_message": _extract_user_message(state),
        "rewritten_query": state.get("rewritten_query"),
        "tools_context": ctx.tools,
    }
    return rag_router_node(cast(Any, payload))


def rag_retrieval_graph_node(state: AgentState, config: RunnableConfig) -> dict[str, list[RagChunk]]:
    """Delegate to retriever with role_id from request context."""
    ctx = get_request_context(state, config)
    payload: dict[str, object] = {
        "role_id": ctx.role_id,
        "rewritten_query": state.get("rewritten_query"),
        "rag_skipped": state.get("rag_skipped", False),
    }
    return rag_retrieval_node(cast(Any, payload))


def context_assembly_node(state: AgentState, config: RunnableConfig) -> dict[str, str]:
    """Assemble dynamic system prompt (K+M+summary+mem0+RAG)."""
    ctx = get_request_context(state, config)
    instructions = build_supervisor_instructions(
        DEFAULT_SUPERVISOR_INSTRUCTIONS,
        ctx.tools,
    )
    system_str, _ = build_context(
        mem0=list(state.get("mem0_memories") or []),
        summary=state.get("rolling_summary"),
        rag_chunks=state.get("rag_chunks") or [],
        instructions=instructions,
        messages=state.get("messages") or [],
        current_human=_extract_user_message(state) or None,
    )
    return {"system_prompt": system_str}


def supervisor_node(state: AgentState) -> dict[str, list[BaseMessage]]:
    """Run deepagents Supervisor on assembled context; append AI reply to checkpoint messages."""
    system_prompt = _text(state.get("system_prompt"))
    ctx_tools: list[ToolSpec] = []
    raw_ctx = state.get("context")
    if isinstance(raw_ctx, dict):
        tools_raw = raw_ctx.get("tools") or []
        ctx_tools = [ToolSpec.model_validate(t) for t in tools_raw]

    instructions = build_supervisor_instructions(
        DEFAULT_SUPERVISOR_INSTRUCTIONS,
        ctx_tools,
    )
    _, model_messages = build_context(
        mem0=list(state.get("mem0_memories") or []),
        summary=state.get("rolling_summary"),
        rag_chunks=state.get("rag_chunks") or [],
        instructions=instructions,
        messages=state.get("messages") or [],
        current_human=_extract_user_message(state) or None,
    )

    full_system = system_prompt or instructions
    result_messages = invoke_supervisor(full_system, model_messages)
    reply = extract_latest_ai_text(result_messages)
    if not reply:
        reply = "（无回复）"
    return {"messages": [AIMessage(content=reply)]}
