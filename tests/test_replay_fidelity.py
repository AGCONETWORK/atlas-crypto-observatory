"""Replay fidelity — archived events replay with identical seq and payload."""

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
from atlas.storage.integrity import validate_archive
from atlas.storage.reader import read_events
from tests.test_replay_storage import _make_event, _write_archive


@pytest.mark.asyncio
async def test_replay_preserves_seq_and_payload(tmp_path: Path) -> None:
    """Replay emits the same seq ordering and payloads as the archive."""
    sid = uuid7()
    events = [_make_event(seq, sid) for seq in range(1, 6)]
    session_dir = _write_archive(tmp_path, events)

    report = validate_archive(session_dir)
    assert report.valid

    archived = read_events(session_dir)

    bus = EventBus()
    replayed: list[EventEnvelope] = []

    async def collector(envelope: EventEnvelope) -> None:
        replayed.append(envelope)

    bus.subscribe(collector)

    engine = ReplayEngine(bus, session_dir, parameters=ReplayParameters(speed=0))
    manifest = await engine.run()

    assert manifest.events_emitted == len(archived)
    assert [e.seq for e in replayed] == [e.seq for e in archived]
    assert [e.payload for e in replayed] == [e.payload for e in archived]
    assert all(e.replayed_at is not None for e in replayed)
