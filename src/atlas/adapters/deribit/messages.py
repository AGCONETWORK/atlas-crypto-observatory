"""Parse instrument and timestamp from Deribit subscription messages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.adapters.deribit.instruments import INDEX_CHANNEL, index_instrument_ref, instrument_ref_from_name
from atlas.core.instrument import InstrumentRef


def parse_channel_instrument(channel: str) -> InstrumentRef | None:
    """Extract instrument reference from a Deribit channel name."""
    if channel == INDEX_CHANNEL:
        return index_instrument_ref()

    parts = channel.split(".")
    if len(parts) < 2:
        return None

    stream = parts[0]
    if stream in {"book", "ticker", "trades"}:
        return instrument_ref_from_name(parts[1])

    if stream == "deribit_price_index":
        return index_instrument_ref()

    return instrument_ref_from_name(parts[1])


def parse_exchange_timestamp(data: dict[str, Any]) -> datetime | None:
    """Extract exchange-native timestamp from subscription payload when present."""
    ts = data.get("timestamp")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def parse_subscription_message(message: dict[str, Any]) -> tuple[str, InstrumentRef | None, datetime | None]:
    """Return (channel, instrument, exchange_timestamp) from a subscription message."""
    params = message.get("params", {})
    channel = params.get("channel", "unknown")
    data = params.get("data", {})
    if not isinstance(data, dict):
        data = {}

    instrument = parse_channel_instrument(channel)
    exchange_ts = parse_exchange_timestamp(data)
    return channel, instrument, exchange_ts
