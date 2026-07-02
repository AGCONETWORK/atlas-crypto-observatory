"""Deribit adapter constants."""

ADAPTER_VERSION = "0.2.0"
EXCHANGE_ID = "deribit"
API_VERSION = "v2"

PRODUCTION_WS_URL = "wss://www.deribit.com/ws/api/v2"
TESTNET_WS_URL = "wss://test.deribit.com/ws/api/v2"

DEFAULT_HEARTBEAT_INTERVAL = 30
DEFAULT_RECONNECT_BASE_DELAY = 1.0
DEFAULT_RECONNECT_MAX_DELAY = 60.0
DEFAULT_REQUEST_TIMEOUT = 10.0
