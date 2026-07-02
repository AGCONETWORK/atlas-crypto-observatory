"""Evidence Pipeline — orchestrates ingest, sequencing, and bus publication."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from atlas.bus.event_bus import EventBus
from atlas.core.envelope import EventEnvelope, EvidenceObject
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession
from atlas.core.archive_state import ArchiveState
from atlas.storage.sink import StorageSink

log = structlog.get_logger(__name__)


class EvidencePipeline:
    """
    Evidence Pipeline: assigns seq, timestamps, publishes to Event Bus.

    The pipeline is not a recorder — it sequences evidence and fans out to sinks.
    Storage is one sink; metrics and live console are future sinks.
    """

    def __init__(self, bus: EventBus, session: ObservationSession) -> None:
        self._bus = bus
        self._session = session
        self._seq = 0
        self._running = False

    @property
    def session(self) -> ObservationSession:
        return self._session

    @property
    def current_seq(self) -> int:
        return self._seq

    async def start(self) -> None:
        """Begin observation session."""
        self._session.transition_to(ArchiveState.RECORDING)
        self._running = True
        await self._emit_lifecycle(
            EventCategory.RECORDER,
            "recorder.started",
            {"session_id": str(self._session.session_id)},
        )
        log.info(
            "pipeline.started",
            session_id=str(self._session.session_id),
            session_label=self._session.session_label,
        )

    async def ingest(self, evidence: EvidenceObject) -> EventEnvelope:
        """Assign sequence number, wrap envelope, publish to bus."""
        if not self._running:
            msg = "Pipeline is not running"
            raise RuntimeError(msg)

        self._seq += 1
        self._session.record_message_received()
        received_at = datetime.now(UTC)

        envelope = EventEnvelope.from_evidence(
            evidence,
            seq=self._seq,
            session_id=self._session.session_id,
            session_label=self._session.session_label,
            received_at=received_at,
        )

        await self._bus.publish(envelope)
        return envelope

    async def stop(self) -> None:
        """Gracefully stop the pipeline."""
        if not self._running:
            return

        await self._emit_lifecycle(
            EventCategory.RECORDER,
            "recorder.stopped",
            {"session_id": str(self._session.session_id), "final_seq": self._seq},
        )
        self._running = False
        self._session.finalize()
        log.info(
            "pipeline.stopped",
            session_id=str(self._session.session_id),
            events=self._seq,
        )

    async def _emit_lifecycle(
        self,
        category: EventCategory,
        stream: str,
        payload: dict,
    ) -> None:
        from atlas.evidence.builder import EvidenceBuilder

        builder = EvidenceBuilder(
            source=self._session.exchange,
            adapter_version=self._session.adapter_version or "0.0.0",
        )
        evidence = builder.build_lifecycle_evidence(
            category=category,
            exchange=self._session.exchange,
            stream=stream,
            channel=stream,
            payload=payload,
        )
        await self.ingest(evidence)


class PipelineRunner:
    """Wires pipeline to storage sink via Event Bus subscription."""

    def __init__(
        self,
        bus: EventBus,
        pipeline: EvidencePipeline,
        storage_sink: StorageSink,
    ) -> None:
        self._bus = bus
        self._pipeline = pipeline
        self._storage_sink = storage_sink
        self._unsubscribe: Callable[[], None] = lambda: None

    async def start(self) -> None:
        await self._storage_sink.open_session(self._pipeline.session)

        async def archive_handler(event: EventEnvelope) -> None:
            await self._storage_sink.write(event)
            self._pipeline.session.record_message_written()

        self._unsubscribe = self._bus.subscribe(archive_handler)
        await self._pipeline.start()

    async def stop(self) -> None:
        await self._pipeline.stop()
        self._unsubscribe()
        self._pipeline.session.transition_to(ArchiveState.FINALIZING)
        await self._storage_sink.finalize_session(self._pipeline.session)
        self._pipeline.session.transition_to(ArchiveState.COMPLETE)
