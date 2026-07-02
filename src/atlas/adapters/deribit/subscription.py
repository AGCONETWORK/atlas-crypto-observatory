"""Subscription channel builder and batched public/subscribe."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

from atlas.adapters.deribit.discovery import DiscoveryResult
from atlas.adapters.deribit.instruments import INDEX_CHANNEL
from atlas.core.instrument import Instrument

log = structlog.get_logger(__name__)

DEFAULT_BATCH_SIZE = 200


class SubscribeClient(Protocol):
    """Minimal client interface for subscription requests."""

    def next_request_id(self) -> int: ...

    async def request(self, message: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class SubscriptionPlan:
    """Channels to subscribe, partitioned into batches."""

    channels: list[str] = field(default_factory=list)
    batches: list[list[str]] = field(default_factory=list)
    instrument_channels: dict[str, list[str]] = field(default_factory=dict)

    @property
    def channel_count(self) -> int:
        return len(self.channels)


def build_market_channels(
    instruments: list[Instrument],
    *,
    channel_types: list[str],
    interval: str,
) -> list[str]:
    """Build Deribit channel names for instruments."""
    channels: list[str] = []
    for instrument in instruments:
        for channel_type in channel_types:
            if channel_type not in {"book", "ticker", "trades"}:
                continue
            channels.append(f"{channel_type}.{instrument.exchange_symbol}.{interval}")
    return channels


def build_subscription_plan(
    discovery: DiscoveryResult,
    *,
    channel_types: list[str],
    interval: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    include_index: bool = True,
) -> SubscriptionPlan:
    """Build full subscription plan from discovery result."""
    channels: list[str] = []
    instrument_channels: dict[str, list[str]] = {}

    if include_index:
        channels.append(discovery.index_channel)
        instrument_channels[discovery.index_instrument.exchange_symbol] = [discovery.index_channel]

    tradeable = discovery.tradeable_instruments
    market_channels = build_market_channels(tradeable, channel_types=channel_types, interval=interval)
    channels.extend(market_channels)

    for instrument in tradeable:
        inst_channels = build_market_channels([instrument], channel_types=channel_types, interval=interval)
        instrument_channels[instrument.exchange_symbol] = inst_channels

    batches = [channels[i : i + batch_size] for i in range(0, len(channels), batch_size)]
    return SubscriptionPlan(
        channels=channels,
        batches=batches,
        instrument_channels=instrument_channels,
    )


@dataclass
class SubscriptionResult:
    """Outcome of a subscription attempt."""

    subscribed_channels: list[str] = field(default_factory=list)
    failed_batches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.subscribed_channels)

    @property
    def failed_count(self) -> int:
        return len(self.failed_batches)


class SubscriptionManager:
    """Manages Deribit public/subscribe with batching and reconnect support."""

    def __init__(self, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._batch_size = batch_size
        self._plan: SubscriptionPlan | None = None
        self._last_result: SubscriptionResult | None = None

    @property
    def plan(self) -> SubscriptionPlan | None:
        return self._plan

    @property
    def last_result(self) -> SubscriptionResult | None:
        return self._last_result

    def build_plan(
        self,
        discovery: DiscoveryResult,
        *,
        channel_types: list[str],
        interval: str,
    ) -> SubscriptionPlan:
        self._plan = build_subscription_plan(
            discovery,
            channel_types=channel_types,
            interval=interval,
            batch_size=self._batch_size,
        )
        return self._plan

    async def subscribe_all(self, client: SubscribeClient) -> SubscriptionResult:
        """Execute batched public/subscribe for the current plan."""
        if self._plan is None:
            msg = "Subscription plan not built — call build_plan() first"
            raise RuntimeError(msg)

        result = SubscriptionResult()
        for batch_index, batch in enumerate(self._plan.batches):
            response = await client.request(
                {
                    "jsonrpc": "2.0",
                    "id": client.next_request_id(),
                    "method": "public/subscribe",
                    "params": {"channels": batch},
                }
            )
            if "error" in response:
                log.error(
                    "subscription.batch_failed",
                    batch_index=batch_index,
                    error=response["error"],
                )
                result.failed_batches.append(
                    {"batch_index": batch_index, "channels": batch, "error": response["error"]}
                )
                continue

            subscribed = response.get("result", [])
            result.subscribed_channels.extend(subscribed)
            log.info(
                "subscription.batch_completed",
                batch_index=batch_index,
                channels=len(subscribed),
            )

        self._last_result = result
        log.info(
            "subscription.completed",
            total=len(result.subscribed_channels),
            failed_batches=len(result.failed_batches),
        )
        return result

    async def resubscribe(self, client: SubscribeClient) -> SubscriptionResult:
        """Re-subscribe after reconnect using the existing plan."""
        log.info("subscription.resubscribing")
        return await self.subscribe_all(client)
