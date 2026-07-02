"""JSONL gzip storage sink — Phase 1 implementation."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import structlog

from atlas.core.envelope import EventEnvelope
from atlas.core.taxonomy import EventCategory
from atlas.evidence.observation import ObservationSession
from atlas.core.archive_state import ArchiveState
from atlas.storage.manifest import PartitionEntry, StorageManifest
from atlas.storage.sink import StorageSink

log = structlog.get_logger(__name__)


class JsonlSink(StorageSink):
    """
    Append-only JSONL storage with gzip compression per partition.

    Layout:
      {data_path}/{date}/market/{instrument}/events.jsonl.gz
      {data_path}/{date}/metadata/session.json
      {data_path}/{date}/metadata/manifest.json
    """

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._session: ObservationSession | None = None
        self._session_dir: Path | None = None
        self._open_files: dict[str, gzip.GzipFile] = {}
        self._partition_counts: dict[str, int] = {}
        self._category_counts: dict[str, int] = {}
        self._seq_min: int | None = None
        self._seq_max: int = 0

    async def open_session(self, session: ObservationSession) -> None:
        self._session = session
        date_part = session.start_time.strftime("%Y-%m-%d")
        self._session_dir = self._data_path / date_part
        metadata_dir = self._session_dir / "metadata"
        market_dir = self._session_dir / "market"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        market_dir.mkdir(parents=True, exist_ok=True)

        session_path = metadata_dir / "session.json"
        session_path.write_text(
            session.model_dump_json(indent=2),
            encoding="utf-8",
        )

        manifest = StorageManifest(
            session_id=session.session_id,
            session_label=session.session_label,
            state=ArchiveState.RECORDING,
            created_at=datetime.now(UTC),
        )
        (metadata_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

        await log.ainfo(
            "storage.session_opened",
            session_id=str(session.session_id),
            path=str(self._session_dir),
        )

    def _partition_key(self, event: EventEnvelope) -> str:
        if event.category == EventCategory.MARKET and event.instrument:
            return event.instrument.exchange_symbol
        return f"_{event.category.value.lower()}"

    def _partition_path(self, key: str) -> Path:
        assert self._session_dir is not None
        safe_key = key.replace("/", "_")
        return self._session_dir / "market" / safe_key / "events.jsonl.gz"

    def _get_file(self, key: str) -> gzip.GzipFile:
        if key not in self._open_files:
            path = self._partition_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._open_files[key] = gzip.open(path, mode="at", encoding="utf-8")
            self._partition_counts[key] = 0
        return self._open_files[key]

    async def write(self, event: EventEnvelope) -> None:
        key = self._partition_key(event)
        handle = self._get_file(key)
        line = event.model_dump_json()
        handle.write(line + "\n")

        self._partition_counts[key] = self._partition_counts.get(key, 0) + 1
        cat = event.category.value
        self._category_counts[cat] = self._category_counts.get(cat, 0) + 1

        if self._seq_min is None:
            self._seq_min = event.seq
        self._seq_max = event.seq

    async def finalize_session(self, session: ObservationSession) -> None:
        for handle in self._open_files.values():
            handle.close()
        self._open_files.clear()

        assert self._session_dir is not None
        metadata_dir = self._session_dir / "metadata"

        partitions: list[PartitionEntry] = []
        total_compressed = 0

        for key, count in self._partition_counts.items():
            path = self._partition_path(key)
            if path.exists():
                size = path.stat().st_size
                total_compressed += size
                rel_path = str(path.relative_to(self._session_dir))
                seq_range = None
                if self._seq_min is not None:
                    seq_range = (self._seq_min, self._seq_max)
                partitions.append(
                    PartitionEntry(
                        path=rel_path,
                        event_count=count,
                        compressed_size_bytes=size,
                        uncompressed_size_bytes=0,
                        seq_range=seq_range,
                    )
                )

        manifest = StorageManifest(
            session_id=session.session_id,
            session_label=session.session_label,
            state=ArchiveState.COMPLETE,
            created_at=session.start_time,
            finalized_at=datetime.now(UTC),
            event_count=sum(self._partition_counts.values()),
            categories=dict(self._category_counts),
            partitions=partitions,
        )

        (metadata_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        session_path = metadata_dir / "session.json"
        session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

        await log.ainfo(
            "storage.session_finalized",
            session_id=str(session.session_id),
            event_count=manifest.event_count,
            partitions=len(partitions),
        )

    async def close(self) -> None:
        for handle in self._open_files.values():
            handle.close()
        self._open_files.clear()
