"""Executor graph adapters."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from contracts.context import ContextBundle
from contracts.events import ObservabilityEventType
from contracts.execution import ExecutorDecision
from contracts.memory_query_polish import build_polish_input
from graph.chitchat_executor import chitchat_reply
from graph.client_actions import (
    ERROR_PARSE,
    ERROR_TOOL_NOT_ALLOWED,
    build_client_actions_assistant_message,
    parse_client_actions_from_llm,
)
from graph.context import GraphContextSchema, request_context_from_runtime
from graph.executors import (
    ExecutorType,
    build_simple_client_action,
    choose_executor,
    executor_trace_metadata,
)
from graph.rag_subagent import max_chunk_score
from graph.state import AgentState
from graph.supervisor import extract_latest_ai_text, invoke_answer_executor, invoke_supervisor
from intent.fallback import memory_query_fallback_decision, tool_fallback_decision
from memory.query import MemoryQueryResult, answer_memory_query, memory_query_trace_metadata
from memory.query_polish import polish_memory_query_reply
from memory.structured_record import (
    format_structured_memory_confirmation,
    legacy_fact_update_confirmation,
)
from observability.path_contract import (
    ensure_path_metrics,
    mark_fast_path,
    mark_memory_write_mode,
    record_fallback_decision,
    update_path_component,
)
from observability.tracing import emit_event
from settings.config import get_settings

from .common import extract_user_message, merge_carry, text

FACT_UPDATE_CONFIRMATION = legacy_fact_update_confirmation()
NO_RAG_SOURCE_REPLY = "知识库未找到可靠来源，我不能基于内部知识库给出确定答案。你可以补充更多关键词或联系管理员补充资料。"


def fact_update_confirm_node(state: AgentState) -> dict[str, object]:
    """Append a deterministic confirmation without rewrite/RAG/Supervisor."""
    if state.get("policy_fast_path_allowed") is not True:
        raise RuntimeError("fact_update_confirm requires policy_fast_path_allowed")
    record = state.get("memory_write_record")
    if record is None:
        raise RuntimeError("fact_update_confirm requires memory_write_record")
    confirmation = format_structured_memory_confirmation(record)
    path_metrics = mark_fast_path(state.get("path_metrics"), enabled=True)
    path_metrics = mark_memory_write_mode(
        path_metrics,
        mode="structured",
        attribute=record.attribute,
    )
    emit_event(
        ObservabilityEventType.EXECUTOR_CHOSEN,
        {
            "executor": "template_executor",
            "executor_reason": "turn_type_fact_update",
            "memory_write.mode": "structured",
            "memory_write.record.attribute": record.attribute,
            "memory_write.extraction_method": record.extraction_method,
        },
    )
    return merge_carry(
        state,
        {
            "messages": [AIMessage(content=confirmation)],
            "supervisor_draft": confirmation,
            "executor": "template_executor",
            "executor_reason": "turn_type_fact_update",
            "client_actions": None,
            "client_actions_error": None,
            "outbound_blocked": False,
            "path_metrics": path_metrics,
        },
    )


def chitchat_reply_node(state: AgentState) -> dict[str, object]:
    """Append a lightweight chitchat reply without rewrite/RAG/deepagents."""
    outcome = chitchat_reply(extract_user_message(state))
    path_metrics = mark_fast_path(state.get("path_metrics"), enabled=True)
    path_metrics = update_path_component(
        path_metrics,
        "supervisor",
        should_call=outcome["executor"] == "small_chat_executor",
        called=outcome["executor"] == "small_chat_executor",
    )
    return merge_carry(
        state,
        {
            "messages": [AIMessage(content=outcome["reply"])],
            "supervisor_draft": outcome["reply"],
            "executor": outcome["executor"],
            "executor_reason": "turn_type_chitchat",
            "client_actions": None,
            "client_actions_error": None,
            "outbound_blocked": False,
            "path_metrics": path_metrics,
        },
    )


def memory_query_reply_node(state: AgentState) -> dict[str, object]:
    """Answer memory read queries without RAG, deepagents, or mem0 writes."""
    decision = choose_executor(
        turn_type="memory_query",
        user_message=extract_user_message(state),
    )
    result = answer_memory_query(
        extract_user_message(state),
        user_memories=state.get("user_memories") or [],
        messages=state.get("messages") or [],
    )
    path_metrics = ensure_path_metrics(state.get("path_metrics"))
    path_metrics["turn_type"] = "memory_query"
    path_metrics["turn_type_reason"] = decision.reason
    path_metrics = mark_fast_path(path_metrics, enabled=True)
    fallback_decision = memory_query_fallback_decision(result)
    if fallback_decision is not None:
        path_metrics = record_fallback_decision(path_metrics, fallback_decision)
        emit_event(
            ObservabilityEventType.FALLBACK_TRIGGERED,
            fallback_decision.to_trace_dict(),
        )
    emit_event(
        ObservabilityEventType.EXECUTOR_CHOSEN,
        {
            **executor_trace_metadata(decision),
            **memory_query_trace_metadata(result),
        },
    )
    return merge_carry(
        state,
        {
            "memory_query_result": result,
            "supervisor_draft": result.reply,
            "executor": decision.executor.value,
            "executor_reason": decision.reason,
            "client_actions": None,
            "client_actions_error": None,
            "outbound_blocked": False,
            "path_metrics": path_metrics,
        },
    )


def memory_query_polish_node(state: AgentState) -> dict[str, object]:
    """Append the final memory_query assistant reply after optional small-model polish."""
    raw_result = state.get("memory_query_result")
    if not isinstance(raw_result, MemoryQueryResult):
        msg = "memory_query_polish requires memory_query_result from memory_query_reply"
        raise RuntimeError(msg)

    polish_input = build_polish_input(extract_user_message(state), raw_result)
    polish_outcome = polish_memory_query_reply(polish_input)

    path_metrics = dict(state.get("path_metrics") or {})
    settings = get_settings()
    path_metrics["memory_query_polish.enabled"] = settings.MEMORY_QUERY_POLISH_USE_LLM
    path_metrics["memory_query_polish.used_llm"] = polish_outcome.used_llm
    path_metrics["memory_query_polish.fallback_reason"] = polish_outcome.fallback_reason
    path_metrics["memory_query_polish.changed"] = polish_outcome.changed

    return merge_carry(
        state,
        {
            "messages": [AIMessage(content=polish_outcome.reply)],
            "supervisor_draft": polish_outcome.reply,
            "path_metrics": path_metrics,
        },
    )


def supervisor_node(
    state: AgentState,
    runtime: Runtime[GraphContextSchema],
) -> dict[str, object]:
    """Route to a lightweight executor or deepagents, then prepare the assistant output."""
    ctx = request_context_from_runtime(runtime)
    bundle = state.get("context_bundle")
    if not isinstance(bundle, ContextBundle):
        raise RuntimeError("context_bundle is required before supervisor execution")

    full_system = bundle.system_prompt
    model_messages = bundle.messages
    context_budget = bundle.budget_metadata()
    decision = choose_executor(
        turn_type=text(state.get("turn_type")),
        user_message=extract_user_message(state),
        rewritten_query=state.get("rewritten_query"),
        rag_skipped=bool(state.get("rag_skipped", False)),
        rag_chunks=state.get("rag_chunks") or [],
        tools=ctx.tools,
    )
    if _should_use_no_source_reply(state):
        decision = ExecutorDecision(ExecutorType.TEMPLATE, "rag_no_reliable_source")
    emit_event(
        ObservabilityEventType.EXECUTOR_CHOSEN,
        executor_trace_metadata(
            decision,
            rag_chunks=state.get("rag_chunks") or [],
            tools=ctx.tools,
        )
    )

    calls_model = decision.executor in {
        ExecutorType.RAG_ANSWER,
        ExecutorType.DEEPAGENTS,
    }
    path_metrics = update_path_component(
        state.get("path_metrics"),
        "supervisor",
        should_call=calls_model,
        called=calls_model,
    )
    base_updates: dict[str, object] = {
        "path_metrics": path_metrics,
        "executor": decision.executor.value,
        "executor_reason": decision.reason,
    }

    if decision.executor is ExecutorType.ACTION:
        action = build_simple_client_action(extract_user_message(state), ctx.tools)
        if action is not None:
            return merge_carry(
                state,
                {
                    **base_updates,
                    "client_actions": [action],
                    "client_actions_error": None,
                    "supervisor_draft": "",
                },
            )
        fallback_decision = tool_fallback_decision("tool_unavailable")
        path_metrics = record_fallback_decision(path_metrics, fallback_decision)
        emit_event(
            ObservabilityEventType.FALLBACK_TRIGGERED,
            fallback_decision.to_trace_dict(),
        )
        return merge_carry(
            state,
            {
                **base_updates,
                "path_metrics": path_metrics,
                "client_actions": None,
                "client_actions_error": {
                    "code": ERROR_TOOL_NOT_ALLOWED,
                    "message": "No matching client tool arguments could be built.",
                },
                "supervisor_draft": "该操作当前不可用或缺少必要参数，无法调用外部工具。",
            },
        )

    if decision.executor is ExecutorType.TEMPLATE and decision.reason == "rag_no_reliable_source":
        return merge_carry(
            state,
            {
                **base_updates,
                "executor": decision.executor.value,
                "executor_reason": decision.reason,
                "supervisor_draft": NO_RAG_SOURCE_REPLY,
                "client_actions": None,
                "client_actions_error": None,
            },
        )

    if decision.executor is ExecutorType.RAG_ANSWER:
        reply = invoke_answer_executor(
            full_system,
            model_messages,
            executor=decision.executor.value,
            executor_reason=decision.reason,
            context_budget=context_budget,
        )
    else:
        result_messages = invoke_supervisor(
            full_system,
            model_messages,
            executor=decision.executor.value,
            executor_reason=decision.reason,
            context_budget=context_budget,
        )
        reply = extract_latest_ai_text(result_messages)

    if ctx.tools:
        outcome = parse_client_actions_from_llm(reply, ctx.tools)
        if outcome.kind == "client_actions":
            return merge_carry(
                state,
                {
                    **base_updates,
                    "client_actions": list(outcome.actions),
                    "client_actions_error": None,
                    "supervisor_draft": "",
                },
            )
        if outcome.kind == "error":
            code = outcome.error_code or ERROR_PARSE
            if code == ERROR_TOOL_NOT_ALLOWED:
                user_msg = "该操作未授权，无法调用此外部工具。"
                fallback_decision = tool_fallback_decision("tool_not_allowed")
            elif code == ERROR_PARSE:
                user_msg = "无法解析客户端工具指令，请换一种说法或联系管理员。"
                fallback_decision = tool_fallback_decision(
                    "schema_invalid",
                    final_route=decision.executor.value,
                )
            else:
                user_msg = outcome.error_message or "客户端工具指令无效。"
                fallback_decision = tool_fallback_decision(
                    code,
                    final_route=decision.executor.value,
                )
            path_metrics = record_fallback_decision(path_metrics, fallback_decision)
            emit_event(
                ObservabilityEventType.FALLBACK_TRIGGERED,
                fallback_decision.to_trace_dict(),
            )
            return merge_carry(
                state,
                {
                    **base_updates,
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
    return merge_carry(
        state,
        {
            **base_updates,
            "supervisor_draft": reply,
            "client_actions": None,
            "client_actions_error": None,
        },
    )


def _should_use_no_source_reply(state: AgentState) -> bool:
    if text(state.get("turn_type")) != "knowledge_query":
        return False
    if bool(state.get("rag_skipped", False)):
        return False
    chunks = list(state.get("rag_chunks") or [])
    if not chunks:
        return True
    return max_chunk_score(chunks) < get_settings().RAG_SUBAGENT_SCORE_THRESHOLD


def client_actions_emit_node(state: AgentState) -> dict[str, object]:
    """Persist assistant message with client_actions metadata; no ToolMessage."""
    actions = list(state.get("client_actions") or [])
    emit_event(
        ObservabilityEventType.CLIENT_ACTIONS_PARSED,
        {"client_actions.count": len(actions), "client_actions.error": ""},
    )
    message = build_client_actions_assistant_message(actions)
    return merge_carry(
        state,
        {
            "messages": [message],
            "outbound_blocked": False,
        },
    )
