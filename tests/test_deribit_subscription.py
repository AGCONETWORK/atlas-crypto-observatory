"""Tests for subscription channel building."""

from atlas.adapters.deribit.discovery import DiscoveryResult, select_discovery_universe
from atlas.adapters.deribit.instruments import INDEX_CHANNEL
from atlas.adapters.deribit.subscription import build_subscription_plan


def test_build_subscription_plan() -> None:
    futures = [
        {
            "instrument_name": "BTC-PERPETUAL",
            "kind": "future",
            "settlement_period": "perpetual",
            "is_active": True,
        },
    ]
    discovery = select_discovery_universe(futures=futures, options=[], spot=[], futures_count=3)

    plan = build_subscription_plan(
        discovery,
        channel_types=["ticker", "trades"],
        interval="100ms",
        batch_size=10,
    )

    assert INDEX_CHANNEL in plan.channels
    assert "ticker.BTC-PERPETUAL.100ms" in plan.channels
    assert "trades.BTC-PERPETUAL.100ms" in plan.channels
    assert plan.channel_count == 3
    assert len(plan.batches) == 1


def test_empty_discovery_still_includes_index() -> None:
    discovery = DiscoveryResult()
    plan = build_subscription_plan(
        discovery,
        channel_types=["book"],
        interval="100ms",
    )
    assert plan.channels == [INDEX_CHANNEL]
