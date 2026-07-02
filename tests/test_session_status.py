"""Tests for session status command."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.config.settings import AtlasSettings
from atlas.core.envelope import EventEnvelope
from atlas.core.instrument import InstrumentRef, InstrumentType
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession
from atlas.recording.status import load_session_status
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
        payload={"last_price": 50000},
    )


@pytest.mark.asyncio
async def test_load_session_status_from_archive(tmp_path: Path) -> None:
    session = ObservationSession.create("deribit")
    sink = JsonlSink(tmp_path)
    await sink.open_session(session)
    await sink.write(_market_event(1, session))
    await sink.finalize_session(session)

    settings = AtlasSettings(data_path=tmp_path)
    status = load_session_status(settings.data_path, str(session.session_id))

    assert status.events_recorded >= 1
    assert status.session.session_id == session.session_id
