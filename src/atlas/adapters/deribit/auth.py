"""Deribit OAuth2 authentication over WebSocket."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class DeribitAuthState:
    """Tracks Deribit access token lifecycle."""

    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str | None = None

    def apply_auth_result(self, result: dict[str, Any]) -> None:
        """Update state from a successful public/auth response."""
        self.access_token = result.get("access_token")
        self.refresh_token = result.get("refresh_token")
        self.scope = result.get("scope")
        expires_in = result.get("expires_in", 0)
        self.expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

    @property
    def is_authenticated(self) -> bool:
        return self.access_token is not None

    def is_expired(self, *, margin_seconds: int = 60) -> bool:
        if self.expires_at is None:
            return True
        return datetime.now(UTC) >= (self.expires_at - timedelta(seconds=margin_seconds))

    def clear(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.scope = None


@dataclass
class DeribitCredentials:
    """API credentials loaded from configuration."""

    client_id: str
    client_secret: str

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def build_auth_request(*, client_id: str, client_secret: str, request_id: int) -> dict[str, Any]:
    """Build JSON-RPC public/auth request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "public/auth",
        "params": {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    }


def build_refresh_request(*, refresh_token: str, request_id: int) -> dict[str, Any]:
    """Build JSON-RPC public/auth refresh request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "public/auth",
        "params": {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    }
