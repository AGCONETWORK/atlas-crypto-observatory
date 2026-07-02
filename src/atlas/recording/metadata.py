"""Session metadata tracking during recording."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.core.envelope import EventEnvelope
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession


@dataclass
class SessionMetadataTracker:
    """Collects lifecycle events and writes metadata sidecar files."""

    session: ObservationSession
    session_dir: Path | None = None
    reconnect_events: list[dict[str, Any]] = field(default_factory=list)
    gap_events: list[dict[str, Any]] = field(default_factory=list)

    async def observe_event(self, event: EventEnvelope) -> None:
        """Track connection lifecycle events for metadata files."""
        if event.category != EventCategory.CONNECTION:
            return

        payload = dict(event.payload)
        payload["stream"] = event.stream

        if event.stream in {"connection.reconnect", "connection.closed"}:
            self.reconnect_events.append(payload)

        if event.stream == "gap.detected":
            self.gap_events.append(payload)
            gap_seconds = float(payload.get("gap_seconds", 0))
            if gap_seconds > self.session.data_quality.largest_gap_seconds:
                self.session.data_quality.largest_gap_seconds = gap_seconds

    def write_reconnects(self) -> None:
        """Persist reconnect and gap log to metadata/reconnects.json."""
        if self.session_dir is None:
            return

        metadata_dir = self.session_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "reconnect_count": len(
                [e for e in self.reconnect_events if e.get("stream") == "connection.reconnect"]
            ),
            "gap_count": len(self.gap_events),
            "reconnects": self.reconnect_events,
            "gaps": self.gap_events,
            "written_at": datetime.now(UTC).isoformat(),
        }
        (metadata_dir / "reconnects.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def flush_session(self) -> None:
        """Rewrite session.json with current data quality metrics."""
        if self.session_dir is None:
            return

        path = self.session_dir / "metadata" / "session.json"
        path.write_text(self.session.model_dump_json(indent=2), encoding="utf-8")
