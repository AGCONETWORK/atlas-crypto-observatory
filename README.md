# ATLAS Market Event Recorder

**ATLAS Market Event Recorder (MER)** is an exchange-agnostic evidence pipeline for immutable market data capture, archival, and deterministic replay.

Deribit is the first adapter. The core does not know it is recording crypto.

> The recorder is the custodian of evidence, not an interpreter of markets.

See [CONSTITUTION.md](CONSTITUTION.md) for frozen Phase 1 principles.

## Architecture

```
+---------+      +---------------+      +--------------+
| Adapter | ---> |   Event Bus   | ---> | Archive Sink |
+---------+      +-------+-------+      +--------------+
                         |
                         +--------> Health / Metadata (v0.6+)
                         |
                 +-------+--------+
                 | Replay Engine  | (injects back into bus)
                 +----------------+
```

**Evidence flow:** Adapter → Evidence Builder → Evidence Pipeline → Event Bus → Sinks

## Phase 1 Status

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.1.0 | Foundation — contracts, bus, pipeline, JsonlSink | Complete |
| v0.2.0 | Deribit connection — auth, WebSocket, reconnect, heartbeat | Complete |
| v0.3.0 | Instrument discovery & subscriptions | Complete |
| v0.4.0 | Live recording | Complete |
| v0.5.0 | Replay engine | Complete |
| v0.6.0 | Hardening — health, gaps, checksums, status | Complete |
| **v1.0.0** | **Production observatory** | **Current** |

Phase 1 delivers a complete evidence pipeline: live capture, immutable archival, integrity validation, and deterministic replay through the same Event Bus interface.

## Requirements

- Python 3.12+
- Deribit API keys (for live recording)

## Quick Start

```bash
# Clone and install
cd atlas-crypto-observatory
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your Deribit credentials

# Test Deribit connection
atlas connect --duration 30

# Discover and subscribe to BTC market data
atlas subscribe --duration 60

# Record live market evidence
atlas record
atlas record --duration 120

# Check session health
atlas status
atlas status --session 2026-07-02

# Validate and replay archives
atlas validate --session 2026-07-02
atlas replay --session 2026-07-02 --speed 10
atlas replay --session <session-uuid> --speed 0

# Run tests
pytest

# Optional live integration tests (requires credentials)
pytest -m integration
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `atlas connect` | Test Deribit connection (auth, heartbeat) |
| `atlas subscribe` | Discover instruments and count market messages |
| `atlas record` | Record live evidence to immutable archives |
| `atlas status` | Show session archive health |
| `atlas validate` | Pre-replay integrity gate |
| `atlas replay` | Replay archives through Event Bus |

## Project Layout

```
src/atlas/
├── core/           # EventEnvelope v1, taxonomy, provenance, clocks
├── evidence/       # Evidence Builder, Observation Session
├── bus/            # Event Bus (central hub)
├── pipeline/       # Evidence Pipeline
├── recording/      # LiveRecorder, health, metadata, status
├── storage/        # StorageSink, JsonlSink, manifest, integrity
├── replay/         # ReplayEngine, cursor, manifest
├── adapters/       # Exchange adapters
│   └── deribit/    # Deribit auth, WebSocket, reconnect, subscriptions
├── config/         # Central configuration
└── logging/        # Structured logging
```

## Storage Layout

```
data/
  2026-07-02/
    {session_id}/
      market/
        BTC-PERPETUAL/
          events.jsonl.gz
      metadata/
        session.json
        manifest.json
        subscriptions.json
        reconnects.json
        replay_{id}.json
```

## Production Checklist

Before running in production:

1. Set `DERIBIT_ENVIRONMENT=production` and valid API keys in `.env`
2. Confirm `ATLAS_DATA_PATH` has sufficient disk space
3. Run `atlas connect` to verify connectivity
4. Record with `atlas record` and verify with `atlas status`
5. Validate archives with `atlas validate --session <date>`
6. Confirm replay fidelity with `atlas replay --session <date> --speed 0`

## License

MIT — see [LICENSE](LICENSE).
