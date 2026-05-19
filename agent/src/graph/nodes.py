"""LangGraph nodes for the Supervisor main pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import RunnableConfig

from graph.context import GraphContextSchema, request_context_from_runtime
from graph.state import AgentState
from graph.rag_subagent import (
    apply_rag_subagent_merge,
    run_rag_subagent_retrieval,
    should_delegate_rag_subagent,
)
from graph.client_actions import (
    ERROR_PARSE,
    ERROR_TOOL_NOT_ALLOWED,
    build_client_actions_assistant_message,
    parse_client_actions_from_llm,
)
from graph.supervisor import (
    DEFAULT_SUPERVISOR_INSTRUCTIONS,
    build_supervisor_instructions,
    extract_latest_ai_text,
    invoke_supervisor,
)
from guardrails.inbound import check_inbound
from guardrails.outbound import OUTBOUND_SAFE_REPLY, check_outbound
from memory.assembly import build_context
from memory.history import get_rolling_summary, load_thread_messages
from memory.mem0_client import fetch_user_memories, format_mem0_for_system
from memory.post_turn import extract_current_turn_messages, schedule_post_turn_jobs
from rag.retriever import RagChunk
from rag.rewrite import rewrite_node
from rag.router import rag_router_node
from rag.retriever import rag_retrieval_node
from settings.config import get_settings

# EphemeralValue channels only expose the previous step's writes; forward keys still
# needed downstream within the same invoke.
_EPHEMERAL_CARRY_KEYS = (
    "mem0_memories",
    "mem0_text",
    "rolling_summary",
    "rewritten_query",
    "rag_skipped",
    "rag_chunks",
    "system_prompt",
    "inbound_blocked",
    "inbound_block_message",
    "supervisor_draft",
    "outbound_blocked",
    "client_actions",
    "client_actions_error",
)


def _ephemeral_carry(state: AgentState) -> dict[str, object]:
    carried: dict[str, object] = {}
    for key in _EPHEMERAL_CARRY_KEYS:
        if key not in state:
            continue
        value = state[key]
        if value is None:
            continue
        if isinstance(value, (list, str)) and not value:
            continue
        carried[key] = value
    return carried


def _merge_carry(state: AgentState, updates: dict[str, object]) -> dict[str, object]:
    return {**_ephemeral_carry(state), **updates}


def _text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _thread_id(config: RunnableConfig | None) -> str:
    configurable = (config or {}).get("configurable") or {}
    thread_id = _text(configurable.get("thread_id"))
    if not thread_id:
        raise ValueError("configurable.thread_id is required")
    return thread_id


def _extract_user_message(state: AgentState) -> str:
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
        return _merge_carry(state, {"inbound_blocked": False})

    block_message = guard.message or "Message blocked by inbound guardrails."
    return _merge_carry(
        state,
        {
            "inbound_blocked": True,
            "inbound_block_message": block_message,
            "messages": [AIMessage(content=block_message)],
        },
    )


def route_after_inbound(state: AgentState) -> Literal["load_memory", "__end__"]:
    if state.get("inbound_blocked"):
        return "__end__"
    return "load_memory"


def load_memory_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
    config: RunnableConfig,
) -> dict[str, object]:
    """Fetch mem0 and checkpoint history in parallel (thread pool)."""
    ctx = request_context_from_runtime(runtime)
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
    }

    incoming = list(state.get("messages") or [])
    if not incoming and checkpoint_messages:
        updates["messages"] = checkpoint_messages
    elif checkpoint_messages and incoming:
        if len(incoming) == 1 and isinstance(incoming[0], HumanMessage):
            updates["messages"] = [*checkpoint_messages, incoming[0]]

    return _merge_carry(state, updates)


def rewrite_graph_node(state: AgentState) -> dict[str, str]:
    """Delegate to rag.rewrite.rewrite_node with graph state."""
    payload: dict[str, object] = {
        "user_message": _extract_user_message(state),
        "mem0_text": state.get("mem0_text") or "",
        "mem0_memories": state.get("mem0_memories") or [],
        "messages": state.get("messages") or [],
    }
    return _merge_carry(state, rewrite_node(cast(Any, payload)))


def rag_router_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, bool]:
    """Delegate to rag router with tools from request context."""
    ctx = request_context_from_runtime(runtime)
    payload: dict[str, object] = {
        "user_message": _extract_user_message(state),
        "rewritten_query": state.get("rewritten_query"),
        "tools_context": ctx.tools,
    }
    return _merge_carry(state, rag_router_node(cast(Any, payload)))


def rag_retrieval_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, list[RagChunk]]:
    """Delegate to retriever with role_id from request context."""
    ctx = request_context_from_runtime(runtime)
    payload: dict[str, object] = {
        "role_id": ctx.role_id,
        "rewritten_query": state.get("rewritten_query"),
        "rag_skipped": state.get("rag_skipped", False),
    }
    return _merge_carry(state, rag_retrieval_node(cast(Any, payload)))


def route_after_rag_retrieval(
    state: AgentState,
) -> Literal["rag_subagent", "context_assembly"]:
    """Route to RagSubAgent when primary chunks are empty or below score threshold."""
    if should_delegate_rag_subagent(
        rag_skipped=bool(state.get("rag_skipped")),
        rag_chunks=state.get("rag_chunks") or [],
        settings=get_settings(),
    ):
        return "rag_subagent"
    return "context_assembly"


def rag_subagent_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, list[RagChunk]]:
    """Second-pass retrieval; merge and dedupe into ``rag_chunks`` (no third pass)."""
    ctx = request_context_from_runtime(runtime)
    role_id = ctx.role_id
    query = _text(state.get("rewritten_query"))
    primary = list(state.get("rag_chunks") or [])

    if not role_id or not query:
        return _merge_carry(state, {"rag_chunks": primary})

    secondary = run_rag_subagent_retrieval(role_id, query, settings=get_settings())
    merged = apply_rag_subagent_merge(primary, secondary, settings=get_settings())
    return _merge_carry(state, {"rag_chunks": merged})


def context_assembly_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, str]:
    """Assemble dynamic system prompt (K+M+summary+mem0+RAG)."""
    ctx = request_context_from_runtime(runtime)
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
    return _merge_carry(state, {"system_prompt": system_str})


def supervisor_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, list[BaseMessage]]:
    """Run deepagents Supervisor on assembled context; append AI reply to checkpoint messages."""
    ctx = request_context_from_runtime(runtime)
    system_prompt = _text(state.get("system_prompt"))
    instructions = build_supervisor_instructions(
        DEFAULT_SUPERVISOR_INSTRUCTIONS,
        ctx.tools,
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

    if ctx.tools:
        outcome = parse_client_actions_from_llm(reply, ctx.tools)
        if outcome.kind == "client_actions":
            return _merge_carry(
                state,
                {
                    "client_actions": list(outcome.actions),
                    "client_actions_error": None,
                    "supervisor_draft": "",
                },
            )
        if outcome.kind == "error":
            code = outcome.error_code or ERROR_PARSE
            if code == ERROR_TOOL_NOT_ALLOWED:
                user_msg = "该操作未授权，无法调用此外部工具。"
            elif code == ERROR_PARSE:
                user_msg = "无法解析客户端工具指令，请换一种说法或联系管理员。"
            else:
                user_msg = outcome.error_message or "客户端工具指令无效。"
            return _merge_carry(
                state,
                {
                    "client_actions": None,
                    "client_actions_error": {
                        "code": code,
                        "message": outcome.error_message or user_msg,
                    },
                    "supervisor_draft": user_msg,
                },
            )

    if not reply:
        reply = "（无回复）"
    return _merge_carry(
        state,
        {"supervisor_draft": reply, "client_actions": None, "client_actions_error": None},
    )


def route_after_supervisor(
    state: AgentState,
) -> Literal["client_actions_emit", "outbound_guard"]:
    """Skip outbound text guard when structured client_actions are ready."""
    actions = state.get("client_actions")
    if actions:
        return "client_actions_emit"
    return "outbound_guard"


def client_actions_emit_node(state: AgentState) -> dict[str, object]:
    """Persist assistant message with client_actions metadata; no ToolMessage."""
    actions = list(state.get("client_actions") or [])
    message = build_client_actions_assistant_message(actions)
    return _merge_carry(
        state,
        {
            "messages": [message],
            "outbound_blocked": False,
        },
    )


def post_turn_jobs_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
    config: RunnableConfig,
) -> dict[str, object]:
    """Fire-and-forget rolling summary + mem0 write (does not block invoke)."""
    if state.get("inbound_blocked"):
        return _merge_carry(state, {})

    ctx = request_context_from_runtime(runtime)
    thread_id = _thread_id(config)
    turn_messages = extract_current_turn_messages(state.get("messages") or [])
    if not turn_messages:
        return _merge_carry(state, {})

    schedule_post_turn_jobs(
        thread_id=thread_id,
        user_id=ctx.user_id,
        turn_messages=turn_messages,
    )
    return _merge_carry(state, {})


def outbound_guard_node(state: AgentState) -> dict[str, object]:
    """Check full supervisor reply before persisting assistant message to checkpoint."""
    draft = _text(state.get("supervisor_draft")) or "（无回复）"
    guard = check_outbound(draft, settings=get_settings())

    if guard.allowed:
        return _merge_carry(
            state,
            {
                "messages": [AIMessage(content=draft)],
                "outbound_blocked": False,
            },
        )

    safe_reply = guard.message or OUTBOUND_SAFE_REPLY
    return _merge_carry(
        state,
        {
            "messages": [AIMessage(content=safe_reply)],
            "outbound_blocked": True,
        },
    )
