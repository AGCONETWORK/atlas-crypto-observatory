"""Session status reporting for live and archived recordings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from atlas.core.archive_state import ArchiveState
from atlas.evidence.observation import ObservationSession
from atlas.storage.archive import list_session_dirs, resolve_session_dir
from atlas.storage.reader import load_manifest, load_session


@dataclass
class SessionStatus:
    """Human-readable session health and archive summary."""

    session_dir: Path
    session: ObservationSession
    state: ArchiveState
    events_recorded: int
    reconnects: int
    gap_count: int
    largest_gap_seconds: float
    is_stale: bool
    messages_per_second: float | None = None


def resolve_status_session(data_path: Path, session: str | None) -> Path:
    """Resolve session directory for status, defaulting to latest archive."""
    if session:
        return resolve_session_dir(data_path, session)
    sessions = list_session_dirs(data_path)
    if not sessions:
        msg = f"No archives found under {data_path}"
        raise FileNotFoundError(msg)
    return sessions[0].parent


def _load_reconnect_metadata(session_dir: Path) -> dict[str, object]:
    path = session_dir / "metadata" / "reconnects.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_session_status(data_path: Path, session: str | None = None) -> SessionStatus:
    """Load status from flushed session metadata on disk."""
    session_dir = resolve_status_session(data_path, session)
    obs_session = load_session(session_dir)
    reconnect_meta = _load_reconnect_metadata(session_dir)

    events_recorded = obs_session.data_quality.messages_written
    try:
        manifest = load_manifest(session_dir)
        events_recorded = manifest.event_count
    except (FileNotFoundError, ValueError):
        pass

    gap_count = int(reconnect_meta.get("gap_count", 0))
    is_stale = obs_session.state == ArchiveState.RECORDING and (
        obs_session.data_quality.messages_written == 0
        or obs_session.data_quality.largest_gap_seconds > 0
    )

    return SessionStatus(
        session_dir=session_dir,
        session=obs_session,
        state=obs_session.state,
        events_recorded=events_recorded,
        reconnects=obs_session.data_quality.reconnects,
        gap_count=gap_count,
        largest_gap_seconds=obs_session.data_quality.largest_gap_seconds,
        is_stale=is_stale,
    )
