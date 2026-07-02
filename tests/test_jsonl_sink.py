"""Tests for JsonlSink hardening — flush and checksums."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.core.envelope import EventEnvelope
from atlas.core.instrument import InstrumentRef, InstrumentType
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession
from atlas.storage.integrity import validate_archive
from atlas.storage.jsonl_sink import JsonlSink


def _market_event(seq: int, session: ObservationSession) -> EventEnvelope:
    return EventEnvelope(
        seq=seq,
        session_id=session.session_id,
        session_label=session.session_label,
        category=EventCategory.MARKET,
        received_at=datetime.now(UTC),
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        instrument=InstrumentRef(
            exchange_symbol="BTC-PERPETUAL",
            normalized_symbol="BTC-PERPETUAL",
            instrument_type=InstrumentType.PERPETUAL,
        ),
        provenance=Provenance(
            source="deribit",
            adapter_version="0.6.0",
            pipeline_version="0.6.0",
        ),
        payload={"last_price": 50000 + seq},
    )


@pytest.mark.asyncio
async def test_jsonl_sink_writes_partition_checksums(tmp_path: Path) -> None:
    session = ObservationSession.create("deribit")
    sink = JsonlSink(tmp_path, flush_every=1)

    await sink.open_session(session)
    await sink.write(_market_event(1, session))
    await sink.write(_market_event(2, session))
    await sink.finalize_session(session)

    session_dir = sink.session_dir
    assert session_dir is not None

    from atlas.storage.reader import load_manifest

    manifest = load_manifest(session_dir)
    assert manifest.partitions
    assert manifest.partitions[0].sha256
    assert manifest.archive is not None
    assert manifest.archive.manifest_sha256

    report = validate_archive(session_dir)
    assert report.valid is True
