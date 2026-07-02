"""Archive integrity validation — pre-replay gate."""

from __future__ import annotations

import gzip
import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from atlas.evidence.observation import ObservationSession
from atlas.storage.manifest import StorageManifest
from atlas.storage.reader import load_manifest, load_session


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


def _merge_reports(target: IntegrityReport, other: IntegrityReport) -> IntegrityReport:
    if not other.valid:
        target.valid = False
    target.errors.extend(other.errors)
    target.warnings.extend(other.warnings)
    return target


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
            continue
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


def validate_readable_partitions(
    session_dir: Path,
    manifest: StorageManifest,
) -> IntegrityReport:
    """Verify partition files are readable and line counts match."""
    report = IntegrityReport(valid=True)

    for partition in manifest.partitions:
        full_path = session_dir / partition.path
        if not full_path.exists():
            continue

        try:
            line_count = 0
            with gzip.open(full_path, mode="rt", encoding="utf-8") as handle:
                for line_no, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    json.loads(line)
                    line_count += 1
        except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
            report.valid = False
            report.errors.append(
                IntegrityError(
                    code=IntegrityErrorCode.CORRUPT_FILE,
                    message=str(exc),
                    path=str(full_path),
                )
            )
            continue

        if line_count != partition.event_count:
            report.valid = False
            report.errors.append(
                IntegrityError(
                    code=IntegrityErrorCode.COUNT_MISMATCH,
                    message=(
                        f"Partition {partition.path}: expected {partition.event_count} "
                        f"events, found {line_count}"
                    ),
                    path=str(full_path),
                )
            )

    return report


def validate_session_match(session: ObservationSession, manifest: StorageManifest) -> IntegrityReport:
    """Verify session.json matches manifest.json."""
    report = IntegrityReport(valid=True)
    if session.session_id != manifest.session_id:
        report.valid = False
        report.errors.append(
            IntegrityError(
                code=IntegrityErrorCode.SESSION_MISMATCH,
                message=(
                    f"session_id mismatch: session={session.session_id} "
                    f"manifest={manifest.session_id}"
                ),
            )
        )
    return report


def validate_archive(session_dir: Path, *, strict_sequence: bool = False) -> IntegrityReport:
    """
    Full pre-replay validation gate.

    Returns report with valid=False if replay should not proceed.
    """
    report = IntegrityReport(valid=True)
    metadata_dir = session_dir / "metadata"

    _merge_reports(report, validate_manifest_exists(metadata_dir))
    if not report.valid:
        return report

    try:
        session = load_session(session_dir)
        manifest = load_manifest(session_dir)
    except (FileNotFoundError, ValueError) as exc:
        report.valid = False
        report.errors.append(
            IntegrityError(
                code=IntegrityErrorCode.CORRUPT_FILE,
                message=str(exc),
                path=str(session_dir),
            )
        )
        return report

    _merge_reports(report, validate_session_match(session, manifest))
    _merge_reports(report, validate_partitions(session_dir, manifest))
    if report.valid:
        _merge_reports(report, validate_readable_partitions(session_dir, manifest))

    if strict_sequence and report.valid:
        from atlas.storage.reader import read_events

        events = read_events(session_dir, manifest=manifest)
        for i in range(1, len(events)):
            if events[i].seq != events[i - 1].seq + 1:
                report.valid = False
                report.errors.append(
                    IntegrityError(
                        code=IntegrityErrorCode.SEQUENCE_GAP,
                        message=(
                            f"Sequence gap between {events[i-1].seq} and {events[i].seq}"
                        ),
                    )
                )
                break

    return report
