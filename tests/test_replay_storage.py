"""Tests for archive reader and integrity validation."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid7

import pytest

from atlas.core.envelope import EventEnvelope
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession
from atlas.core.archive_state import ArchiveState
from atlas.storage.integrity import validate_archive
from atlas.storage.manifest import PartitionEntry, StorageManifest
from atlas.storage.reader import read_events


def _make_event(seq: int, session_id: object) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        session_id=session_id,
        session_label="obs_test",
        category=EventCategory.MARKET if seq > 2 else EventCategory.RECORDER,
        received_at=datetime(2026, 7, 2, 12, 0, seq, tzinfo=UTC),
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        provenance=Provenance(
            source="deribit",
            adapter_version="0.4.0",
            pipeline_version="0.4.0",
        ),
        payload={"seq": seq},
    )


def _write_archive(tmp_path: Path, events: list[EventEnvelope]) -> Path:
    session_id = events[0].session_id
    session = ObservationSession(
        session_id=session_id,
        session_label="obs_test",
        exchange="deribit",
        state=ArchiveState.COMPLETE,
    )
    session_dir = tmp_path / "2026-07-02" / str(session_id)
    metadata_dir = session_dir / "metadata"
    market_dir = session_dir / "market" / "BTC-PERPETUAL"
    metadata_dir.mkdir(parents=True)
    market_dir.mkdir(parents=True)

    partition_path = market_dir / "events.jsonl.gz"
    with gzip.open(partition_path, "wt", encoding="utf-8") as handle:
        for event in events:
            handle.write(event.model_dump_json() + "\n")

    manifest = StorageManifest(
        session_id=session_id,
        session_label="obs_test",
        state=ArchiveState.COMPLETE,
        created_at=datetime(2026, 7, 2, tzinfo=UTC),
        finalized_at=datetime(2026, 7, 2, tzinfo=UTC),
        event_count=len(events),
        partitions=[
            PartitionEntry(
                path=str(partition_path.relative_to(session_dir)),
                event_count=len(events),
                compressed_size_bytes=partition_path.stat().st_size,
                uncompressed_size_bytes=0,
            )
        ],
    )

    (metadata_dir / "session.json").write_text(session.model_dump_json(), encoding="utf-8")
    (metadata_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return session_dir


@pytest.mark.asyncio
async def test_read_events_sorted(tmp_path: Path) -> None:
    sid = uuid7()
    events = [_make_event(seq, sid) for seq in [3, 1, 2]]
    session_dir = _write_archive(tmp_path, events)
    loaded = read_events(session_dir)
    assert [e.seq for e in loaded] == [1, 2, 3]


def test_validate_archive_ok(tmp_path: Path) -> None:
    sid = uuid7()
    events = [_make_event(seq, sid) for seq in [1, 2, 3]]
    session_dir = _write_archive(tmp_path, events)
    report = validate_archive(session_dir)
    assert report.valid
    assert not report.errors


def test_validate_archive_missing_manifest(tmp_path: Path) -> None:
    session_dir = tmp_path / "empty"
    (session_dir / "metadata").mkdir(parents=True)
    report = validate_archive(session_dir)
    assert not report.valid
    assert any(e.code.value == "MANIFEST_MISSING" for e in report.errors)
