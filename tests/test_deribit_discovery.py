"""Tests for Deribit discovery selection logic."""

from atlas.adapters.deribit.discovery import select_discovery_universe


def _future(name: str, expiry: int, *, perpetual: bool = False) -> dict:
    entry = {
        "instrument_name": name,
        "kind": "future",
        "expiration_timestamp": expiry,
        "is_active": True,
    }
    if perpetual:
        entry["settlement_period"] = "perpetual"
    return entry


def _option(name: str, expiry: int, strike: float) -> dict:
    return {
        "instrument_name": name,
        "kind": "option",
        "expiration_timestamp": expiry,
        "strike": strike,
        "option_type": "call",
        "is_active": True,
    }


def test_select_discovery_universe() -> None:
    futures = [
        _future("BTC-PERPETUAL", 0, perpetual=True),
        _future("BTC-28MAR26", 1000),
        _future("BTC-27JUN26", 2000),
        _future("BTC-26SEP26", 3000),
        _future("BTC-25DEC26", 4000),
    ]
    options = [
        _option("BTC-27JUN26-80000-C", 2000, 80000),
        _option("BTC-27JUN26-90000-C", 2000, 90000),
    ]
    spot = [{"instrument_name": "BTC_USDC", "kind": "spot", "is_active": True}]

    result = select_discovery_universe(
        futures=futures,
        options=options,
        spot=spot,
        futures_count=3,
    )

    assert result.perpetual is not None
    assert result.perpetual.exchange_symbol == "BTC-PERPETUAL"
    assert len(result.nearby_futures) == 3
    assert result.nearby_futures[0].exchange_symbol == "BTC-28MAR26"
    assert len(result.options) == 2
    assert len(result.spot_instruments) == 1
    assert result.summary()["total_instruments"] == 7
