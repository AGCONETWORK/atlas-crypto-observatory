"""Replay manifest v1 contract."""

from datetime import datetime
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from atlas.storage.integrity import IntegrityReport

REPLAY_MANIFEST_VERSION = 1


class ReplayParameters(BaseModel):
    """Parameters that define a reproducible replay run."""

    speed: float = 1.0
    start_seq: int | None = None
    end_seq: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class ReplayCursorState(BaseModel):
    """Final cursor state after replay completes."""

    seq: int
    timestamp: datetime | None = None
    progress_pct: float = 0.0


class ReplayManifest(BaseModel):
    """Audit trail for a replay session. Contract: ReplayManifest v1."""

    manifest_version: int = Field(default=REPLAY_MANIFEST_VERSION)
    replay_id: UUID = Field(default_factory=uuid7)
    source_session_id: UUID
    replay_version: str
    started_at: datetime
    ended_at: datetime | None = None
    parameters: ReplayParameters = Field(default_factory=ReplayParameters)
    integrity_report: IntegrityReport | None = None
    events_emitted: int = 0
    cursor_final: ReplayCursorState | None = None
