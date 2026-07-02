"""Recording health metrics — recorder health, not market analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class HealthSnapshot:
    """Point-in-time recording health snapshot."""

    messages_total: int = 0
    messages_per_second: float = 0.0
    last_message_at: datetime | None = None
    seconds_since_last_message: float | None = None
    reconnects: int = 0
    heartbeat_failures: int = 0
    is_stale: bool = False


@dataclass
class HealthMonitor:
    """
    Tracks ingest rate and staleness during live recording.

    Stale threshold: no market message for N seconds (default 120).
    """

    stale_threshold_seconds: float = 120.0
    _messages_total: int = 0
    _window_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    _window_count: int = 0
    _last_message_at: datetime | None = None
    reconnects: int = 0
    heartbeat_failures: int = 0

    def record_message(self) -> None:
        now = datetime.now(UTC)
        self._messages_total += 1
        self._window_count += 1
        self._last_message_at = now

    def snapshot(self) -> HealthSnapshot:
        now = datetime.now(UTC)
        elapsed = (now - self._window_start).total_seconds()
        rate = self._window_count / elapsed if elapsed > 0 else 0.0

        seconds_since = None
        is_stale = False
        if self._last_message_at:
            seconds_since = (now - self._last_message_at).total_seconds()
            is_stale = seconds_since > self.stale_threshold_seconds

        return HealthSnapshot(
            messages_total=self._messages_total,
            messages_per_second=round(rate, 2),
            last_message_at=self._last_message_at,
            seconds_since_last_message=round(seconds_since, 2) if seconds_since is not None else None,
            reconnects=self.reconnects,
            heartbeat_failures=self.heartbeat_failures,
            is_stale=is_stale,
        )

    def reset_window(self) -> None:
        self._window_start = datetime.now(UTC)
        self._window_count = 0
