"""Deribit exchange adapter — connection layer for v0.2.0."""

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

    v0.2.0: connect, authenticate, heartbeat, reconnect, graceful shutdown.
    Subscriptions arrive in v0.3.0.
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

    async def _emit_connection_evidence(self, stream: str, payload: dict[str, Any]) -> None:
        evidence = self._builder.build_lifecycle_evidence(
            category=EventCategory.CONNECTION,
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
            on_lifecycle=self._on_lifecycle,
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

    async def subscribe(self) -> None:
        """Subscribe to market channels — implemented in v0.3.0."""
        msg = "Deribit subscriptions are implemented in v0.3.0"
        raise NotImplementedError(msg)

    async def _on_lifecycle(self, event: str, payload: dict[str, Any]) -> None:
        await self._emit_connection_evidence(event, payload)

    async def _on_market_message(self, message: dict[str, Any]) -> None:
        """Forward market messages as evidence — wired fully in v0.3.0+."""
        if self._evidence_handler is None:
            return

        params = message.get("params", {})
        channel = params.get("channel", "unknown")
        stream = channel.split(".")[0] if "." in channel else "unknown"

        evidence = self._builder.build_market_evidence(
            exchange=EXCHANGE_ID,
            stream=stream,
            channel=channel,
            payload=message,
        )
        await self._evidence_handler(evidence)

    async def run(self, bus: Any = None) -> None:
        """
        Maintain connection until cancelled.

        Optional bus argument reserved for future direct bus wiring.
        Prefer evidence_handler in constructor for pipeline integration.
        """
        _ = bus
        await self.connect()
        assert self._client is not None
        self._run_task = asyncio.create_task(self._client.run_until_shutdown())
        try:
            await self._run_task
        except asyncio.CancelledError:
            await self.disconnect()
            raise
