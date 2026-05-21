"""Chat turn: invoke Supervisor graph, return SSE text stream or client_actions JSON."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from gateway.schemas import ChatRequest, ChatResponse, ClientAction
from graph.context import graph_context_from_request
from graph.supervisor import reset_stream_token_sink, set_stream_token_sink
from guardrails.outbound import OUTBOUND_SAFE_REPLY, check_outbound_stream_window

_graph_override: CompiledStateGraph | None = None

# Characters per SSE token event (full reply is produced after graph invoke).
_SSE_CHUNK_SIZE = 32
_SSE_STOP = object()
_SEGMENT_PREFIX = "seg"


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
    for index, chunk in enumerate(iter_token_chunks(text), start=1):
        yield format_sse_event(
            {
                "type": "token",
                "content": chunk,
                "segment_id": f"{_SEGMENT_PREFIX}-{index}",
            }
        )
    yield format_sse_event({"type": "done"})


def _should_live_stream(body: ChatRequest) -> bool:
    """Only natural-language text replies stream live; tool turns stay structured."""
    return not bool(body.context.tools)


def _next_segment_id(index: int) -> str:
    return f"{_SEGMENT_PREFIX}-{index}"


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


def iter_chat_sse_events(
    body: ChatRequest,
    *,
    graph: CompiledStateGraph | None = None,
) -> Iterator[str]:
    """Run one chat turn and yield SSE frames.

    For plain text turns, final model tokens are forwarded through a LangChain callback
    while the graph is running. If a turn has client tools, live token streaming is
    disabled so client_actions JSON is never split into natural-language token events.
    """
    if not _should_live_stream(body):
        outcome = invoke_chat_turn(body, graph=graph)
        if outcome.kind == "client_actions":
            yield format_sse_event(
                {
                    "type": "client_actions",
                    "client_actions": [a.model_dump() for a in outcome.client_actions or []],
                }
            )
            yield format_sse_event({"type": "done"})
            return
        yield from iter_sse_text_events(outcome.text or "")
        return

    token_queue: queue.Queue[str | ChatTurnOutcome | BaseException | object] = queue.Queue()

    def push_token(token: str) -> None:
        token_queue.put(token)

    def run_graph() -> None:
        sink_token = set_stream_token_sink(push_token)
        try:
            token_queue.put(invoke_chat_turn(body, graph=graph))
        except BaseException as exc:
            token_queue.put(exc)
        finally:
            reset_stream_token_sink(sink_token)
            token_queue.put(_SSE_STOP)

    thread = threading.Thread(target=run_graph, name="chat-sse-graph", daemon=True)
    thread.start()

    streamed_text = ""
    emitted_segment_ids: list[str] = []
    blocked_stream = False
    segment_index = 1
    final_outcome: ChatTurnOutcome | None = None
    pending_error: BaseException | None = None
    while True:
        item = token_queue.get()
        if item is _SSE_STOP:
            break
        if isinstance(item, str):
            streamed_text += item
            if blocked_stream:
                continue
            segment_id = _next_segment_id(segment_index)
            segment_index += 1
            emitted_segment_ids.append(segment_id)
            yield format_sse_event(
                {
                    "type": "token",
                    "content": item,
                    "segment_id": segment_id,
                }
            )
            decision = check_outbound_stream_window(streamed_text)
            if not decision.allowed:
                blocked_stream = True
                for emitted_id in emitted_segment_ids:
                    yield format_sse_event(
                        {
                            "type": "retract",
                            "segment_id": emitted_id,
                            "reason": decision.reason_code or "outbound_guard",
                        }
                    )
                yield format_sse_event(
                    {
                        "type": "replace",
                        "segment_id": segment_id,
                        "content": decision.replacement or OUTBOUND_SAFE_REPLY,
                    }
                )
            continue
        if isinstance(item, ChatTurnOutcome):
            final_outcome = item
            continue
        if isinstance(item, BaseException):
            pending_error = item

    thread.join()
    if pending_error is not None:
        yield format_sse_event(
            {
                "type": "error",
                "message": str(pending_error) or type(pending_error).__name__,
            }
        )
        return

    if final_outcome is None:
        yield format_sse_event({"type": "done"})
        return
    if final_outcome.kind == "client_actions":
        yield format_sse_event(
            {
                "type": "client_actions",
                "client_actions": [a.model_dump() for a in final_outcome.client_actions or []],
            }
        )
        yield format_sse_event({"type": "done"})
        return

    final_text = final_outcome.text or ""
    if final_text and not streamed_text:
        yield from iter_sse_text_events(final_text)
        return
    if not blocked_stream and emitted_segment_ids and final_text and final_text != streamed_text:
        for segment_id in emitted_segment_ids:
            yield format_sse_event(
                {
                    "type": "retract",
                    "segment_id": segment_id,
                    "reason": "outbound_guard",
                }
            )
        yield format_sse_event(
            {
                "type": "replace",
                "segment_id": emitted_segment_ids[0],
                "content": final_text,
            }
        )
    yield format_sse_event({"type": "done"})


def build_chat_response(outcome: ChatTurnOutcome) -> ChatResponse:
    if outcome.kind == "client_actions":
        return ChatResponse(text=None, client_actions=outcome.client_actions)
    return ChatResponse(text=outcome.text, client_actions=None)
