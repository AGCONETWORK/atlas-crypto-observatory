"""Tests for Deribit WebSocket client with mocked connection."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
import websockets

from atlas.adapters.deribit.auth import DeribitCredentials
from atlas.adapters.deribit.client import ConnectionState, DeribitClientConfig, DeribitWebSocketClient
from atlas.adapters.deribit.constants import TESTNET_WS_URL


class RespondingFakeWebSocket:
    """WebSocket mock that responds to JSON-RPC requests."""

    def __init__(self) -> None:
        self._incoming: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[str] = []
        self._closed = False

    def __aiter__(self) -> RespondingFakeWebSocket:
        return self

    async def __anext__(self) -> str:
        if self._closed:
            raise websockets.ConnectionClosed(None, None)
        return await self._incoming.get()

    async def send(self, data: str) -> None:
        self.sent.append(data)
        message = json.loads(data)
        req_id = message.get("id")
        method = message.get("method")

        if method == "public/auth":
            await self._incoming.put(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "access_token": "token",
                            "refresh_token": "refresh",
                            "expires_in": 3600,
                            "scope": "connection",
                        },
                    }
                )
            )
        elif method == "public/set_heartbeat":
            await self._incoming.put(
                json.dumps({"jsonrpc": "2.0", "id": req_id, "result": "ok"})
            )

    async def push(self, data: dict[str, Any]) -> None:
        await self._incoming.put(json.dumps(data))

    async def close(self) -> None:
        self._closed = True
        await self._incoming.put("")


@pytest.mark.asyncio
async def test_connect_authenticate_and_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    lifecycle_events: list[str] = []
    fake = RespondingFakeWebSocket()

    async def on_lifecycle(event: str, payload: dict[str, Any]) -> None:
        lifecycle_events.append(event)

    async def fake_connect(*_args: Any, **_kwargs: Any) -> RespondingFakeWebSocket:
        return fake

    monkeypatch.setattr(websockets, "connect", fake_connect)

    config = DeribitClientConfig(
        ws_url=TESTNET_WS_URL,
        credentials=DeribitCredentials(client_id="cid", client_secret="secret"),
        heartbeat_interval=30,
        request_timeout=2.0,
    )
    client = DeribitWebSocketClient(config, on_lifecycle=on_lifecycle)

    await client.connect()
    await asyncio.sleep(0.05)

    assert client.state == ConnectionState.AUTHENTICATED
    assert client.auth.is_authenticated
    assert "connection.open" in lifecycle_events
    assert "connection.authenticated" in lifecycle_events
    assert "heartbeat.enabled" in lifecycle_events

    methods = [json.loads(msg)["method"] for msg in fake.sent]
    assert "public/auth" in methods
    assert "public/set_heartbeat" in methods

    await client.disconnect()


@pytest.mark.asyncio
async def test_responds_to_test_request_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = RespondingFakeWebSocket()

    async def fake_connect(*_args: Any, **_kwargs: Any) -> RespondingFakeWebSocket:
        return fake

    monkeypatch.setattr(websockets, "connect", fake_connect)

    config = DeribitClientConfig(ws_url=TESTNET_WS_URL, request_timeout=2.0)
    client = DeribitWebSocketClient(config)

    await client.connect()
    await fake.push(
        {
            "jsonrpc": "2.0",
            "method": "heartbeat",
            "params": {"type": "test_request"},
        }
    )
    await asyncio.sleep(0.1)

    methods = [json.loads(msg)["method"] for msg in fake.sent]
    assert "public/test" in methods
    assert client.metrics.heartbeats_received >= 1

    await client.disconnect()


@pytest.mark.asyncio
async def test_graceful_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = RespondingFakeWebSocket()

    async def fake_connect(*_args: Any, **_kwargs: Any) -> RespondingFakeWebSocket:
        return fake

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = DeribitWebSocketClient(DeribitClientConfig(ws_url=TESTNET_WS_URL))
    await client.connect()
    await client.disconnect()

    assert client.state == ConnectionState.DISCONNECTED
