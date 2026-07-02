# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/atlas/atlas-crypto-observatory/releases/tag/v0.1.0
