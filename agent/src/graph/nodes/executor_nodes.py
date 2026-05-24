"""Executor graph adapters."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from contracts.context import ContextBundle
from contracts.events import ObservabilityEventType
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
from graph.state import AgentState
from graph.supervisor import extract_latest_ai_text, invoke_answer_executor, invoke_supervisor
from observability.path_contract import mark_fast_path, update_path_component
from observability.tracing import emit_event

from .common import extract_user_message, merge_carry, text

FACT_UPDATE_CONFIRMATION = "已收到，我会把这个信息作为你的偏好/事实参考。"


def fact_update_confirm_node(state: AgentState) -> dict[str, object]:
    """Append a deterministic confirmation without rewrite/RAG/Supervisor."""
    if state.get("policy_fast_path_allowed") is not True:
        raise RuntimeError("fact_update_confirm requires policy_fast_path_allowed")
    path_metrics = mark_fast_path(state.get("path_metrics"), enabled=True)
    emit_event(
        ObservabilityEventType.EXECUTOR_CHOSEN,
        {
            "executor": "template_executor",
            "executor_reason": "turn_type_fact_update",
        }
    )
    return merge_carry(
        state,
        {
            "messages": [AIMessage(content=FACT_UPDATE_CONFIRMATION)],
            "supervisor_draft": FACT_UPDATE_CONFIRMATION,
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
            elif code == ERROR_PARSE:
                user_msg = "无法解析客户端工具指令，请换一种说法或联系管理员。"
            else:
                user_msg = outcome.error_message or "客户端工具指令无效。"
            return merge_carry(
                state,
                {
                    **base_updates,
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
