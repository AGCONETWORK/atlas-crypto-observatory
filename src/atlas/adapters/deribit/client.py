"""Deribit WebSocket client — connect, auth, heartbeat, reconnect."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
import websockets
from websockets.asyncio.client import ClientConnection

from atlas.adapters.deribit.auth import (
    DeribitAuthState,
    DeribitCredentials,
    build_auth_request,
    build_refresh_request,
)
from atlas.adapters.deribit.constants import (
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_RECONNECT_BASE_DELAY,
    DEFAULT_RECONNECT_MAX_DELAY,
    DEFAULT_REQUEST_TIMEOUT,
)

log = structlog.get_logger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]
LifecycleHandler = Callable[[str, dict[str, Any]], Awaitable[None]]
ReconnectHandler = Callable[[], Awaitable[None]]


class ConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"


@dataclass
class ConnectionMetrics:
    """Connection health metrics — recorder health, not market analytics."""

    reconnect_count: int = 0
    heartbeat_failures: int = 0
    heartbeats_received: int = 0
    last_heartbeat_at: datetime | None = None
    connected_at: datetime | None = None
    last_disconnect_at: datetime | None = None


@dataclass
class DeribitClientConfig:
    ws_url: str
    credentials: DeribitCredentials | None = None
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL
    reconnect_base_delay: float = DEFAULT_RECONNECT_BASE_DELAY
    reconnect_max_delay: float = DEFAULT_RECONNECT_MAX_DELAY
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    ping_interval: float = 20.0
    ping_timeout: float = 20.0


class DeribitWebSocketClient:
    """
    Robust Deribit WebSocket client.

    Responsibilities: connect, authenticate, heartbeat, auto-reconnect, graceful shutdown.
    No business logic or market interpretation.
    """

    def __init__(
        self,
        config: DeribitClientConfig,
        *,
        on_message: MessageHandler | None = None,
        on_lifecycle: LifecycleHandler | None = None,
        on_reconnected: ReconnectHandler | None = None,
    ) -> None:
        self._config = config
        self._on_message = on_message
        self._on_lifecycle = on_lifecycle
        self._on_reconnected = on_reconnected
        self._ws: ClientConnection | None = None
        self._state = ConnectionState.DISCONNECTED
        self._auth = DeribitAuthState()
        self._metrics = ConnectionMetrics()
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()
        self._reconnect_attempt = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def metrics(self) -> ConnectionMetrics:
        return self._metrics

    @property
    def auth(self) -> DeribitAuthState:
        return self._auth

    def next_request_id(self) -> int:
        """Public request ID generator for adapter RPC calls."""
        return self._next_id()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _emit_lifecycle(self, event: str, payload: dict[str, Any]) -> None:
        if self._on_lifecycle:
            await self._on_lifecycle(event, payload)

    async def connect(self, *, is_reconnect: bool = False) -> None:
        """Establish WebSocket connection, authenticate, and enable heartbeat."""
        if self._shutdown.is_set():
            msg = "Client is shut down"
            raise RuntimeError(msg)

        async with self._lock:
            self._state = ConnectionState.CONNECTING
            log.info("connection.connecting", url=self._config.ws_url)

            self._ws = await websockets.connect(
                self._config.ws_url,
                ping_interval=self._config.ping_interval,
                ping_timeout=self._config.ping_timeout,
                close_timeout=5,
            )
            self._state = ConnectionState.CONNECTED
            self._metrics.connected_at = datetime.now(UTC)
            self._reconnect_attempt = 0

            await self._emit_lifecycle("connection.open", {"url": self._config.ws_url})
            log.info("connection.established", url=self._config.ws_url)

            self._reader_task = asyncio.create_task(self._read_loop(), name="deribit-reader")

            if self._config.credentials and self._config.credentials.is_configured:
                await self.authenticate()
            else:
                log.warning("connection.unauthenticated", reason="no_credentials")

            await self.enable_heartbeat()

        if is_reconnect and self._on_reconnected:
            await self._on_reconnected()

    async def authenticate(self) -> None:
        """Authenticate using client credentials."""
        creds = self._config.credentials
        if creds is None or not creds.is_configured:
            msg = "Deribit credentials not configured"
            raise ValueError(msg)

        if self._auth.is_authenticated and not self._auth.is_expired():
            return

        if self._auth.refresh_token and self._auth.is_expired():
            await self._authenticate_refresh()
            return

        request = build_auth_request(
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            request_id=self._next_id(),
        )
        response = await self.request(request)
        if "error" in response:
            error = response["error"]
            log.error("connection.auth_failed", error=error)
            msg = f"Authentication failed: {error}"
            raise RuntimeError(msg)

        self._auth.apply_auth_result(response["result"])
        self._state = ConnectionState.AUTHENTICATED
        log.info("connection.authenticated", scope=self._auth.scope)
        await self._emit_lifecycle("connection.authenticated", {"scope": self._auth.scope})

    async def _authenticate_refresh(self) -> None:
        if not self._auth.refresh_token:
            await self.authenticate()
            return

        request = build_refresh_request(
            refresh_token=self._auth.refresh_token,
            request_id=self._next_id(),
        )
        response = await self.request(request)
        if "error" in response:
            self._auth.clear()
            await self.authenticate()
            return

        self._auth.apply_auth_result(response["result"])
        self._state = ConnectionState.AUTHENTICATED
        log.info("connection.token_refreshed")

    async def enable_heartbeat(self) -> None:
        """Enable Deribit application-layer heartbeat."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "public/set_heartbeat",
            "params": {"interval": self._config.heartbeat_interval},
        }
        response = await self.request(request)
        if "error" in response:
            self._metrics.heartbeat_failures += 1
            log.error("heartbeat.setup_failed", error=response["error"])
            await self._emit_lifecycle(
                "heartbeat.setup_failed",
                {"error": response["error"]},
            )
            return

        log.info("heartbeat.enabled", interval=self._config.heartbeat_interval)
        await self._emit_lifecycle(
            "heartbeat.enabled",
            {"interval": self._config.heartbeat_interval},
        )

    async def request(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC request and await matching response."""
        if self._ws is None:
            msg = "Not connected"
            raise RuntimeError(msg)

        request_id = message.get("id")
        if request_id is None:
            await self._ws.send(json.dumps(message))
            return {}

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[int(request_id)] = future
        await self._ws.send(json.dumps(message))

        try:
            return await asyncio.wait_for(future, timeout=self._config.request_timeout)
        except TimeoutError:
            self._pending.pop(int(request_id), None)
            self._metrics.heartbeat_failures += 1
            msg = f"Request timed out: {message.get('method')}"
            raise TimeoutError(msg) from None

    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message without waiting for a response."""
        if self._ws is None:
            msg = "Not connected"
            raise RuntimeError(msg)
        await self._ws.send(json.dumps(message))

    async def _handle_server_message(self, data: dict[str, Any]) -> None:
        """Dispatch incoming server messages."""
        if "id" in data and data["id"] in self._pending:
            future = self._pending.pop(int(data["id"]))
            if not future.done():
                future.set_result(data)
            return

        method = data.get("method")
        if method == "heartbeat":
            params = data.get("params", {})
            self._metrics.heartbeats_received += 1
            self._metrics.last_heartbeat_at = datetime.now(UTC)
            if params.get("type") == "test_request":
                await self._respond_to_test_request()
            return

        if method == "subscription" and self._on_message:
            await self._on_message(data)
            return

        if self._on_message:
            await self._on_message(data)

    async def _respond_to_test_request(self) -> None:
        """Reply to Deribit test_request heartbeat — required to keep connection alive."""
        try:
            await self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "public/test",
                    "params": {},
                }
            )
        except Exception as exc:
            self._metrics.heartbeat_failures += 1
            log.error("heartbeat.response_failed", error=str(exc))
            await self._emit_lifecycle("heartbeat.failure", {"error": str(exc)})

    async def _read_loop(self) -> None:
        """Read messages until disconnect or shutdown."""
        assert self._ws is not None
        ws = self._ws
        try:
            async for raw in ws:
                if self._shutdown.is_set():
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("connection.invalid_json")
                    continue
                await self._handle_server_message(data)
        except websockets.ConnectionClosed as exc:
            self._metrics.last_disconnect_at = datetime.now(UTC)
            log.warning("connection.closed", code=exc.code, reason=exc.reason)
            await self._emit_lifecycle(
                "connection.closed",
                {"code": exc.code, "reason": exc.reason},
            )
            if not self._shutdown.is_set():
                await self._reconnect()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("connection.read_error", error=str(exc))
            if not self._shutdown.is_set():
                await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff."""
        if self._shutdown.is_set():
            return

        self._state = ConnectionState.RECONNECTING
        self._metrics.reconnect_count += 1
        self._auth.clear()

        await self._cleanup_connection()
        delay = min(
            self._config.reconnect_base_delay * (2**self._reconnect_attempt),
            self._config.reconnect_max_delay,
        )
        self._reconnect_attempt += 1

        log.info(
            "connection.reconnect",
            attempt=self._reconnect_attempt,
            delay_seconds=delay,
        )
        await self._emit_lifecycle(
            "connection.reconnect",
            {"attempt": self._reconnect_attempt, "delay_seconds": delay},
        )

        await asyncio.sleep(delay)

        if self._shutdown.is_set():
            return

        try:
            await self.connect(is_reconnect=True)
        except Exception as exc:
            log.error("connection.reconnect_failed", error=str(exc))
            await self._reconnect()

    async def _cleanup_connection(self) -> None:
        """Close socket and cancel reader without marking shutdown."""
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._reader_task = None

        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Connection closed"))
        self._pending.clear()

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._state = ConnectionState.DISCONNECTED

    async def disconnect(self) -> None:
        """Gracefully shut down the client."""
        self._shutdown.set()
        await self._emit_lifecycle("connection.shutdown", {})
        await self._cleanup_connection()
        self._state = ConnectionState.DISCONNECTED
        log.info("connection.shutdown_complete")

    async def run_until_shutdown(self) -> None:
        """Maintain connection until disconnect() is called."""
        if self._state == ConnectionState.DISCONNECTED:
            await self.connect()
        while not self._shutdown.is_set():
            await asyncio.sleep(1)
