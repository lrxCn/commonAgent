"""Supervisor deep agent factory (built-in tools only; external tools via prompt)."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from contextvars import ContextVar, Token
from typing import Any

from deepagents import create_deep_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph

from gateway.schemas import ToolSpec
from graph.client_actions import supervisor_client_actions_instruction_block
from observability.tracing import attach_run_metadata, supervisor_traceable
from settings.config import Settings, get_settings

_supervisor_agent_override: CompiledStateGraph | None = None
_supervisor_invoke_override: Callable[[str, list[BaseMessage]], list[BaseMessage]] | None = None
_answer_invoke_override: Callable[[str, list[BaseMessage]], str] | None = None
_stream_token_sink: ContextVar[Callable[[str], None] | None] = ContextVar(
    "stream_token_sink",
    default=None,
)

DEFAULT_SUPERVISOR_INSTRUCTIONS = """You are a helpful enterprise assistant.

Answer using the conversation, user preferences, summary, and knowledge excerpts in your instructions.
When knowledge excerpts include [doc:.../chunk:...] citations, reference them when relevant.
Be concise unless the user asks for detail.
The pipeline may run a RagSubAgent second retrieval when primary excerpts are empty or low-confidence; you receive the merged excerpts only — do not request a third search.
External client tools are described below; follow the client_actions JSON contract when the user wants one.
""".strip()


def set_supervisor_agent(agent: CompiledStateGraph | None) -> None:
    """Replace compiled deep agent (tests)."""
    global _supervisor_agent_override
    _supervisor_agent_override = agent


def set_supervisor_invoke(
    fn: Callable[[str, list[BaseMessage]], list[BaseMessage]] | None,
) -> None:
    """Replace supervisor invocation (tests). Pass None to clear."""
    global _supervisor_invoke_override
    _supervisor_invoke_override = fn


def set_answer_invoke(
    fn: Callable[[str, list[BaseMessage]], str] | None,
) -> None:
    """Replace lightweight answer invocation (tests). Pass None to clear."""
    global _answer_invoke_override
    _answer_invoke_override = fn


def reset_supervisor_overrides() -> None:
    set_supervisor_agent(None)
    set_supervisor_invoke(None)
    set_answer_invoke(None)


def set_stream_token_sink(
    sink: Callable[[str], None] | None,
) -> Token[Callable[[str], None] | None]:
    """Install a per-call token sink for true SSE streaming."""
    return _stream_token_sink.set(sink)


def reset_stream_token_sink(token: Token[Callable[[str], None] | None]) -> None:
    """Restore the previous per-call token sink."""
    _stream_token_sink.reset(token)


def emit_stream_token(token: str) -> None:
    """Emit a token to the active streaming sink, if one is installed."""
    sink = _stream_token_sink.get()
    if sink is not None and token:
        sink(token)


class _SupervisorStreamingCallback(BaseCallbackHandler):
    """Bridge LangChain streaming callbacks to the active SSE token sink."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        super().__init__()
        self._sink = sink

    def on_llm_new_token(self, token: str, **_: Any) -> None:
        if token:
            self._sink(token)


def format_external_tools_for_prompt(tools: Sequence[ToolSpec | dict[str, Any]]) -> str:
    """Describe request-scoped external tools for the system prompt (not LangChain tools)."""
    if not tools:
        return ""

    max_chars = max(0, int(get_settings().TOOLS_SCHEMA_MAX_CHARS))
    if max_chars <= 0:
        attach_run_metadata(
            {
                "tools_count": len(tools),
                "tools_schema_len": 0,
                "tools_schema_truncated": True,
            }
        )
        return ""

    lines = ["## External client tools (this turn only)", ""]
    truncated = False
    for item in tools:
        if isinstance(item, ToolSpec):
            spec = item
        else:
            spec = ToolSpec.model_validate(item)
        schema = json.dumps(spec.parameters, ensure_ascii=False)
        approval = "requires approval" if spec.requires_approval else "no approval required"
        line_prefix = f"- **{spec.name}**: {spec.description} ({approval})\n  parameters schema: "
        candidate_line = f"{line_prefix}{schema}"
        candidate_block = "\n".join([*lines, candidate_line])
        if len(candidate_block) <= max_chars:
            lines.append(candidate_line)
            continue
        truncated = True
        remaining = max_chars - len("\n".join([*lines, line_prefix]))
        if remaining > 0:
            suffix = "...[truncated]"
            if remaining > len(suffix):
                schema = f"{schema[: remaining - len(suffix)]}{suffix}"
            else:
                schema = schema[:remaining]
            lines.append(f"{line_prefix}{schema}")
        break

    block = "\n".join(lines)
    if max_chars > 0 and len(block) > max_chars:
        block = block[:max_chars]
        truncated = True
    attach_run_metadata(
        {
            "tools_count": len(tools),
            "tools_schema_len": len(block),
            "tools_schema_truncated": truncated,
        }
    )
    return block


def build_supervisor_instructions(
    base: str,
    external_tools: Sequence[ToolSpec | dict[str, Any]] | None,
) -> str:
    """Base supervisor instructions plus external tool descriptions."""
    parts = [base.strip()] if base.strip() else []
    tools_block = format_external_tools_for_prompt(external_tools or [])
    if tools_block:
        parts.append(tools_block)
        parts.append(supervisor_client_actions_instruction_block())
    return "\n\n".join(parts)


def _create_chat_model(settings: Settings) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": settings.OPENAI_MODEL_NAME,
        "api_key": settings.OPENAI_API_KEY,
        "base_url": settings.OPENAI_BASE_URL,
        "temperature": 0.2,
    }
    sink = _stream_token_sink.get()
    if sink is not None:
        kwargs["streaming"] = True
        kwargs["callbacks"] = [_SupervisorStreamingCallback(sink)]
    return ChatOpenAI(**kwargs)


def build_supervisor_agent(
    *,
    system_prompt: str,
    model: BaseChatModel | str | None = None,
) -> CompiledStateGraph:
    """Create a deep agent with built-in tools only (no external ToolSpec bindings)."""
    settings = get_settings()
    resolved_model = model if model is not None else _create_chat_model(settings)
    return create_deep_agent(
        model=resolved_model,
        tools=[],
        system_prompt=system_prompt,
        interrupt_on={},
        name="supervisor",
    )


def _get_supervisor_agent(system_prompt: str) -> CompiledStateGraph:
    if _supervisor_agent_override is not None:
        return _supervisor_agent_override
    return build_supervisor_agent(system_prompt=system_prompt)


@supervisor_traceable()
def invoke_supervisor(
    system_prompt: str,
    messages: list[BaseMessage],
    *,
    executor: str = "deepagents_executor",
    executor_reason: str = "",
    context_budget: dict[str, object] | None = None,
) -> list[BaseMessage]:
    """Run the supervisor and return the resulting message list."""
    del context_budget  # tracing metadata only
    del executor, executor_reason  # tracing metadata only
    if _supervisor_invoke_override is not None:
        return _supervisor_invoke_override(system_prompt, messages)

    agent = _get_supervisor_agent(system_prompt)
    result = agent.invoke({"messages": messages})
    out = result.get("messages")
    if not out:
        return [AIMessage(content="")]
    return list(out)


@supervisor_traceable()
def invoke_answer_executor(
    system_prompt: str,
    messages: list[BaseMessage],
    *,
    executor: str = "rag_answer_executor",
    executor_reason: str = "",
    context_budget: dict[str, object] | None = None,
) -> str:
    """Run a plain ChatOpenAI answer path without deepagents middleware."""
    del context_budget  # tracing metadata only
    del executor, executor_reason  # tracing metadata only
    if _answer_invoke_override is not None:
        return _answer_invoke_override(system_prompt, messages).strip()

    settings = get_settings()
    llm = _create_chat_model(settings)
    response = llm.invoke([SystemMessage(content=system_prompt), *messages])
    return str(response.content).strip()


def extract_latest_ai_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = message.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                return "".join(parts).strip()
    return ""
