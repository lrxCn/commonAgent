"""Fire-and-forget post-turn jobs (summary + mem0 write)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor

from langchain_core.messages import BaseMessage, HumanMessage

from memory.mem0_write import extract_and_store
from memory.summary_job import update_rolling_summary

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_pending_futures: set[Future[None]] = set()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="post-turn")
    return _executor


def reset_post_turn_executor(*, wait: bool = True) -> None:
    """Shut down background executor (tests)."""
    global _executor
    if _executor is None:
        return
    if wait:
        for future in list(_pending_futures):
            future.result(timeout=10)
        _pending_futures.clear()
    _executor.shutdown(wait=wait, cancel_futures=not wait)
    _executor = None


def _run_post_turn_jobs(
    *,
    thread_id: str,
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    k: int | None,
    m: int | None,
) -> None:
    try:
        update_rolling_summary(thread_id, turn_messages, k, m)
    except Exception:
        logger.exception(
            "post_turn.summary_failed",
            extra={"thread_id": thread_id},
        )

    try:
        extract_and_store(user_id, turn_messages)
    except Exception:
        logger.exception(
            "post_turn.mem0_write_failed",
            extra={"thread_id": thread_id, "user_id": user_id},
        )


def schedule_post_turn_jobs(
    *,
    thread_id: str,
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    k: int | None = None,
    m: int | None = None,
) -> Future[None]:
    """Schedule summary + mem0 writes without blocking the chat path."""
    future = _get_executor().submit(
        _run_post_turn_jobs,
        thread_id=thread_id,
        user_id=user_id,
        turn_messages=list(turn_messages),
        k=k,
        m=m,
    )
    _pending_futures.add(future)

    def _done(done: Future[None]) -> None:
        _pending_futures.discard(done)
        try:
            done.result()
        except Exception:
            logger.exception("post_turn.job_failed", extra={"thread_id": thread_id})

    future.add_done_callback(_done)
    return future


def extract_current_turn_messages(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """Return messages from the latest human turn through the end of the list."""
    last_human: int | None = None
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            last_human = index
            break
    if last_human is None:
        return []
    return list(messages[last_human:])
