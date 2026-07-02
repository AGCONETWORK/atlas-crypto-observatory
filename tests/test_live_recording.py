"""Tests for live recording orchestration."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.config.settings import AtlasSettings
from atlas.core.archive_state import ArchiveState
from atlas.core.instrument import InstrumentRef, InstrumentType
from atlas.evidence.builder import EvidenceBuilder
from atlas.recording.live import LiveRecorder


@pytest.mark.asyncio
async def test_live_recorder_pipeline_to_disk(tmp_path: Path) -> None:
    """Record evidence through full pipeline without live Deribit connection."""
    settings = AtlasSettings(data_path=tmp_path, deribit_environment="testnet")

    mock_discovery = MagicMock()
    mock_discovery.summary.return_value = {"total_instruments": 1, "options": 0}
    mock_discovery.instrument_count = 1

    mock_sub_result = MagicMock()
    mock_sub_result.success_count = 3
    mock_sub_result.failed_batches = []

    mock_client = MagicMock()
    mock_client.run_until_shutdown = AsyncMock()

    mock_adapter = MagicMock()
    mock_adapter.connect = AsyncMock()
    mock_adapter.discover = AsyncMock(return_value=mock_discovery)
    mock_adapter.subscribe = AsyncMock(return_value=mock_sub_result)
    mock_adapter.disconnect = AsyncMock()
    mock_adapter.client = mock_client
    mock_adapter.message_count = 0

    recorder = LiveRecorder(settings)

    with patch("atlas.recording.live.DeribitAdapter", return_value=mock_adapter):
        await recorder.start()

        builder = EvidenceBuilder(source="deribit", adapter_version="0.4.0")
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
        from atlas.pipeline.pipeline import EvidencePipeline

        pipeline: EvidencePipeline = recorder._pipeline  # noqa: SLF001
        await pipeline.ingest(evidence)

        summary = await recorder.stop()

    session_dir = tmp_path / recorder.session.start_time.strftime("%Y-%m-%d") / str(
        recorder.session.session_id
    )
    assert session_dir.exists()
    assert (session_dir / "metadata" / "manifest.json").exists()
    assert (session_dir / "metadata" / "subscriptions.json").exists()
    assert (session_dir / "market" / "BTC-PERPETUAL" / "events.jsonl.gz").exists()
    assert summary.events_recorded >= 2
    assert recorder.session.state == ArchiveState.COMPLETE
