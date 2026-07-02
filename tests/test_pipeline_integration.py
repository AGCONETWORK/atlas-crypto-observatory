"""Integration tests for evidence pipeline and JsonlSink."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.bus.event_bus import EventBus
from atlas.core.instrument import InstrumentRef, InstrumentType
from atlas.evidence.builder import EvidenceBuilder
from atlas.evidence.observation import ObservationSession
from atlas.pipeline.pipeline import PipelineRunner
from atlas.core.archive_state import ArchiveState
from atlas.storage.jsonl_sink import JsonlSink


@pytest.mark.asyncio
async def test_pipeline_records_to_jsonl(tmp_path: Path) -> None:
    bus = EventBus()
    session = ObservationSession.create("deribit", adapter_version="0.1.0")
    sink = JsonlSink(tmp_path)

    from atlas.pipeline.pipeline import EvidencePipeline

    pipeline = EvidencePipeline(bus, session)
    runner = PipelineRunner(bus, pipeline, sink)

    await runner.start()

    builder = EvidenceBuilder(source="deribit", adapter_version="0.1.0")
    evidence = builder.build_market_evidence(
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        payload={"last_price": 50000},
        instrument=InstrumentRef(
            exchange_symbol="BTC-PERPETUAL",
            normalized_symbol="BTC-PERPETUAL",
            instrument_type=InstrumentType.PERPETUAL,
        ),
        exchange_timestamp=datetime(2026, 7, 2, 14, 0, 0, tzinfo=UTC),
    )
    await pipeline.ingest(evidence)
    await runner.stop()

    date_dir = tmp_path / session.start_time.strftime("%Y-%m-%d") / str(session.session_id)
    manifest_path = date_dir / "metadata" / "manifest.json"
    session_path = date_dir / "metadata" / "session.json"
    market_path = date_dir / "market" / "BTC-PERPETUAL" / "events.jsonl.gz"

    assert manifest_path.exists()
    assert session_path.exists()
    assert market_path.exists()
    assert session.state == ArchiveState.COMPLETE
    assert pipeline.current_seq >= 2  # market + lifecycle events
