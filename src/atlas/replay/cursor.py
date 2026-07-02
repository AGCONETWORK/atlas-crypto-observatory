"""Replay cursor — position, progress, and playback controls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ReplayState(StrEnum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass
class ReplayCursor:
    """
    Tracks replay position and exposes progress metrics.

    Contract: ReplayCursor v1
    """

    total_events: int
    current_index: int = 0
    current_seq: int | None = None
    current_timestamp: datetime | None = None
    state: ReplayState = ReplayState.IDLE
    _step_requested: bool = field(default=False, repr=False)

    @property
    def emitted(self) -> int:
        return self.current_index

    @property
    def remaining(self) -> int:
        return max(0, self.total_events - self.current_index)

    @property
    def progress_pct(self) -> float:
        if self.total_events == 0:
            return 100.0
        return round((self.current_index / self.total_events) * 100, 2)

    def advance(self, seq: int, timestamp: datetime) -> None:
        self.current_index += 1
        self.current_seq = seq
        self.current_timestamp = timestamp

    def pause(self) -> None:
        self.state = ReplayState.PAUSED

    def resume(self) -> None:
        self.state = ReplayState.PLAYING
        self._step_requested = False

    def request_step(self) -> None:
        """Allow one event through while paused."""
        self._step_requested = True

    def should_wait(self) -> bool:
        return self.state == ReplayState.PAUSED and not self._step_requested

    def consume_step(self) -> None:
        self._step_requested = False

    async def wait_while_paused(self) -> None:
        while self.should_wait():
            await asyncio.sleep(0.05)

    def mark_completed(self) -> None:
        self.state = ReplayState.COMPLETED

    def mark_stopped(self) -> None:
        self.state = ReplayState.STOPPED
