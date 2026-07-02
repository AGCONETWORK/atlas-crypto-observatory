"""Live recording — wires adapter, pipeline, bus, and storage."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import structlog

from atlas.adapters.deribit import DeribitAdapter
from atlas.adapters.deribit.constants import ADAPTER_VERSION, API_VERSION, EXCHANGE_ID
from atlas.bus.event_bus import EventBus
from atlas.config.settings import AtlasSettings
from atlas.evidence.observation import ObservationSession
from atlas.pipeline.pipeline import EvidencePipeline, PipelineRunner
from atlas.storage.jsonl_sink import JsonlSink

log = structlog.get_logger(__name__)


@dataclass
class RecordingSummary:
    """Outcome of a live recording session."""

    session_id: str
    session_label: str
    session_dir: Path | None
    events_recorded: int
    market_messages: int
    reconnects: int
    subscription_failures: int


class LiveRecorder:
    """
    Orchestrates live evidence capture.

    Adapter → Evidence Pipeline → Event Bus → JsonlSink
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self._settings = settings
        self._bus = EventBus()
        self._session = ObservationSession.create(
            EXCHANGE_ID,
            environment=settings.deribit_environment,
            adapter_version=ADAPTER_VERSION,
            api_version=API_VERSION,
        )
        self._pipeline = EvidencePipeline(self._bus, self._session)
        self._sink = JsonlSink(settings.data_path)
        self._runner = PipelineRunner(self._bus, self._pipeline, self._sink)
        self._adapter: DeribitAdapter | None = None
        self._client_task: asyncio.Task[None] | None = None
        self._started = False

    @property
    def session(self) -> ObservationSession:
        return self._session

    @property
    def adapter(self) -> DeribitAdapter | None:
        return self._adapter

    async def start(self) -> None:
        """Start pipeline, storage, adapter, discovery, and subscriptions."""
        if self._started:
            return

        await self._runner.start()

        self._adapter = DeribitAdapter(
            self._settings,
            evidence_handler=self._pipeline.ingest,
        )
        await self._adapter.connect()
        discovery = await self._adapter.discover()
        result = await self._adapter.subscribe()

        if result.failed_batches:
            self._session.data_quality.subscription_failures = len(result.failed_batches)

        await self._write_subscriptions_metadata(discovery.summary(), result)

        assert self._adapter.client is not None
        self._client_task = asyncio.create_task(self._adapter.client.run_until_shutdown())

        self._started = True
        log.info(
            "recording.started",
            session_id=str(self._session.session_id),
            session_label=self._session.session_label,
            channels=result.success_count,
            instruments=discovery.instrument_count,
        )

    async def _write_subscriptions_metadata(
        self,
        discovery_summary: dict[str, int],
        subscription_result: object,
    ) -> None:
        if self._sink.session_dir is None:
            return

        metadata_dir = self._sink.session_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "discovery": discovery_summary,
            "subscribed_channels": getattr(subscription_result, "success_count", 0),
            "failed_batches": len(getattr(subscription_result, "failed_batches", [])),
            "channels": self._settings.channel_list,
            "interval": self._settings.interval,
        }
        (metadata_dir / "subscriptions.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    async def stop(self) -> RecordingSummary:
        """Gracefully stop recording and finalize the archive."""
        if not self._started:
            return RecordingSummary(
                session_id=str(self._session.session_id),
                session_label=self._session.session_label,
                session_dir=self._sink.session_dir,
                events_recorded=0,
                market_messages=0,
                reconnects=0,
                subscription_failures=0,
            )

        if self._adapter and self._adapter.client:
            metrics = self._adapter.client.metrics
            self._session.data_quality.reconnects = metrics.reconnect_count
            self._session.data_quality.heartbeat_failures = metrics.heartbeat_failures

        if self._client_task and not self._client_task.done():
            self._client_task.cancel()
            try:
                await self._client_task
            except asyncio.CancelledError:
                pass

        if self._adapter:
            await self._adapter.disconnect()

        await self._runner.stop()
        self._started = False

        written = self._session.data_quality.messages_written
        received = self._session.data_quality.messages_received
        if received > written:
            self._session.data_quality.dropped_messages = received - written

        if self._sink.session_dir and written > 0:
            compressed = sum(
                p.stat().st_size
                for p in (self._sink.session_dir / "market").rglob("*.jsonl.gz")
                if p.is_file()
            )
            if compressed > 0:
                self._session.data_quality.compression_ratio = round(
                    compressed / max(written, 1),
                    4,
                )

        log.info(
            "recording.stopped",
            session_id=str(self._session.session_id),
            events=written,
        )

        market_messages = self._adapter.message_count if self._adapter else 0
        return RecordingSummary(
            session_id=str(self._session.session_id),
            session_label=self._session.session_label,
            session_dir=self._sink.session_dir,
            events_recorded=written,
            market_messages=market_messages,
            reconnects=self._session.data_quality.reconnects,
            subscription_failures=self._session.data_quality.subscription_failures,
        )

    async def run_until(self, stop: asyncio.Event, *, duration: int | None = None) -> RecordingSummary:
        """Record until stop event, optional timeout, or Ctrl+C."""
        await self.start()
        try:
            if duration and duration > 0:
                await asyncio.wait_for(stop.wait(), timeout=duration)
            else:
                await stop.wait()
        except TimeoutError:
            pass
        return await self.stop()
