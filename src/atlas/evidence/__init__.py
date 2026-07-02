"""Evidence layer public API.

Import submodules directly to avoid circular imports at package load time:
  from atlas.evidence.builder import EvidenceBuilder
  from atlas.evidence.observation import ObservationSession
"""

from atlas.evidence.builder import EvidenceBuilder

__all__ = ["EvidenceBuilder"]
