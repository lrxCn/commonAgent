"""Chat turn: invoke Supervisor graph, return SSE text stream or client_actions JSON."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from gateway.schemas import ChatRequest, ChatResponse, ClientAction
from graph.context import graph_context_from_request

_graph_override: CompiledStateGraph | None = None

# Characters per SSE token event (full reply is produced after graph invoke).
_SSE_CHUNK_SIZE = 32


@dataclass(frozen=True)
class ChatTurnOutcome:
    """Result of a single graph invoke for Gateway routing."""

    kind: Literal["text", "client_actions"]
    text: str | None = None
    client_actions: list[ClientAction] | None = None


def set_chat_graph(graph: CompiledStateGraph | None) -> None:
    """Replace compiled graph used by Gateway (tests)."""
    global _graph_override
    _graph_override = graph


def reset_chat_graph() -> None:
    set_chat_graph(None)


def get_chat_graph() -> CompiledStateGraph:
    if _graph_override is not None:
        return _graph_override
    from graph.build import compile_graph

    return compile_graph()


def format_sse_event(payload: dict[str, Any]) -> str:
    """Serialize one Server-Sent Events ``data:`` frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def iter_token_chunks(text: str, *, chunk_size: int = _SSE_CHUNK_SIZE) -> Iterator[str]:
    """Split assistant text into stream chunks (post-invoke; preprocessing already finished)."""
    if not text:
        return
    size = max(1, chunk_size)
    for index in range(0, len(text), size):
        yield text[index : index + size]


def iter_sse_text_events(text: str) -> Iterator[str]:
    """Yield SSE frames: one or more ``token`` events, then ``done``."""
    for chunk in iter_token_chunks(text):
        yield format_sse_event({"type": "token", "content": chunk})
    yield format_sse_event({"type": "done"})


def _latest_ai_text(messages: list[BaseMessage]) -> str:
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


def extract_turn_outcome(result: dict[str, Any]) -> ChatTurnOutcome:
    """Map graph invoke state to Gateway SSE or JSON response."""
    actions = result.get("client_actions")
    if actions:
        return ChatTurnOutcome(
            kind="client_actions",
            client_actions=[a if isinstance(a, ClientAction) else ClientAction.model_validate(a) for a in actions],
        )

    messages = list(result.get("messages") or [])
    text = _latest_ai_text(messages)
    if not text:
        draft = result.get("supervisor_draft")
        if draft:
            text = str(draft).strip()
    if not text and result.get("inbound_blocked"):
        text = str(result.get("inbound_block_message") or "").strip()
    return ChatTurnOutcome(kind="text", text=text or "")


def invoke_chat_turn(
    body: ChatRequest,
    *,
    graph: CompiledStateGraph | None = None,
) -> ChatTurnOutcome:
    """Run one chat turn; ``thread_id`` is passed via LangGraph ``configurable``."""
    resolved = graph or get_chat_graph()
    config = {"configurable": {"thread_id": body.thread_id}}
    context = graph_context_from_request(body.context)
    result = resolved.invoke(
        {"messages": [HumanMessage(content=body.message)]},
        context=context,
        config=config,
    )
    return extract_turn_outcome(result)


def build_chat_response(outcome: ChatTurnOutcome) -> ChatResponse:
    if outcome.kind == "client_actions":
        return ChatResponse(text=None, client_actions=outcome.client_actions)
    return ChatResponse(text=outcome.text, client_actions=None)
