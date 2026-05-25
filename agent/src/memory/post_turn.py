"""Fire-and-forget post-turn jobs (summary + memory write)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor

from langchain_core.messages import BaseMessage, HumanMessage

from contracts.memory_write import StructuredMemoryRecord
from memory.write import extract_and_store, store_structured_record
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
    memory_write_record: StructuredMemoryRecord | None,
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
        if memory_write_record is not None:
            write_result = store_structured_record(user_id, memory_write_record)
        else:
            write_result = extract_and_store(user_id, turn_messages)
    except Exception:
        logger.exception(
            "post_turn.memory_write_failed",
            extra={"thread_id": thread_id, "user_id": user_id},
        )
        return

    if write_result.status == "failed":
        logger.error(
            "post_turn.memory_write_failed",
            extra={
                "thread_id": thread_id,
                "user_id": user_id,
                "reason": write_result.reason,
            },
        )
    else:
        logger.info(
            "post_turn.memory_write_completed",
            extra={
                "thread_id": thread_id,
                "user_id": user_id,
                "status": write_result.status,
                "stored_count": write_result.stored_count,
            },
        )


def schedule_post_turn_jobs(
    *,
    thread_id: str,
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    memory_write_record: StructuredMemoryRecord | None = None,
    k: int | None = None,
    m: int | None = None,
) -> Future[None]:
    """Schedule summary + memory writes without blocking the chat path."""
    future = _get_executor().submit(
        _run_post_turn_jobs,
        thread_id=thread_id,
        user_id=user_id,
        turn_messages=list(turn_messages),
        memory_write_record=memory_write_record,
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
