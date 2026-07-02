"""Deribit exchange adapter — connection, discovery, and subscriptions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from atlas.adapters.base import ExchangeAdapter
from atlas.adapters.deribit.auth import DeribitCredentials
from atlas.adapters.deribit.client import DeribitClientConfig, DeribitWebSocketClient
from atlas.adapters.deribit.constants import (
    ADAPTER_VERSION,
    EXCHANGE_ID,
    PRODUCTION_WS_URL,
    TESTNET_WS_URL,
)
from atlas.adapters.deribit.discovery import DiscoveryResult, discover_btc_universe
from atlas.adapters.deribit.messages import parse_subscription_message
from atlas.adapters.deribit.subscription import SubscriptionManager, SubscriptionResult
from atlas.config.settings import AtlasSettings
from atlas.core.capabilities import AdapterCapabilities
from atlas.core.envelope import EvidenceObject
from atlas.core.taxonomy import EventCategory
from atlas.evidence.builder import EvidenceBuilder

log = structlog.get_logger(__name__)

EvidenceHandler = Callable[[EvidenceObject], Awaitable[None]]


class DeribitAdapter(ExchangeAdapter):
    """
    Deribit-specific adapter. Exchange logic lives only here.

    v0.3.0: instrument discovery and market data subscriptions.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        evidence_handler: EvidenceHandler | None = None,
    ) -> None:
        self._settings = settings
        self._evidence_handler = evidence_handler
        self._builder = EvidenceBuilder(source=EXCHANGE_ID, adapter_version=ADAPTER_VERSION)
        self._client: DeribitWebSocketClient | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._discovery: DiscoveryResult | None = None
        self._subscriptions = SubscriptionManager()
        self._message_count = 0

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            exchange=EXCHANGE_ID,
            adapter_version=ADAPTER_VERSION,
            supports_book=True,
            supports_ticker=True,
            supports_trades=True,
            supports_options=True,
            supports_futures=True,
            supports_spot=True,
            supports_index=True,
            supports_heartbeat=True,
            supports_authentication=True,
            supports_raw_interval=True,
            supported_intervals=["raw", "100ms", "agg2"],
        )

    @property
    def client(self) -> DeribitWebSocketClient | None:
        return self._client

    @property
    def discovery(self) -> DiscoveryResult | None:
        return self._discovery

    @property
    def message_count(self) -> int:
        return self._message_count

    def _ws_url(self) -> str:
        if self._settings.deribit_environment == "testnet":
            return TESTNET_WS_URL
        return PRODUCTION_WS_URL

    def _credentials(self) -> DeribitCredentials | None:
        if not self._settings.deribit_api_key:
            return None
        return DeribitCredentials(
            client_id=self._settings.deribit_api_key,
            client_secret=self._settings.deribit_api_secret,
        )

    def _client_config(self) -> DeribitClientConfig:
        return DeribitClientConfig(
            ws_url=self._ws_url(),
            credentials=self._credentials(),
            heartbeat_interval=self._settings.deribit_heartbeat_interval,
            reconnect_base_delay=self._settings.deribit_reconnect_base_delay,
            reconnect_max_delay=self._settings.deribit_reconnect_max_delay,
        )

    async def _emit_lifecycle(
        self,
        category: EventCategory,
        stream: str,
        payload: dict[str, Any],
    ) -> None:
        evidence = self._builder.build_lifecycle_evidence(
            category=category,
            exchange=EXCHANGE_ID,
            stream=stream,
            channel=stream,
            payload=payload,
        )
        if self._evidence_handler:
            await self._evidence_handler(evidence)

    async def connect(self) -> None:
        """Establish connection to Deribit."""
        if self._client is not None:
            return

        self._client = DeribitWebSocketClient(
            self._client_config(),
            on_message=self._on_market_message,
            on_lifecycle=self._on_connection_lifecycle,
            on_reconnected=self._on_reconnected,
        )
        await self._client.connect()
        log.info(
            "adapter.connected",
            exchange=EXCHANGE_ID,
            environment=self._settings.deribit_environment,
        )

    async def disconnect(self) -> None:
        """Gracefully shut down the adapter."""
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass

        if self._client is not None:
            await self._client.disconnect()
            self._client = None

        log.info("adapter.disconnected", exchange=EXCHANGE_ID)

    async def discover(self) -> DiscoveryResult:
        """Discover BTC instrument universe via public/get_instruments."""
        if self._client is None:
            msg = "Not connected — call connect() first"
            raise RuntimeError(msg)

        self._discovery = await discover_btc_universe(
            self._client,
            futures_count=self._settings.futures_count,
        )
        summary = self._discovery.summary()
        log.info("discovery.completed", **summary)
        await self._emit_lifecycle(EventCategory.SYSTEM, "discovery.completed", summary)
        return self._discovery

    async def subscribe(self) -> SubscriptionResult:
        """Discover instruments (if needed) and subscribe to configured channels."""
        if self._client is None:
            msg = "Not connected — call connect() first"
            raise RuntimeError(msg)

        if self._discovery is None:
            await self.discover()

        assert self._discovery is not None
        plan = self._subscriptions.build_plan(
            self._discovery,
            channel_types=self._settings.channel_list,
            interval=self._settings.interval,
        )
        log.info(
            "subscription.plan_built",
            instruments=self._discovery.instrument_count,
            channels=plan.channel_count,
            batches=len(plan.batches),
        )

        result = await self._subscriptions.subscribe_all(self._client)

        if result.failed_batches:
            await self._emit_lifecycle(
                EventCategory.SUBSCRIPTION,
                "subscription.failed",
                {
                    "failed_batches": len(result.failed_batches),
                    "subscribed": result.success_count,
                },
            )
        else:
            await self._emit_lifecycle(
                EventCategory.SUBSCRIPTION,
                "subscription.completed",
                {
                    "subscribed": result.success_count,
                    "channels": plan.channel_count,
                    "instruments": self._discovery.instrument_count,
                },
            )

        return result

    async def _on_reconnected(self) -> None:
        """Re-subscribe after automatic reconnect."""
        if self._subscriptions.plan is None:
            return
        log.info("adapter.resubscribing_after_reconnect")
        await self._subscriptions.resubscribe(self._client)  # type: ignore[arg-type]

    async def _on_connection_lifecycle(self, event: str, payload: dict[str, Any]) -> None:
        await self._emit_lifecycle(EventCategory.CONNECTION, event, payload)

    async def _on_market_message(self, message: dict[str, Any]) -> None:
        """Forward market subscription messages as evidence."""
        if self._evidence_handler is None:
            return

        channel, instrument, exchange_ts = parse_subscription_message(message)
        stream = channel.split(".")[0] if "." in channel else "unknown"
        self._message_count += 1

        evidence = self._builder.build_market_evidence(
            exchange=EXCHANGE_ID,
            stream=stream,
            channel=channel,
            payload=message,
            instrument=instrument,
            exchange_timestamp=exchange_ts,
        )
        await self._evidence_handler(evidence)

    async def run(self, bus: Any = None) -> None:
        """Connect, subscribe, and maintain until cancelled."""
        _ = bus
        await self.connect()
        await self.subscribe()
        assert self._client is not None
        self._run_task = asyncio.create_task(self._client.run_until_shutdown())
        try:
            await self._run_task
        except asyncio.CancelledError:
            await self.disconnect()
            raise
