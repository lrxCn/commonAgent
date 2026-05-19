"""Supervisor deep agent factory (built-in tools only; external tools via prompt)."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from deepagents import create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph.state import CompiledStateGraph

from gateway.schemas import ToolSpec
from settings.config import Settings, get_settings

_supervisor_agent_override: CompiledStateGraph | None = None
_supervisor_invoke_override: Callable[[str, list[BaseMessage]], list[BaseMessage]] | None = None

DEFAULT_SUPERVISOR_INSTRUCTIONS = """You are a helpful enterprise assistant.

Answer using the conversation, user preferences, summary, and knowledge excerpts in your instructions.
When knowledge excerpts include [doc:.../chunk:...] citations, reference them when relevant.
Be concise unless the user asks for detail.
The pipeline may run a RagSubAgent second retrieval when primary excerpts are empty or low-confidence; you receive the merged excerpts only — do not request a third search.
External client tools are described below; when the user clearly wants a client action, describe what would happen — structured client_actions output is added in a later task.
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


def reset_supervisor_overrides() -> None:
    set_supervisor_agent(None)
    set_supervisor_invoke(None)


def format_external_tools_for_prompt(tools: Sequence[ToolSpec | dict[str, Any]]) -> str:
    """Describe request-scoped external tools for the system prompt (not LangChain tools)."""
    if not tools:
        return ""

    lines = ["## External client tools (this turn only)", ""]
    for item in tools:
        if isinstance(item, ToolSpec):
            spec = item
        else:
            spec = ToolSpec.model_validate(item)
        schema = json.dumps(spec.parameters, ensure_ascii=False)
        approval = "requires approval" if spec.requires_approval else "no approval required"
        lines.append(
            f"- **{spec.name}**: {spec.description} ({approval})\n  parameters schema: {schema}"
        )
    return "\n".join(lines)


def build_supervisor_instructions(
    base: str,
    external_tools: Sequence[ToolSpec | dict[str, Any]] | None,
) -> str:
    """Base supervisor instructions plus external tool descriptions."""
    parts = [base.strip()] if base.strip() else []
    tools_block = format_external_tools_for_prompt(external_tools or [])
    if tools_block:
        parts.append(tools_block)
    return "\n\n".join(parts)


def _create_chat_model(settings: Settings) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.OPENAI_MODEL_NAME,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0.2,
    )


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


def invoke_supervisor(system_prompt: str, messages: list[BaseMessage]) -> list[BaseMessage]:
    """Run the supervisor and return the resulting message list."""
    if _supervisor_invoke_override is not None:
        return _supervisor_invoke_override(system_prompt, messages)

    agent = _get_supervisor_agent(system_prompt)
    result = agent.invoke({"messages": messages})
    out = result.get("messages")
    if not out:
        return [AIMessage(content="")]
    return list(out)


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
