"""Archive lifecycle state machine."""

from enum import StrEnum


class ArchiveState(StrEnum):
    """
    Explicit archive states for crash recovery and audit.

    Transitions:
      CREATING -> RECORDING -> FINALIZING -> COMPLETE
      RECORDING -> ABORTED (crash / kill)
      FINALIZING -> ABORTED (failure during finalize)
      Any validation failure on read -> CORRUPTED (assigned by integrity check)
    """

    CREATING = "CREATING"
    RECORDING = "RECORDING"
    FINALIZING = "FINALIZING"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"
    CORRUPTED = "CORRUPTED"

    def can_transition_to(self, target: "ArchiveState") -> bool:
        """Return whether a transition to target is valid."""
        allowed: dict[ArchiveState, set[ArchiveState]] = {
            ArchiveState.CREATING: {ArchiveState.RECORDING, ArchiveState.ABORTED},
            ArchiveState.RECORDING: {ArchiveState.FINALIZING, ArchiveState.ABORTED},
            ArchiveState.FINALIZING: {ArchiveState.COMPLETE, ArchiveState.ABORTED},
            ArchiveState.COMPLETE: set(),
            ArchiveState.ABORTED: set(),
            ArchiveState.CORRUPTED: set(),
        }
        return target in allowed.get(self, set())
