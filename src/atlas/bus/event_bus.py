"""Central Event Bus — single integration point for live and replay data."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol

from atlas.core.envelope import EventEnvelope

Subscriber = Callable[[EventEnvelope], Awaitable[None]]


class EventStream(Protocol):
    """
    Contract: EventStream v1

    Live capture and replay both expose this interface.
    Downstream consumers cannot distinguish LIVE from REPLAY.
    """

    async def events(self) -> AsyncIterator[EventEnvelope]: ...

    async def close(self) -> None: ...


class EventBus:
    """
    Central pub/sub hub. All evidence flows through the bus.

    Adapters and replay inject events; sinks (archive, metrics, console) subscribe.
    """

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._lock = asyncio.Lock()
        self._closed = False
        self._published_count = 0

    @property
    def published_count(self) -> int:
        return self._published_count

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self, handler: Subscriber) -> Callable[[], None]:
        """Register an async subscriber. Returns an unsubscribe callable."""
        self._subscribers.append(handler)

        def unsubscribe() -> None:
            if handler in self._subscribers:
                self._subscribers.remove(handler)

        return unsubscribe

    async def publish(self, event: EventEnvelope) -> None:
        """Publish an event to all subscribers."""
        if self._closed:
            msg = "Cannot publish to a closed EventBus"
            raise RuntimeError(msg)

        async with self._lock:
            self._published_count += 1

        for handler in list(self._subscribers):
            await handler(event)

    async def close(self) -> None:
        """Close the bus; no further publishes allowed."""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed
