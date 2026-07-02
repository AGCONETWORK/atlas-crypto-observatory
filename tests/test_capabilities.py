"""Tests for adapter capabilities."""

from atlas.core.capabilities import AdapterCapabilities


def test_capabilities_supports_channel() -> None:
    caps = AdapterCapabilities(
        exchange="deribit",
        adapter_version="0.1.0",
        supports_book=True,
        supports_ticker=True,
        supports_trades=True,
        supports_options=True,
        supports_authentication=True,
    )
    assert caps.supports_channel("book")
    assert caps.supports_channel("ticker")
    assert caps.supports_channel("trades")
    assert not caps.supports_channel("unknown")
