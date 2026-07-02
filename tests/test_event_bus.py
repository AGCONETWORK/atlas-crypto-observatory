"""Tests for Event Bus — central integration point."""

from datetime import UTC, datetime
from uuid import uuid7

import pytest

from atlas.bus.event_bus import EventBus
from atlas.core.envelope import EventEnvelope
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory


def _make_event(seq: int) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        session_id=uuid7(),
        session_label="obs_test",
        category=EventCategory.MARKET,
        received_at=datetime.now(UTC),
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        provenance=Provenance(
            source="deribit",
            adapter_version="0.1.0",
            pipeline_version="0.1.0",
        ),
        payload={"seq": seq},
    )


@pytest.mark.asyncio
async def test_publish_delivers_to_subscribers() -> None:
    bus = EventBus()
    received: list[EventEnvelope] = []

    async def handler(event: EventEnvelope) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.publish(_make_event(1))
    await bus.publish(_make_event(2))

    assert len(received) == 2
    assert received[0].seq == 1
    assert received[1].seq == 2
    assert bus.published_count == 2


@pytest.mark.asyncio
async def test_multiple_subscribers() -> None:
    bus = EventBus()
    counts = {"a": 0, "b": 0}

    async def handler_a(event: EventEnvelope) -> None:
        counts["a"] += 1

    async def handler_b(event: EventEnvelope) -> None:
        counts["b"] += 1

    bus.subscribe(handler_a)
    bus.subscribe(handler_b)
    await bus.publish(_make_event(1))

    assert counts["a"] == 1
    assert counts["b"] == 1


@pytest.mark.asyncio
async def test_unsubscribe() -> None:
    bus = EventBus()
    received: list[EventEnvelope] = []

    async def handler(event: EventEnvelope) -> None:
        received.append(event)

    unsub = bus.subscribe(handler)
    await bus.publish(_make_event(1))
    unsub()
    await bus.publish(_make_event(2))

    assert len(received) == 1


@pytest.mark.asyncio
async def test_closed_bus_rejects_publish() -> None:
    bus = EventBus()
    await bus.close()

    with pytest.raises(RuntimeError, match="closed"):
        await bus.publish(_make_event(1))
