"""Tests for replay engine."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid7

import pytest

from atlas.bus.event_bus import EventBus
from atlas.core.envelope import EventEnvelope
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory
from atlas.replay.engine import ReplayEngine
from atlas.replay.manifest import ReplayParameters
from tests.test_replay_storage import _make_event, _write_archive


@pytest.mark.asyncio
async def test_replay_engine_publishes_to_bus(tmp_path: Path) -> None:
    sid = uuid7()
    events = [_make_event(seq, sid) for seq in [1, 2, 3]]
    session_dir = _write_archive(tmp_path, events)

    bus = EventBus()
    received: list[EventEnvelope] = []

    async def collector(envelope: EventEnvelope) -> None:
        received.append(envelope)

    bus.subscribe(collector)

    engine = ReplayEngine(
        bus,
        session_dir,
        parameters=ReplayParameters(speed=0),
    )
    manifest = await engine.run()

    assert manifest.events_emitted == 3
    assert len(received) == 3
    assert received[0].seq == 1
    assert received[0].replayed_at is not None
    assert engine.cursor is not None
    assert engine.cursor.progress_pct == 100.0
    assert (session_dir / "metadata").glob("replay_*.json")


@pytest.mark.asyncio
async def test_replay_engine_seq_filter(tmp_path: Path) -> None:
    sid = uuid7()
    events = [_make_event(seq, sid) for seq in [1, 2, 3, 4, 5]]
    session_dir = _write_archive(tmp_path, events)

    bus = EventBus()
    received: list[EventEnvelope] = []

    async def collector(envelope: EventEnvelope) -> None:
        received.append(envelope)

    bus.subscribe(collector)

    engine = ReplayEngine(
        bus,
        session_dir,
        parameters=ReplayParameters(speed=0, start_seq=2, end_seq=4),
    )
    manifest = await engine.run()

    assert manifest.events_emitted == 3
    assert [e.seq for e in received] == [2, 3, 4]
