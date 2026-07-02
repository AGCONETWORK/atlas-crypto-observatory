"""Optional live Deribit integration tests — skipped unless credentials are set."""

from __future__ import annotations

import os

import pytest

from atlas.adapters.deribit import DeribitAdapter
from atlas.config.settings import AtlasSettings


def _has_deribit_credentials() -> bool:
    settings = AtlasSettings()
    return bool(settings.deribit_api_key and settings.deribit_api_secret)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not _has_deribit_credentials(), reason="Deribit credentials not configured")
async def test_live_connect_and_disconnect() -> None:
    """Smoke test: connect, authenticate, heartbeat, disconnect."""
    settings = AtlasSettings()
    if settings.deribit_environment != "testnet" and os.getenv("ATLAS_INTEGRATION_PRODUCTION") != "1":
        pytest.skip("Set ATLAS_INTEGRATION_PRODUCTION=1 to run against production")

    adapter = DeribitAdapter(settings)
    await adapter.connect()
    assert adapter.client is not None
    assert adapter.client.auth.is_authenticated or not settings.deribit_api_key
    await adapter.disconnect()
