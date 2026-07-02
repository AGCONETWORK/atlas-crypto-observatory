"""Exchange adapter protocol — implementations live in adapters/."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from atlas.core.capabilities import AdapterCapabilities

if TYPE_CHECKING:
    from atlas.bus.event_bus import EventBus


class ExchangeAdapter(ABC):
    """
    Base protocol for exchange-specific adapters.

    Adapters connect to exchanges and inject evidence into the Event Bus
    via the Evidence Builder and Pipeline.
    """

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Advertise adapter capabilities to the core."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the exchange."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close connection."""

    @abstractmethod
    async def subscribe(self) -> None:
        """Subscribe to configured market data channels."""

    @abstractmethod
    async def run(self, bus: "EventBus") -> None:
        """Run the adapter, publishing evidence through the pipeline."""
