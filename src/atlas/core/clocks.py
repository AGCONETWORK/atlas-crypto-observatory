"""Three-clock model: exchange, recorder, and replay time."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ClockKind(StrEnum):
    """Conceptual clock ownership — avoids conflating logical and physical time."""

    EXCHANGE = "exchange"  # When the exchange says the event occurred
    RECORDER = "recorder"  # When evidence arrived at the pipeline
    REPLAY = "replay"  # When evidence is re-emitted during replay


class EventClocks(BaseModel):
    """Explicit separation of logical time from physical time."""

    exchange_timestamp: datetime | None = Field(
        default=None,
        description="Exchange Clock: exchange-native event time",
    )
    received_at: datetime | None = Field(
        default=None,
        description="Recorder Clock: when evidence arrived at ingest",
    )
    replayed_at: datetime | None = Field(
        default=None,
        description="Replay Clock: when evidence was re-emitted (replay only)",
    )

    model_config = {"frozen": True}
