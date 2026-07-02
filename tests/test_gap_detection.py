"""Tests for gap detection on reconnect."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import websockets

from atlas.adapters.deribit.client import DeribitClientConfig, DeribitWebSocketClient
from atlas.adapters.deribit.constants import TESTNET_WS_URL


class DisconnectingFakeWebSocket:
    """WebSocket mock used for reconnect testing."""

    def __init__(self) -> None:
        self._incoming: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[str] = []
        self._closed = False

    def __aiter__(self) -> DisconnectingFakeWebSocket:
        return self

    async def __anext__(self) -> str:
        if self._closed:
            raise websockets.ConnectionClosed(1006, "connection lost")
        return await self._incoming.get()

    async def send(self, data: str) -> None:
        self.sent.append(data)
        message = json.loads(data)
        req_id = message.get("id")
        method = message.get("method")

        if method == "public/set_heartbeat":
            await self._incoming.put(
                json.dumps({"jsonrpc": "2.0", "id": req_id, "result": "ok"})
            )

    async def push_subscription(self) -> None:
        await self._incoming.put(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "subscription",
                    "params": {
                        "channel": "ticker.BTC-PERPETUAL.100ms",
                        "data": {"last_price": 50000},
                    },
                }
            )
        )

    async def close(self) -> None:
        self._closed = True


@pytest.mark.asyncio
async def test_reconnect_emits_gap_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    lifecycle_events: list[tuple[str, dict[str, Any]]] = []

    async def fake_connect(*_args: Any, **_kwargs: Any) -> DisconnectingFakeWebSocket:
        return DisconnectingFakeWebSocket()

    monkeypatch.setattr(websockets, "connect", fake_connect)

    async def on_lifecycle(event: str, payload: dict[str, Any]) -> None:
        lifecycle_events.append((event, payload))

    config = DeribitClientConfig(
        ws_url=TESTNET_WS_URL,
        reconnect_base_delay=0.01,
        reconnect_max_delay=0.05,
        request_timeout=2.0,
    )
    client = DeribitWebSocketClient(config, on_lifecycle=on_lifecycle)

    await client.connect()
    client._last_market_message_at = datetime.now(UTC) - timedelta(seconds=5)  # noqa: SLF001
    client._disconnect_at = datetime.now(UTC) - timedelta(seconds=4)  # noqa: SLF001

    await client._reconnect()

    gap_events = [event for event, _ in lifecycle_events if event == "gap.detected"]
    assert gap_events
    assert lifecycle_events[-1][0] == "gap.detected"
    assert lifecycle_events[-1][1]["gap_seconds"] > 0

    await client.disconnect()
