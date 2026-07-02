"""Archive integrity validation — pre-replay gate."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from atlas.storage.manifest import StorageManifest


class IntegrityErrorCode(StrEnum):
    MANIFEST_MISSING = "MANIFEST_MISSING"
    SESSION_MISSING = "SESSION_MISSING"
    SESSION_MISMATCH = "SESSION_MISMATCH"
    PARTITION_MISSING = "PARTITION_MISSING"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    CORRUPT_FILE = "CORRUPT_FILE"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    INCOMPLETE_ARCHIVE = "INCOMPLETE_ARCHIVE"


class IntegrityError(BaseModel):
    code: IntegrityErrorCode
    message: str
    path: str | None = None


class IntegrityWarning(BaseModel):
    code: str
    message: str


class IntegrityReport(BaseModel):
    """Result of pre-replay archive validation."""

    valid: bool
    errors: list[IntegrityError] = Field(default_factory=list)
    warnings: list[IntegrityWarning] = Field(default_factory=list)


def validate_manifest_exists(metadata_dir: Path) -> IntegrityReport:
    """Basic validation: manifest and session files exist."""
    report = IntegrityReport(valid=True)
    manifest_path = metadata_dir / "manifest.json"
    session_path = metadata_dir / "session.json"

    if not manifest_path.exists():
        report.valid = False
        report.errors.append(
            IntegrityError(
                code=IntegrityErrorCode.MANIFEST_MISSING,
                message="manifest.json not found",
                path=str(manifest_path),
            )
        )
        return report

    if not session_path.exists():
        report.valid = False
        report.errors.append(
            IntegrityError(
                code=IntegrityErrorCode.SESSION_MISSING,
                message="session.json not found",
                path=str(session_path),
            )
        )

    return report


def validate_partitions(
    session_dir: Path,
    manifest: StorageManifest,
) -> IntegrityReport:
    """Validate all partition paths referenced in manifest exist."""
    report = IntegrityReport(valid=True)

    if manifest.state.value in ("ABORTED", "CREATING", "RECORDING"):
        report.warnings.append(
            IntegrityWarning(
                code="INCOMPLETE_ARCHIVE",
                message=f"Archive state is {manifest.state.value}",
            )
        )

    total_from_partitions = 0
    for partition in manifest.partitions:
        full_path = session_dir / partition.path
        if not full_path.exists():
            report.valid = False
            report.errors.append(
                IntegrityError(
                    code=IntegrityErrorCode.PARTITION_MISSING,
                    message=f"Partition not found: {partition.path}",
                    path=str(full_path),
                )
            )
        total_from_partitions += partition.event_count

    if manifest.partitions and total_from_partitions != manifest.event_count:
        report.valid = False
        report.errors.append(
            IntegrityError(
                code=IntegrityErrorCode.COUNT_MISMATCH,
                message=(
                    f"Manifest event_count ({manifest.event_count}) != "
                    f"partition sum ({total_from_partitions})"
                ),
            )
        )

    return report
