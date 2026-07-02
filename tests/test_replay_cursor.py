"""Tests for replay cursor."""

from datetime import UTC, datetime

from atlas.replay.cursor import ReplayCursor, ReplayState


def test_cursor_progress() -> None:
    cursor = ReplayCursor(total_events=100)
    cursor.advance(1, datetime(2026, 7, 2, tzinfo=UTC))
    assert cursor.emitted == 1
    assert cursor.remaining == 99
    assert cursor.progress_pct == 1.0
    assert cursor.current_seq == 1


def test_cursor_pause_resume() -> None:
    cursor = ReplayCursor(total_events=10, state=ReplayState.PLAYING)
    cursor.pause()
    assert cursor.state == ReplayState.PAUSED
    assert cursor.should_wait()
    cursor.request_step()
    assert not cursor.should_wait()
    cursor.consume_step()
    assert cursor.should_wait()
    cursor.resume()
    assert cursor.state == ReplayState.PLAYING
