"""Tests for Observation Session."""

from uuid import UUID

from atlas.evidence.observation import ObservationSession, make_session_label
from atlas.storage.archive_state import ArchiveState


def test_session_has_uuidv7() -> None:
    session = ObservationSession.create("deribit")
    assert isinstance(session.session_id, UUID)
    assert session.session_label.startswith("obs_")
    assert "deribit" in session.session_label


def test_session_label_format() -> None:
    label = make_session_label("deribit")
    assert label.startswith("obs_")
    assert label.endswith("_deribit")


def test_data_quality_counters() -> None:
    session = ObservationSession.create("deribit")
    session.record_message_received()
    session.record_message_received()
    session.record_message_written()
    assert session.data_quality.messages_received == 2
    assert session.data_quality.messages_written == 1


def test_session_finalize_sets_duration() -> None:
    session = ObservationSession.create("deribit")
    session.finalize()
    assert session.end_time is not None
    assert session.data_quality.recording_duration_seconds >= 0
