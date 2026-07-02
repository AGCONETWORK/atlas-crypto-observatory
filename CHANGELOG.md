# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-07-02

### Added

- **Live recording** via `LiveRecorder` — Adapter → Pipeline → Event Bus → JsonlSink
- `atlas record` CLI command (runs until Ctrl+C, or `--duration N`)
- Per-session archive directories (`{date}/{session_id}/`)
- `metadata/subscriptions.json` written at recording start
- Session data quality metrics on stop (reconnects, dropped messages)

### Changed

- Storage layout isolates each observation session under its UUID
- Package version 0.4.0, Deribit adapter 0.4.0

## [0.3.0] - 2026-07-02

### Added

- **Instrument discovery** via `public/get_instruments` (BTC spot, perpetual, nearest futures, full options chain)
- **Subscription manager** with batched `public/subscribe` for `book`, `ticker`, `trades` at configured interval
- **Instrument parser** — Deribit symbols mapped to internal `Instrument` model
- **Auto re-subscribe** after WebSocket reconnect
- `atlas subscribe` CLI command to discover, subscribe, and count market messages
- Market message parser for channel, instrument, and exchange timestamp

### Changed

- `DeribitAdapter.subscribe()` fully implemented
- Adapter version bumped to 0.3.0

## [0.2.0] - 2026-07-02

### Added

- **Deribit adapter** (`adapters/deribit/`) — first exchange adapter
- WebSocket client with OAuth2 authentication (`public/auth`)
- Application-layer heartbeat (`public/set_heartbeat` + `public/test` response)
- Automatic reconnect with exponential backoff
- Connection lifecycle events emitted as evidence
- `AdapterCapabilities` advertisement for Deribit
- `atlas connect` CLI command to test live connection
- Configuration: heartbeat interval, reconnect delays
- Unit tests for auth, client, and adapter

### Changed

- Added `websockets` dependency
- Version bumped to 0.2.0

## [0.1.0] - 2026-07-02

### Added

- Phase 1 foundation: exchange-agnostic evidence pipeline architecture
- **Event Bus** as central integration point for live and replay data
- **EventEnvelope v1** and **EvidenceObject v1** contracts with provenance
- Explicit **EventCategory** taxonomy (MARKET, SYSTEM, CONNECTION, SUBSCRIPTION, RECORDER, STORAGE)
- **Three-clock model**: exchange_timestamp, received_at, replayed_at
- **Observation Session** with UUIDv7 canonical ID and human-readable label
- **Archive state machine**: CREATING, RECORDING, FINALIZING, COMPLETE, ABORTED, CORRUPTED
- **AdapterCapabilities** protocol for exchange feature advertisement
- **Evidence Pipeline** with sequence assignment and bus publication
- **StorageSink** interface with **JsonlSink** Phase 1 implementation
- **StorageManifest v1** and **ReplayManifest v1** contracts
- Archive **integrity validation** types (pre-replay gate)
- Central configuration via `pydantic-settings` and environment variables
- Structured logging via `structlog`
- Exchange adapter base protocol
- Unit and integration tests
- CONSTITUTION.md — frozen Phase 1 principles
- CLI stub (`atlas record`, `atlas replay`, `atlas validate`)

[0.4.0]: https://github.com/AGCONETWORK/atlas-crypto-observatory/releases/tag/v0.4.0
[0.3.0]: https://github.com/AGCONETWORK/atlas-crypto-observatory/releases/tag/v0.3.0
[0.2.0]: https://github.com/AGCONETWORK/atlas-crypto-observatory/releases/tag/v0.2.0
[0.1.0]: https://github.com/AGCONETWORK/atlas-crypto-observatory/releases/tag/v0.1.0
