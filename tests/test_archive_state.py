"""Tests for archive state machine."""

import pytest

from atlas.storage.archive_state import ArchiveState


def test_valid_transitions() -> None:
    assert ArchiveState.CREATING.can_transition_to(ArchiveState.RECORDING)
    assert ArchiveState.RECORDING.can_transition_to(ArchiveState.FINALIZING)
    assert ArchiveState.FINALIZING.can_transition_to(ArchiveState.COMPLETE)


def test_invalid_transitions() -> None:
    assert not ArchiveState.CREATING.can_transition_to(ArchiveState.COMPLETE)
    assert not ArchiveState.COMPLETE.can_transition_to(ArchiveState.RECORDING)
    assert not ArchiveState.ABORTED.can_transition_to(ArchiveState.RECORDING)


def test_observation_session_state_transition() -> None:
    from atlas.evidence.observation import ObservationSession

    session = ObservationSession.create("deribit")
    session.transition_to(ArchiveState.RECORDING)
    assert session.state == ArchiveState.RECORDING

    with pytest.raises(ValueError, match="Invalid state transition"):
        session.transition_to(ArchiveState.COMPLETE)
