"""Tests for Deribit adapter."""

import pytest

from atlas.adapters.deribit import DeribitAdapter, EXCHANGE_ID
from atlas.config.settings import AtlasSettings


def test_capabilities() -> None:
    adapter = DeribitAdapter(AtlasSettings())
    caps = adapter.capabilities

    assert caps.exchange == EXCHANGE_ID
    assert caps.supports_book
    assert caps.supports_ticker
    assert caps.supports_trades
    assert caps.supports_options
    assert caps.supports_authentication
    assert caps.supports_channel("book")
    assert not caps.supports_channel("unknown")


def test_subscribe_not_implemented() -> None:
    adapter = DeribitAdapter(AtlasSettings())
    assert adapter.capabilities.supports_options


@pytest.mark.asyncio
async def test_subscribe_raises() -> None:
    adapter = DeribitAdapter(AtlasSettings())
    with pytest.raises(NotImplementedError, match="v0.3.0"):
        await adapter.subscribe()
