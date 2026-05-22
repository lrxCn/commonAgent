"""In-process observability event collector and dispatch helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from contracts.events import ObservabilityEvent, ObservabilityEventType

EventSubscriber = Callable[[ObservabilityEvent], None]

_events_var: ContextVar[tuple[ObservabilityEvent, ...]] = ContextVar(
    "observability_events",
    default=(),
)
_subscribers: list[EventSubscriber] = []


def get_current_events() -> list[ObservabilityEvent]:
    """Return events emitted in the current context."""
    return list(_events_var.get())


def clear_current_events() -> None:
    """Clear current-context events."""
    _events_var.set(())


@contextmanager
def collect_events() -> Iterable[list[ObservabilityEvent]]:
    """Collect events emitted inside the context and restore the previous context."""
    previous = _events_var.get()
    _events_var.set(())
    try:
        buffer: list[ObservabilityEvent] = []
        yield buffer
        buffer.extend(_events_var.get())
    finally:
        _events_var.set(previous)


def subscribe_events(subscriber: EventSubscriber) -> None:
    """Register a synchronous subscriber if not already registered."""
    if subscriber not in _subscribers:
        _subscribers.append(subscriber)


def unsubscribe_events(subscriber: EventSubscriber) -> None:
    """Remove a synchronous subscriber if present."""
    try:
        _subscribers.remove(subscriber)
    except ValueError:
        pass


def reset_event_subscribers() -> None:
    """Clear subscribers, intended for tests."""
    _subscribers.clear()


def emit_event(
    name: str | ObservabilityEventType,
    metadata: Mapping[str, Any] | None = None,
) -> ObservabilityEvent:
    """Emit one observability event and notify subscribers.

    Subscriber failures are swallowed so observability cannot affect business paths.
    """
    event = ObservabilityEvent(name=name, metadata=dict(metadata or {}))
    _events_var.set((*_events_var.get(), event))
    for subscriber in list(_subscribers):
        try:
            subscriber(event)
        except Exception:
            pass
    return event
