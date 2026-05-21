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
from graph.chitchat_executor import chitchat_reply
from graph.supervisor import (
    DEFAULT_SUPERVISOR_INSTRUCTIONS,
    build_supervisor_instructions,
    extract_latest_ai_text,
    invoke_supervisor,
)
from graph.turn_type import classify_turn_type
from guardrails.inbound import check_inbound
from guardrails.outbound import OUTBOUND_SAFE_REPLY, check_outbound
from memory.assembly import build_context
from memory.history import get_rolling_summary, load_thread_messages
from memory.mem0_client import fetch_user_memories
from observability.path_contract import (
    finalize_path_metrics,
    mark_fast_path,
    mark_post_turn_schedule,
    new_path_metrics,
    update_path_component,
)
from observability.tracing import attach_run_metadata, build_path_contract_trace_metadata
from memory.post_turn import extract_current_turn_messages, schedule_post_turn_jobs
from rag.retriever import RagChunk
from rag.rewrite import rewrite_node, should_rewrite
from rag.router import RuleDecision, classify_with_rules, rag_router_node
from rag.retriever import rag_retrieval_node
from settings.config import get_settings

# EphemeralValue channels only expose the previous step's writes; forward keys still
# needed downstream within the same invoke.
_EPHEMERAL_CARRY_KEYS = (
    "mem0_memories",
    "rolling_summary",
    "turn_type",
    "turn_type_reason",
    "path_metrics",
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

FACT_UPDATE_CONFIRMATION = "已收到，我会把这个信息作为你的偏好/事实参考。"


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
    return _extract_user_message_from_messages(messages)


def _extract_user_message_from_messages(messages: list[BaseMessage]) -> str:
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
        "rolling_summary": rolling_summary,
    }

    incoming = list(state.get("messages") or [])
    if not incoming and checkpoint_messages:
        updates["messages"] = checkpoint_messages
    elif checkpoint_messages and incoming:
        if len(incoming) == 1 and isinstance(incoming[0], HumanMessage):
            updates["messages"] = [*checkpoint_messages, incoming[0]]

    classify_messages = cast(list[BaseMessage], updates.get("messages") or incoming)
    decision = classify_turn_type(
        _extract_user_message_from_messages(classify_messages),
        tools_context=ctx.tools,
    )
    updates["turn_type"] = decision.turn_type.value
    updates["turn_type_reason"] = decision.reason
    updates["path_metrics"] = new_path_metrics(
        turn_type=decision.turn_type.value,
        turn_type_reason=decision.reason,
    )
    attach_run_metadata(
        {
            "turn_type": decision.turn_type.value,
            "turn_type_reason": decision.reason,
        }
    )
    return _merge_carry(state, updates)


def route_after_load_memory(
    state: AgentState,
) -> Literal["fact_update_confirm", "chitchat_reply", "rewrite"]:
    """Route fact updates/chitchat to lightweight executors after turn classification."""
    if state.get("turn_type") == "fact_update":
        return "fact_update_confirm"
    if state.get("turn_type") == "chitchat":
        return "chitchat_reply"
    return "rewrite"


def fact_update_confirm_node(state: AgentState) -> dict[str, object]:
    """Append a deterministic confirmation without rewrite/RAG/Supervisor."""
    path_metrics = mark_fast_path(state.get("path_metrics"), enabled=True)
    return _merge_carry(
        state,
        {
            "messages": [AIMessage(content=FACT_UPDATE_CONFIRMATION)],
            "supervisor_draft": FACT_UPDATE_CONFIRMATION,
            "client_actions": None,
            "client_actions_error": None,
            "outbound_blocked": False,
            "path_metrics": path_metrics,
        },
    )


def chitchat_reply_node(state: AgentState) -> dict[str, object]:
    """Append a lightweight chitchat reply without rewrite/RAG/deepagents."""
    user_message = _extract_user_message(state)
    outcome = chitchat_reply(user_message)
    path_metrics = mark_fast_path(state.get("path_metrics"), enabled=True)
    path_metrics = update_path_component(
        path_metrics,
        "supervisor",
        should_call=outcome["executor"] == "small_chat_executor",
        called=outcome["executor"] == "small_chat_executor",
    )
    return _merge_carry(
        state,
        {
            "messages": [AIMessage(content=outcome["reply"])],
            "supervisor_draft": outcome["reply"],
            "client_actions": None,
            "client_actions_error": None,
            "outbound_blocked": False,
            "path_metrics": path_metrics,
        },
    )


def rewrite_graph_node(state: AgentState) -> dict[str, object]:
    """Delegate to rag.rewrite.rewrite_node with graph state."""
    user_message = _extract_user_message(state)
    messages = list(state.get("messages") or [])
    recent_messages = list(messages[:-1]) if messages else []
    settings = get_settings()
    use_skip = settings.REWRITE_SKIP_ENABLED and not settings.REWRITE_FORCE
    should_call, _reason = should_rewrite(
        user_message,
        recent_messages=recent_messages,
        mem0_memories=list(state.get("mem0_memories") or []),
    )
    called = bool(user_message) and (should_call or not use_skip)
    payload: dict[str, object] = {
        "user_message": user_message,
        "mem0_memories": state.get("mem0_memories") or [],
        "messages": messages,
    }
    updates = rewrite_node(cast(Any, payload))
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "rewrite",
        should_call=should_call,
        called=called,
    )
    return _merge_carry(state, {**updates, "path_metrics": path_metrics})


def rag_router_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Delegate to rag router with tools from request context."""
    ctx = request_context_from_runtime(runtime)
    message = _extract_user_message(state)
    rewritten = state.get("rewritten_query")
    settings = get_settings()
    rule_decision = classify_with_rules(message, rewritten, ctx.tools)
    should_call = (
        rule_decision is RuleDecision.UNCERTAIN
        and settings.RAG_ROUTER_MODE == "hybrid"
    )
    payload: dict[str, object] = {
        "user_message": message,
        "rewritten_query": rewritten,
        "tools_context": ctx.tools,
    }
    updates = rag_router_node(cast(Any, payload))
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "rag_router",
        should_call=should_call,
        called=should_call,
    )
    return _merge_carry(state, {**updates, "path_metrics": path_metrics})


def rag_retrieval_graph_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Delegate to retriever with role_id from request context."""
    ctx = request_context_from_runtime(runtime)
    should_call = not bool(state.get("rag_skipped", False))
    payload: dict[str, object] = {
        "role_id": ctx.role_id,
        "rewritten_query": state.get("rewritten_query"),
        "rag_skipped": state.get("rag_skipped", False),
    }
    updates = rag_retrieval_node(cast(Any, payload))
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "rag",
        should_call=should_call,
        called=should_call,
    )
    return _merge_carry(state, {**updates, "path_metrics": path_metrics})


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
) -> dict[str, object]:
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
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "supervisor",
        should_call=True,
        called=True,
    )

    if ctx.tools:
        outcome = parse_client_actions_from_llm(reply, ctx.tools)
        if outcome.kind == "client_actions":
            return _merge_carry(
                state,
                {
                    "path_metrics": path_metrics,
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
                    "path_metrics": path_metrics,
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
        {
            "path_metrics": path_metrics,
            "supervisor_draft": reply,
            "client_actions": None,
            "client_actions_error": None,
        },
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

    finalized_metrics = finalize_path_metrics(state.get("path_metrics"))

    ctx = request_context_from_runtime(runtime)
    thread_id = _thread_id(config)
    turn_messages = extract_current_turn_messages(state.get("messages") or [])
    if not turn_messages:
        metrics = mark_post_turn_schedule(finalized_metrics, scheduled=False)
        attach_run_metadata(build_path_contract_trace_metadata(metrics))
        return _merge_carry(state, {"path_metrics": metrics})

    try:
        schedule_post_turn_jobs(
            thread_id=thread_id,
            user_id=ctx.user_id,
            turn_messages=turn_messages,
        )
    except Exception as exc:
        metrics = mark_post_turn_schedule(
            finalized_metrics,
            scheduled=False,
            error=type(exc).__name__,
        )
        attach_run_metadata(build_path_contract_trace_metadata(metrics))
        return _merge_carry(state, {"path_metrics": metrics})

    metrics = mark_post_turn_schedule(finalized_metrics, scheduled=True)
    attach_run_metadata(build_path_contract_trace_metadata(metrics))
    return _merge_carry(state, {"path_metrics": metrics})


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
