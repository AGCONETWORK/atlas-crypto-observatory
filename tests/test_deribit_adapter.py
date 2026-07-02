"""Tests for Deribit adapter."""

import pytest

from atlas.adapters.deribit import DeribitAdapter
from atlas.adapters.deribit.constants import EXCHANGE_ID
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


@pytest.mark.asyncio
async def test_subscribe_requires_connection() -> None:
    adapter = DeribitAdapter(AtlasSettings())
    with pytest.raises(RuntimeError, match="Not connected"):
        await adapter.subscribe()


@pytest.mark.asyncio
async def test_discover_requires_connection() -> None:
    adapter = DeribitAdapter(AtlasSettings())
    with pytest.raises(RuntimeError, match="Not connected"):
        await adapter.discover()
