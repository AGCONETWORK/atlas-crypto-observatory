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
                         +--------> Metrics (v0.6+)
                         |
                         +--------> Live Console (future)
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
| v0.4.0 | Live recording | **Current** |
| v0.5.0 | Replay engine | Planned |
| v0.6.0 | Hardening | Planned |
| v1.0.0 | Production observatory | Planned |

## Requirements

- Python 3.12+
- Deribit API keys (for live recording, v0.2.0+)

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

# Test Deribit connection (v0.2.0)
atlas connect --duration 30

# Discover and subscribe to BTC market data (v0.3.0)
atlas subscribe --duration 60

# Record live market evidence (v0.4.0)
atlas record
atlas record --duration 120

# Run tests
pytest

# CLI (commands added per milestone)
atlas --version
```

## Project Layout

```
src/atlas/
├── core/           # EventEnvelope v1, taxonomy, provenance, clocks
├── evidence/       # Evidence Builder, Observation Session
├── bus/            # Event Bus (central hub)
├── pipeline/       # Evidence Pipeline
├── recording/      # LiveRecorder orchestration (v0.4.0)
├── storage/        # StorageSink, JsonlSink, manifest, integrity
├── replay/         # Replay manifest v1 (engine in v0.5.0)
├── adapters/       # Exchange adapters
│   └── deribit/    # Deribit auth, WebSocket, reconnect (v0.2.0)
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
```

## License

MIT — see [LICENSE](LICENSE).
