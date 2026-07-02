"""Tests for recording health monitor."""

from datetime import UTC, datetime, timedelta

from atlas.recording.health import HealthMonitor


def test_health_monitor_tracks_message_rate() -> None:
    monitor = HealthMonitor(stale_threshold_seconds=120.0)
    monitor.record_message()
    monitor.record_message()

    snapshot = monitor.snapshot()
    assert snapshot.messages_total == 2
    assert snapshot.messages_per_second >= 0.0
    assert snapshot.is_stale is False


def test_health_monitor_detects_staleness() -> None:
    monitor = HealthMonitor(stale_threshold_seconds=1.0)
    monitor._last_message_at = datetime.now(UTC) - timedelta(seconds=5)  # noqa: SLF001

    snapshot = monitor.snapshot()
    assert snapshot.is_stale is True
    assert snapshot.seconds_since_last_message is not None
    assert snapshot.seconds_since_last_message > 1.0
