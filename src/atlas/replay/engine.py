"""Replay engine — deterministic playback into the Event Bus."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import structlog

from atlas import __version__
from atlas.bus.event_bus import EventBus
from atlas.core.envelope import EventEnvelope
from atlas.replay.cursor import ReplayCursor, ReplayState
from atlas.replay.manifest import ReplayCursorState, ReplayManifest, ReplayParameters
from atlas.storage.integrity import IntegrityReport, validate_archive
from atlas.storage.reader import filter_events, load_session, read_events

log = structlog.get_logger(__name__)


class ReplayEngine:
    """
    Replays archived evidence into the Event Bus.

    Live and replay share identical downstream interface.
    Contract: ReplayEngine v1
    """

    def __init__(
        self,
        bus: EventBus,
        session_dir: Path,
        *,
        parameters: ReplayParameters | None = None,
        force: bool = False,
    ) -> None:
        self._bus = bus
        self._session_dir = session_dir
        self._parameters = parameters or ReplayParameters()
        self._force = force
        self._cursor: ReplayCursor | None = None
        self._stop = asyncio.Event()
        self._integrity_report: IntegrityReport | None = None

    @property
    def cursor(self) -> ReplayCursor | None:
        return self._cursor

    @property
    def integrity_report(self) -> IntegrityReport | None:
        return self._integrity_report

    def pause(self) -> None:
        if self._cursor:
            self._cursor.pause()

    def resume(self) -> None:
        if self._cursor:
            self._cursor.resume()

    def stop(self) -> None:
        self._stop.set()
        if self._cursor:
            self._cursor.mark_stopped()

    def step(self) -> None:
        """Emit one event while paused."""
        if self._cursor:
            self._cursor.request_step()

    async def run(self) -> ReplayManifest:
        """Validate archive, replay events, return audit manifest."""
        started_at = datetime.now(UTC)
        session = load_session(self._session_dir)

        self._integrity_report = validate_archive(self._session_dir)
        if not self._integrity_report.valid and not self._force:
            errors = [e.message for e in self._integrity_report.errors]
            msg = f"Archive integrity check failed: {'; '.join(errors)}"
            raise RuntimeError(msg)

        all_events = read_events(self._session_dir)
        events = filter_events(
            all_events,
            start_seq=self._parameters.start_seq,
            end_seq=self._parameters.end_seq,
            start_time=self._parameters.start_time,
            end_time=self._parameters.end_time,
        )

        self._cursor = ReplayCursor(total_events=len(events))
        self._cursor.state = ReplayState.PLAYING
        emitted = 0
        prev_received_at: datetime | None = None

        log.info(
            "replay.started",
            session_id=str(session.session_id),
            events=len(events),
            speed=self._parameters.speed,
        )

        for event in events:
            if self._stop.is_set():
                break

            await self._cursor.wait_while_paused()
            if self._stop.is_set():
                break

            if prev_received_at is not None and self._parameters.speed > 0:
                delta = (event.received_at - prev_received_at).total_seconds()
                if delta > 0:
                    await asyncio.sleep(delta / self._parameters.speed)

            await self._emit(event)
            emitted += 1
            prev_received_at = event.received_at

            if self._cursor.state == ReplayState.PAUSED:
                self._cursor.consume_step()

        if self._stop.is_set():
            self._cursor.mark_stopped()
        else:
            self._cursor.mark_completed()

        ended_at = datetime.now(UTC)
        manifest = ReplayManifest(
            source_session_id=session.session_id,
            replay_version=__version__,
            started_at=started_at,
            ended_at=ended_at,
            parameters=self._parameters,
            integrity_report=self._integrity_report,
            events_emitted=emitted,
            cursor_final=ReplayCursorState(
                seq=self._cursor.current_seq or 0,
                timestamp=self._cursor.current_timestamp,
                progress_pct=self._cursor.progress_pct,
            ),
        )

        await self._write_audit_manifest(manifest)
        log.info("replay.completed", events_emitted=emitted, replay_id=str(manifest.replay_id))
        return manifest

    async def _emit(self, event: EventEnvelope) -> EventEnvelope:
        """Publish event to bus with Replay Clock timestamp."""
        replayed_at = datetime.now(UTC)
        replayed = event.model_copy(update={"replayed_at": replayed_at})
        await self._bus.publish(replayed)
        if self._cursor:
            self._cursor.advance(event.seq, event.received_at)
        return replayed

    async def _write_audit_manifest(self, manifest: ReplayManifest) -> None:
        metadata_dir = self._session_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        path = metadata_dir / f"replay_{manifest.replay_id}.json"
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
