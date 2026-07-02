"""Tests for EventEnvelope v1 and EvidenceObject."""

from datetime import UTC, datetime
from uuid import uuid7

from atlas.core.envelope import EventEnvelope, EvidenceObject
from atlas.core.instrument import InstrumentRef, InstrumentType
from atlas.core.provenance import Provenance
from atlas.core.taxonomy import EventCategory


def test_evidence_object_preserves_payload() -> None:
    original = {"type": "test", "price": 50000.0, "nested": {"a": 1}}
    evidence = EvidenceObject(
        category=EventCategory.MARKET,
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        provenance=Provenance(
            source="deribit",
            adapter_version="0.1.0",
            pipeline_version="0.1.0",
        ),
        payload=original,
    )
    assert evidence.payload == original
    assert evidence.payload is not original


def test_envelope_from_evidence_assigns_seq() -> None:
    session_id = uuid7()
    received = datetime(2026, 7, 2, 14, 32, 1, tzinfo=UTC)
    evidence = EvidenceObject(
        category=EventCategory.MARKET,
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        instrument=InstrumentRef(
            exchange_symbol="BTC-PERPETUAL",
            normalized_symbol="BTC-PERPETUAL",
            instrument_type=InstrumentType.PERPETUAL,
        ),
        provenance=Provenance(
            source="deribit",
            adapter_version="0.1.0",
            pipeline_version="0.1.0",
        ),
        payload={"last_price": 50000},
    )

    envelope = EventEnvelope.from_evidence(
        evidence,
        seq=42,
        session_id=session_id,
        session_label="obs_2026-07-02_deribit",
        received_at=received,
    )

    assert envelope.seq == 42
    assert envelope.session_id == session_id
    assert envelope.received_at == received
    assert envelope.payload == {"last_price": 50000}
    assert envelope.schema_version == 1


def test_replay_clock_only_on_replay() -> None:
    session_id = uuid7()
    replayed = datetime(2026, 7, 5, 10, 0, 0, tzinfo=UTC)
    evidence = EvidenceObject(
        category=EventCategory.MARKET,
        exchange="deribit",
        stream="ticker",
        channel="ticker.BTC-PERPETUAL.100ms",
        provenance=Provenance(
            source="deribit",
            adapter_version="0.1.0",
            pipeline_version="0.1.0",
        ),
        payload={},
    )

    envelope = EventEnvelope.from_evidence(
        evidence,
        seq=1,
        session_id=session_id,
        session_label="obs_test",
        received_at=datetime.now(UTC),
        replayed_at=replayed,
    )
    assert envelope.replayed_at == replayed
