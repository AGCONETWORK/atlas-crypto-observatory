"""Deribit exchange adapter."""

from atlas.adapters.deribit.adapter import DeribitAdapter
from atlas.adapters.deribit.auth import DeribitAuthState, DeribitCredentials
from atlas.adapters.deribit.client import DeribitClientConfig, DeribitWebSocketClient
from atlas.adapters.deribit.constants import ADAPTER_VERSION, EXCHANGE_ID
from atlas.adapters.deribit.discovery import DiscoveryResult, discover_btc_universe
from atlas.adapters.deribit.subscription import SubscriptionManager, SubscriptionResult

__all__ = [
    "ADAPTER_VERSION",
    "DeribitAdapter",
    "DeribitAuthState",
    "DeribitClientConfig",
    "DeribitCredentials",
    "DeribitWebSocketClient",
    "DiscoveryResult",
    "EXCHANGE_ID",
    "SubscriptionManager",
    "SubscriptionResult",
    "discover_btc_universe",
]
