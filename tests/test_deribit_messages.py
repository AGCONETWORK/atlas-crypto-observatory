"""Tests for subscription message parsing."""

from atlas.adapters.deribit.messages import parse_channel_instrument, parse_subscription_message
from atlas.core.instrument import InstrumentType


def test_parse_channel_instrument() -> None:
    ref = parse_channel_instrument("ticker.BTC-PERPETUAL.100ms")
    assert ref is not None
    assert ref.instrument_type == InstrumentType.PERPETUAL


def test_parse_subscription_message() -> None:
    message = {
        "jsonrpc": "2.0",
        "method": "subscription",
        "params": {
            "channel": "ticker.BTC-PERPETUAL.100ms",
            "data": {"timestamp": 1_700_000_000_000, "last_price": 50000},
        },
    }
    channel, instrument, exchange_ts = parse_subscription_message(message)
    assert channel == "ticker.BTC-PERPETUAL.100ms"
    assert instrument is not None
    assert exchange_ts is not None
