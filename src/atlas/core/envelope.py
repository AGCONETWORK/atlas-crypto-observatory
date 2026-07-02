"""EventEnvelope v1 and EvidenceObject — versioned contracts."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from atlas.core.instrument import InstrumentRef
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory

# Contract version identifiers — bump when breaking changes occur.
EVENT_ENVELOPE_VERSION = 1
EVIDENCE_OBJECT_VERSION = 1


class EvidenceObject(BaseModel):
    """
    Pre-pipeline evidence unit produced by the Evidence Builder.

    The pipeline assigns seq and received_at; payload is never modified.
  Contract: EvidenceObject v1
    """

    schema_version: int = Field(default=EVIDENCE_OBJECT_VERSION)
    category: EventCategory
    exchange: str
    stream: str
    channel: str
    instrument: InstrumentRef | None = None
    exchange_timestamp: datetime | None = None
    provenance: Provenance
    payload: dict[str, Any]

    model_config = {"frozen": True}


class EventEnvelope(BaseModel):
    """
    Persisted and bus-published event. Contract: EventEnvelope v1.

    seq is assigned per observation session (not per exchange globally).
    """

    schema_version: int = Field(default=EVENT_ENVELOPE_VERSION)
    seq: int = Field(ge=1, description="Monotonic sequence within observation session")
    session_id: UUID = Field(description="Canonical session identifier (UUIDv7)")
    session_label: str = Field(description="Human-readable session label")
    category: EventCategory
    received_at: datetime = Field(description="Recorder Clock: ingest timestamp (UTC)")
    exchange: str
    stream: str
    channel: str
    instrument: InstrumentRef | None = None
    exchange_timestamp: datetime | None = Field(
        default=None,
        description="Exchange Clock: exchange-native timestamp when available",
    )
    replayed_at: datetime | None = Field(
        default=None,
        description="Replay Clock: set only when emitted during replay",
    )
    provenance: Provenance
    payload: dict[str, Any]

    model_config = {"frozen": True}

    @classmethod
    def from_evidence(
        cls,
        evidence: EvidenceObject,
        *,
        seq: int,
        session_id: UUID,
        session_label: str,
        received_at: datetime,
        replayed_at: datetime | None = None,
    ) -> "EventEnvelope":
        """Wrap evidence into a pipeline envelope without modifying payload."""
        return cls(
            seq=seq,
            session_id=session_id,
            session_label=session_label,
            category=evidence.category,
            received_at=received_at,
            exchange=evidence.exchange,
            stream=evidence.stream,
            channel=evidence.channel,
            instrument=evidence.instrument,
            exchange_timestamp=evidence.exchange_timestamp,
            replayed_at=replayed_at,
            provenance=evidence.provenance,
            payload=evidence.payload,
        )
