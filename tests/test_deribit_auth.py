"""Tests for Deribit authentication helpers."""

from datetime import UTC, datetime, timedelta

from atlas.adapters.deribit.auth import (
    DeribitAuthState,
    DeribitCredentials,
    build_auth_request,
    build_refresh_request,
)


def test_credentials_configured() -> None:
    assert DeribitCredentials(client_id="id", client_secret="secret").is_configured
    assert not DeribitCredentials(client_id="", client_secret="").is_configured


def test_build_auth_request() -> None:
    req = build_auth_request(client_id="cid", client_secret="csec", request_id=1)
    assert req["method"] == "public/auth"
    assert req["params"]["grant_type"] == "client_credentials"
    assert req["id"] == 1


def test_build_refresh_request() -> None:
    req = build_refresh_request(refresh_token="rtok", request_id=2)
    assert req["params"]["grant_type"] == "refresh_token"
    assert req["params"]["refresh_token"] == "rtok"


def test_auth_state_apply_and_expiry() -> None:
    state = DeribitAuthState()
    state.apply_auth_result(
        {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 3600,
            "scope": "connection",
        }
    )
    assert state.is_authenticated
    assert not state.is_expired()

    state.expires_at = datetime.now(UTC) + timedelta(seconds=30)
    assert state.is_expired()
