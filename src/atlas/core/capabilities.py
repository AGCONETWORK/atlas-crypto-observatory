"""Adapter capability advertisement — exchange-specific features without core conditionals."""

from pydantic import BaseModel, Field


class AdapterCapabilities(BaseModel):
    """Capabilities advertised by an exchange adapter."""

    exchange: str
    adapter_version: str
    supports_book: bool = True
    supports_ticker: bool = True
    supports_trades: bool = True
    supports_options: bool = False
    supports_futures: bool = False
    supports_spot: bool = False
    supports_index: bool = False
    supports_heartbeat: bool = True
    supports_authentication: bool = False
    supports_raw_interval: bool = False
    supported_intervals: list[str] = Field(default_factory=lambda: ["100ms", "agg2"])

    model_config = {"frozen": True}

    def supports_channel(self, channel: str) -> bool:
        """Check whether the adapter supports a named channel type."""
        mapping = {
            "book": self.supports_book,
            "ticker": self.supports_ticker,
            "trades": self.supports_trades,
        }
        return mapping.get(channel, False)
