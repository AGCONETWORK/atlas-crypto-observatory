"""Storage manifest v1 contract."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from atlas.storage.archive_state import ArchiveState

STORAGE_MANIFEST_VERSION = 1


class PartitionEntry(BaseModel):
    """A single immutable partition in the archive."""

    path: str
    event_count: int = Field(ge=0)
    compressed_size_bytes: int = Field(ge=0)
    uncompressed_size_bytes: int = Field(ge=0)
    sha256: str = ""
    seq_range: tuple[int, int] | None = None


class ArchiveTotals(BaseModel):
    """Aggregate archive size metrics."""

    total_compressed_size_bytes: int = Field(ge=0)
    total_uncompressed_size_bytes: int = Field(ge=0)
    compression_ratio: float = Field(ge=0.0)
    manifest_sha256: str = ""


class StorageManifest(BaseModel):
    """Table of contents for an observation archive. Contract: StorageManifest v1."""

    manifest_version: int = Field(default=STORAGE_MANIFEST_VERSION)
    session_id: UUID
    session_label: str
    schema_version: int = 1
    state: ArchiveState = ArchiveState.CREATING
    created_at: datetime
    finalized_at: datetime | None = None
    event_count: int = Field(default=0, ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    partitions: list[PartitionEntry] = Field(default_factory=list)
    archive: ArchiveTotals | None = None
