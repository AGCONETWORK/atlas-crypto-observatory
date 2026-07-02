"""Evidence Builder — transforms adapter output into EvidenceObjects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas import __version__
from atlas.core.envelope import EvidenceObject
from atlas.core.instrument import InstrumentRef
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory


class EvidenceBuilder:
    """
    Builds evidence objects from raw adapter messages.

    Does not interpret market meaning — only classifies and wraps.
    """

    def __init__(self, *, source: str, adapter_version: str) -> None:
        self._source = source
        self._adapter_version = adapter_version

    def _provenance(self) -> Provenance:
        return Provenance(
            source=self._source,
            adapter_version=self._adapter_version,
            pipeline_version=__version__,
            schema_version=1,
        )

    def build_market_evidence(
        self,
        *,
        exchange: str,
        stream: str,
        channel: str,
        payload: dict[str, Any],
        instrument: InstrumentRef | None = None,
        exchange_timestamp: datetime | None = None,
    ) -> EvidenceObject:
        """Wrap a market message as evidence. Payload is stored unchanged."""
        return EvidenceObject(
            category=EventCategory.MARKET,
            exchange=exchange,
            stream=stream,
            channel=channel,
            instrument=instrument,
            exchange_timestamp=exchange_timestamp,
            provenance=self._provenance(),
            payload=payload,
        )

    def build_lifecycle_evidence(
        self,
        *,
        category: EventCategory,
        exchange: str,
        stream: str,
        channel: str,
        payload: dict[str, Any],
    ) -> EvidenceObject:
        """Wrap a lifecycle/metadata event as evidence."""
        if category not in {
            EventCategory.SYSTEM,
            EventCategory.CONNECTION,
            EventCategory.SUBSCRIPTION,
            EventCategory.RECORDER,
            EventCategory.STORAGE,
        }:
            msg = f"Invalid lifecycle category: {category}"
            raise ValueError(msg)

        return EvidenceObject(
            category=category,
            exchange=exchange,
            stream=stream,
            channel=channel,
            provenance=self._provenance(),
            payload={
                **payload,
                "observed_at": datetime.now(UTC).isoformat(),
            },
        )
