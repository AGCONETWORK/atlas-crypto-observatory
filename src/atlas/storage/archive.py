"""Archive path resolution and session discovery."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID


def resolve_session_dir(data_path: Path, session: str) -> Path:
    """
    Resolve a session directory from a path, UUID, or date.

    - Absolute/existing path → used directly
    - UUID → search under data_path
    - YYYY-MM-DD → latest session under that date
    """
    candidate = Path(session)
    if candidate.is_dir():
        return candidate.resolve()

    # UUID lookup
    try:
        UUID(session)
    except ValueError:
        pass
    else:
        matches = list(data_path.rglob(session))
        dirs = [p for p in matches if p.is_dir() and (p / "metadata").exists()]
        if not dirs:
            msg = f"No archive found for session_id={session}"
            raise FileNotFoundError(msg)
        if len(dirs) > 1:
            dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return dirs[0].resolve()

    # Date lookup YYYY-MM-DD
    date_dir = data_path / session
    if date_dir.is_dir():
        sessions = sorted(
            [p for p in date_dir.iterdir() if p.is_dir() and (p / "metadata").exists()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not sessions:
            msg = f"No sessions found under {date_dir}"
            raise FileNotFoundError(msg)
        return sessions[0].resolve()

    msg = f"Could not resolve session: {session}"
    raise FileNotFoundError(msg)


def list_session_dirs(data_path: Path) -> list[Path]:
    """List all session directories under data_path."""
    return sorted(
        [
            p
            for p in data_path.rglob("metadata")
            if p.is_dir() and (p.parent / "market").exists()
        ],
        key=lambda p: p.parent.stat().st_mtime,
        reverse=True,
    )
