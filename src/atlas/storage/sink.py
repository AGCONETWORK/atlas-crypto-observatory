"""Pluggable storage sink interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atlas.core.envelope import EventEnvelope
    from atlas.evidence.observation import ObservationSession


class StorageSink(ABC):
    """
    Pluggable storage backend. Phase 1: JsonlSink.

    Future: ParquetSink, S3Sink, KafkaSink, etc.
    """

    @abstractmethod
    async def open_session(self, session: "ObservationSession") -> None:
        """Prepare storage for a new observation session."""

    @abstractmethod
    async def write(self, event: "EventEnvelope") -> None:
        """Append an immutable event to storage."""

    @abstractmethod
    async def finalize_session(self, session: "ObservationSession") -> None:
        """Finalize partitions, write manifest, update session metadata."""

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""
