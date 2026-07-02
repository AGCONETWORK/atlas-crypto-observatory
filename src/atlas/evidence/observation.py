"""Observation session — auditable unit of evidence capture."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from atlas import __version__
from atlas.storage.archive_state import ArchiveState


def make_session_label(exchange: str, started_at: datetime | None = None) -> str:
    """Human-readable session label: obs_{date}_{exchange}."""
    ts = started_at or datetime.now(UTC)
    date_part = ts.strftime("%Y-%m-%d")
    return f"obs_{date_part}_{exchange}"


class DataQualityMetrics(BaseModel):
    """Recorder health metrics — not market analytics."""

    messages_received: int = 0
    messages_written: int = 0
    reconnects: int = 0
    heartbeat_failures: int = 0
    subscription_failures: int = 0
    largest_gap_seconds: float = 0.0
    recording_duration_seconds: float = 0.0
    compression_ratio: float = 0.0
    dropped_messages: int = 0


class ObservationSession(BaseModel):
    """
    Every recording is an Observation Session.

    session_id (UUIDv7) is the canonical identifier.
    session_label is human-readable convenience.
    """

    session_id: UUID = Field(default_factory=uuid7)
    session_label: str
    exchange: str
    environment: str = "production"
    pipeline_version: str = __version__
    adapter_version: str = ""
    schema_version: int = 1
    api_version: str = ""
    state: ArchiveState = ArchiveState.CREATING
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    data_quality: DataQualityMetrics = Field(default_factory=DataQualityMetrics)

    @classmethod
    def create(
        cls,
        exchange: str,
        *,
        environment: str = "production",
        adapter_version: str = "",
        api_version: str = "",
    ) -> "ObservationSession":
        start = datetime.now(UTC)
        return cls(
            session_label=make_session_label(exchange, start),
            exchange=exchange,
            environment=environment,
            adapter_version=adapter_version,
            api_version=api_version,
            start_time=start,
        )

    def transition_to(self, new_state: ArchiveState) -> None:
        """Transition archive state with validation."""
        if not self.state.can_transition_to(new_state):
            msg = f"Invalid state transition: {self.state} -> {new_state}"
            raise ValueError(msg)
        self.state = new_state

    def record_message_received(self) -> None:
        self.data_quality.messages_received += 1

    def record_message_written(self) -> None:
        self.data_quality.messages_written += 1

    def finalize(self) -> None:
        """Mark session end time and compute duration."""
        self.end_time = datetime.now(UTC)
        delta = self.end_time - self.start_time
        self.data_quality.recording_duration_seconds = delta.total_seconds()
