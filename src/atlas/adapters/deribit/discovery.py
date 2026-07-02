"""Instrument discovery via Deribit public/get_instruments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from atlas.adapters.deribit.instruments import INDEX_CHANNEL, index_instrument_ref, parse_deribit_instrument
from atlas.core.instrument import Instrument, InstrumentRef, InstrumentType

PERPETUAL_NAME = "BTC-PERPETUAL"


@dataclass
class DiscoveryResult:
    """Universe of instruments selected for subscription."""

    index_channel: str = INDEX_CHANNEL
    index_instrument: InstrumentRef = field(default_factory=index_instrument_ref)
    perpetual: Instrument | None = None
    spot_instruments: list[Instrument] = field(default_factory=list)
    nearby_futures: list[Instrument] = field(default_factory=list)
    options: list[Instrument] = field(default_factory=list)

    @property
    def tradeable_instruments(self) -> list[Instrument]:
        """All instrument-backed channels (excludes index)."""
        items: list[Instrument] = []
        if self.perpetual:
            items.append(self.perpetual)
        items.extend(self.spot_instruments)
        items.extend(self.nearby_futures)
        items.extend(self.options)
        return items

    @property
    def instrument_count(self) -> int:
        return len(self.tradeable_instruments)

    def summary(self) -> dict[str, int]:
        return {
            "perpetual": 1 if self.perpetual else 0,
            "spot": len(self.spot_instruments),
            "futures": len(self.nearby_futures),
            "options": len(self.options),
            "total_instruments": self.instrument_count,
        }


def _is_perpetual(entry: dict[str, Any]) -> bool:
    name = entry.get("instrument_name", "")
    if name == PERPETUAL_NAME:
        return True
    return entry.get("settlement_period") == "perpetual" or "PERPETUAL" in name.upper()


def _to_instrument(entry: dict[str, Any]) -> Instrument:
    return parse_deribit_instrument(
        entry["instrument_name"],
        kind=entry.get("kind"),
        expiration_timestamp=entry.get("expiration_timestamp"),
        strike=entry.get("strike"),
        option_type=entry.get("option_type"),
    )


def select_discovery_universe(
    *,
    futures: list[dict[str, Any]],
    options: list[dict[str, Any]],
    spot: list[dict[str, Any]],
    futures_count: int = 3,
) -> DiscoveryResult:
    """
    Select BTC spot, perpetual, nearest dated futures, and full options chain.

    Pure function — testable without API calls.
    """
    result = DiscoveryResult()

    perpetual_entry = next((f for f in futures if _is_perpetual(f)), None)
    if perpetual_entry:
        result.perpetual = _to_instrument(perpetual_entry)

    for entry in spot:
        if entry.get("is_active", True):
            result.spot_instruments.append(_to_instrument(entry))

    dated = [
        f
        for f in futures
        if not _is_perpetual(f) and f.get("is_active", True)
    ]
    dated.sort(key=lambda f: f.get("expiration_timestamp") or 0)
    result.nearby_futures = [_to_instrument(f) for f in dated[:futures_count]]

    active_options = [o for o in options if o.get("is_active", True)]
    active_options.sort(key=lambda o: (o.get("expiration_timestamp") or 0, o.get("strike") or 0))
    result.options = [_to_instrument(o) for o in active_options]

    return result


async def fetch_instruments(
    client: Any,
    *,
    currency: str = "BTC",
    kind: str,
    expired: bool = False,
) -> list[dict[str, Any]]:
    """Fetch instruments from Deribit via WebSocket JSON-RPC."""
    response = await client.request(
        {
            "jsonrpc": "2.0",
            "id": client.next_request_id(),
            "method": "public/get_instruments",
            "params": {
                "currency": currency,
                "kind": kind,
                "expired": expired,
            },
        }
    )
    if "error" in response:
        msg = f"get_instruments failed for kind={kind}: {response['error']}"
        raise RuntimeError(msg)
    return list(response.get("result", []))


async def discover_btc_universe(
    client: Any,
    *,
    currency: str = "BTC",
    futures_count: int = 3,
) -> DiscoveryResult:
    """Discover the full BTC subscription universe from Deribit."""
    futures = await fetch_instruments(client, currency=currency, kind="future")
    options = await fetch_instruments(client, currency=currency, kind="option")
    spot = await fetch_instruments(client, currency=currency, kind="spot")
    return select_discovery_universe(
        futures=futures,
        options=options,
        spot=spot,
        futures_count=futures_count,
    )
