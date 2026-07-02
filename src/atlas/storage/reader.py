"""Read immutable JSONL archives for replay."""

from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path

from atlas.core.envelope import EventEnvelope
from atlas.evidence.observation import ObservationSession
from atlas.storage.manifest import StorageManifest


def load_session(session_dir: Path) -> ObservationSession:
    """Load observation session metadata."""
    session_path = session_dir / "metadata" / "session.json"
    if not session_path.exists():
        msg = f"session.json not found in {session_dir}"
        raise FileNotFoundError(msg)
    return ObservationSession.model_validate_json(session_path.read_text(encoding="utf-8"))


def load_manifest(session_dir: Path) -> StorageManifest:
    """Load storage manifest."""
    manifest_path = session_dir / "metadata" / "manifest.json"
    if not manifest_path.exists():
        msg = f"manifest.json not found in {session_dir}"
        raise FileNotFoundError(msg)
    return StorageManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def _iter_partition_files(session_dir: Path, manifest: StorageManifest | None) -> list[Path]:
    if manifest and manifest.partitions:
        files = [session_dir / p.path for p in manifest.partitions]
        return [f for f in files if f.exists()]

    market_dir = session_dir / "market"
    return sorted(market_dir.rglob("events.jsonl.gz"))


def read_events(session_dir: Path, *, manifest: StorageManifest | None = None) -> list[EventEnvelope]:
    """
    Load all events from an archive, sorted by global seq.

    Reads every partition file; merges into deterministic order.
    """
    if manifest is None:
        manifest = load_manifest(session_dir)

    events: list[EventEnvelope] = []
    for path in _iter_partition_files(session_dir, manifest):
        with gzip.open(path, mode="rt", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(EventEnvelope.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError) as exc:
                    msg = f"Corrupt event at {path}:{line_no}: {exc}"
                    raise ValueError(msg) from exc

    events.sort(key=lambda e: e.seq)
    return events


def filter_events(
    events: list[EventEnvelope],
    *,
    start_seq: int | None = None,
    end_seq: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[EventEnvelope]:
    """Filter events by sequence or received_at range."""
    filtered = events
    if start_seq is not None:
        filtered = [e for e in filtered if e.seq >= start_seq]
    if end_seq is not None:
        filtered = [e for e in filtered if e.seq <= end_seq]
    if start_time is not None:
        filtered = [e for e in filtered if e.received_at >= start_time]
    if end_time is not None:
        filtered = [e for e in filtered if e.received_at <= end_time]
    return filtered
