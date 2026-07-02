"""Stable event taxonomy for all exchanges and consumers."""

from enum import StrEnum


class EventCategory(StrEnum):
    """Explicit event taxonomy — stable across adapters and replay."""

    MARKET = "MARKET"
    SYSTEM = "SYSTEM"
    CONNECTION = "CONNECTION"
    SUBSCRIPTION = "SUBSCRIPTION"
    RECORDER = "RECORDER"
    STORAGE = "STORAGE"
