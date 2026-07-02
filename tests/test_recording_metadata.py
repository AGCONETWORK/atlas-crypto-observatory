"""Tests for session metadata tracking."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.core.envelope import EventEnvelope
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession
from atlas.recording.metadata import SessionMetadataTracker


def _connection_event(stream: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        seq=1,
        session_id=ObservationSession.create("deribit").session_id,
        session_label="obs_test",
        category=EventCategory.CONNECTION,
        received_at=datetime.now(UTC),
        exchange="deribit",
        stream=stream,
        channel=stream,
        provenance=Provenance(
            source="deribit",
            adapter_version="0.6.0",
            pipeline_version="0.6.0",
        ),
        payload=payload,
    )


@pytest.mark.asyncio
async def test_metadata_tracker_records_reconnects_and_gaps(tmp_path: Path) -> None:
    session = ObservationSession.create("deribit")
    tracker = SessionMetadataTracker(session=session, session_dir=tmp_path)

    await tracker.observe_event(
        _connection_event("connection.reconnect", {"attempt": 1, "delay_seconds": 1.0})
    )
    await tracker.observe_event(
        _connection_event("gap.detected", {"gap_seconds": 12.5})
    )

    tracker.write_reconnects()
    reconnects_path = tmp_path / "metadata" / "reconnects.json"
    assert reconnects_path.exists()
    assert session.data_quality.largest_gap_seconds == 12.5
    assert len(tracker.gap_events) == 1
