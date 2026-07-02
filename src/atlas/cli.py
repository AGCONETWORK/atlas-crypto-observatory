"""ATLAS CLI — commands added per release milestone."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from atlas import __version__
from atlas.adapters.deribit import DeribitAdapter
from atlas.config.settings import AtlasSettings
from atlas.logging.setup import setup_logging
from atlas.recording import LiveRecorder
from atlas.recording.status import load_session_status
from atlas.replay import ReplayEngine, ReplayParameters
from atlas.storage.archive import resolve_session_dir
from atlas.storage.integrity import validate_archive


def _register_stop_handler(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass


async def _cmd_connect(settings: AtlasSettings, duration: int) -> int:
    """Test Deribit connection — connect, auth, heartbeat, then shutdown."""
    adapter = DeribitAdapter(settings)
    stop = asyncio.Event()
    _register_stop_handler(stop)

    await adapter.connect()
    print(
        f"Connected to Deribit ({settings.deribit_environment}). "
        f"Press Ctrl+C to stop. Auto-stop in {duration}s."
    )

    client = adapter.client
    try:
        await asyncio.wait_for(stop.wait(), timeout=duration)
    except TimeoutError:
        pass
    finally:
        reconnects = client.metrics.reconnect_count if client else 0
        heartbeats = client.metrics.heartbeats_received if client else 0
        await adapter.disconnect()
        print(f"Session complete. Reconnects: {reconnects}, Heartbeats: {heartbeats}")

    return 0


async def _cmd_subscribe(settings: AtlasSettings, duration: int) -> int:
    """Discover instruments, subscribe to market data, count incoming messages."""
    adapter = DeribitAdapter(settings)
    stop = asyncio.Event()
    _register_stop_handler(stop)

    await adapter.connect()
    discovery = await adapter.discover()
    summary = discovery.summary()
    print(f"Discovered: {summary}")

    result = await adapter.subscribe()
    print(
        f"Subscribed to {result.success_count} channels "
        f"({len(result.failed_batches)} failed batches)."
    )
    print(f"Listening for {duration}s — press Ctrl+C to stop early.")

    assert adapter.client is not None
    run_task = asyncio.create_task(adapter.client.run_until_shutdown())

    try:
        await asyncio.wait_for(stop.wait(), timeout=duration)
    except TimeoutError:
        pass
    finally:
        messages = adapter.message_count
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
        await adapter.disconnect()
        print(f"Received {messages} market messages.")

    return 0


async def _cmd_record(settings: AtlasSettings, duration: int) -> int:
    """Record live market evidence to immutable JSONL archives."""
    recorder = LiveRecorder(settings)
    stop = asyncio.Event()
    _register_stop_handler(stop)

    if duration > 0:
        print(f"Recording to {settings.data_path} — auto-stop in {duration}s (Ctrl+C to stop early).")
    else:
        print(f"Recording to {settings.data_path} — press Ctrl+C to stop.")

    summary = await recorder.run_until(stop, duration=duration if duration > 0 else None)

    print("Recording complete.")
    print(f"  Session:      {summary.session_label}")
    print(f"  Session ID:   {summary.session_id}")
    print(f"  Events:       {summary.events_recorded}")
    print(f"  Market msgs:  {summary.market_messages}")
    print(f"  Reconnects:   {summary.reconnects}")
    if summary.gap_count:
        print(f"  Gaps:         {summary.gap_count} (largest {summary.largest_gap_seconds:.1f}s)")
    if summary.session_dir:
        print(f"  Archive path: {summary.session_dir}")
    return 0


def _cmd_status(settings: AtlasSettings, session: str | None) -> int:
    """Show archive health and recording metrics for a session."""
    try:
        status = load_session_status(settings.data_path, session)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Archive:  {status.session_dir}")
    print(f"Session:  {status.session.session_label}")
    print(f"State:    {status.state.value}")
    print(f"Events:   {status.events_recorded}")
    print(f"Reconnects: {status.reconnects}")
    print(f"Gaps:     {status.gap_count} (largest {status.largest_gap_seconds:.1f}s)")
    if status.state.value == "RECORDING":
        print(f"Stale:    {'yes' if status.is_stale else 'no'}")
    return 0


async def _cmd_validate(settings: AtlasSettings, session: str) -> int:
    """Validate archive integrity before replay."""
    session_dir = resolve_session_dir(settings.data_path, session)
    report = validate_archive(session_dir)

    print(f"Archive: {session_dir}")
    print(f"Valid:   {report.valid}")

    for warning in report.warnings:
        print(f"  WARNING: {warning.message}")

    for error in report.errors:
        print(f"  ERROR:   [{error.code}] {error.message}")

    return 0 if report.valid else 1


async def _cmd_replay(
    settings: AtlasSettings,
    session: str,
    *,
    speed: float,
    start_seq: int | None,
    end_seq: int | None,
    force: bool,
) -> int:
    """Replay archived evidence through the Event Bus."""
    from atlas.bus.event_bus import EventBus

    session_dir = resolve_session_dir(settings.data_path, session)
    bus = EventBus()
    received: list[int] = []

    async def counter(envelope: object) -> None:
        received.append(getattr(envelope, "seq", 0))

    bus.subscribe(counter)

    engine = ReplayEngine(
        bus,
        session_dir,
        parameters=ReplayParameters(
            speed=speed,
            start_seq=start_seq,
            end_seq=end_seq,
        ),
        force=force,
    )

    print(f"Replaying: {session_dir}")
    print(f"Speed:     {speed}x")

    manifest = await engine.run()

    print("Replay complete.")
    print(f"  Replay ID:      {manifest.replay_id}")
    print(f"  Events emitted: {manifest.events_emitted}")
    if engine.cursor:
        print(f"  Progress:       {engine.cursor.progress_pct}%")
        print(f"  Final seq:      {engine.cursor.current_seq}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="ATLAS Market Event Recorder — evidence pipeline",
    )
    parser.add_argument("--version", action="version", version=f"atlas-mer {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    connect_parser = subparsers.add_parser("connect", help="Test Deribit connection")
    connect_parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Seconds to maintain connection (default: 30)",
    )

    subscribe_parser = subparsers.add_parser(
        "subscribe",
        help="Discover and subscribe to BTC market data",
    )
    subscribe_parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Seconds to listen after subscribing (default: 60)",
    )

    record_parser = subparsers.add_parser("record", help="Record live market evidence to disk")
    record_parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Seconds to record (0 = until Ctrl+C, default: 0)",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate archive integrity")
    validate_parser.add_argument(
        "--session",
        required=True,
        help="Session path, UUID, or date (YYYY-MM-DD)",
    )

    replay_parser = subparsers.add_parser("replay", help="Replay archived evidence")
    replay_parser.add_argument(
        "--session",
        required=True,
        help="Session path, UUID, or date (YYYY-MM-DD)",
    )
    replay_parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier (0 = as fast as possible)",
    )
    replay_parser.add_argument("--start-seq", type=int, default=None)
    replay_parser.add_argument("--end-seq", type=int, default=None)
    replay_parser.add_argument(
        "--force",
        action="store_true",
        help="Replay even if integrity check fails",
    )

    status_parser = subparsers.add_parser("status", help="Show session archive health")
    status_parser.add_argument(
        "--session",
        default=None,
        help="Session path, UUID, or date (default: latest archive)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    settings = AtlasSettings()
    setup_logging(level=settings.log_level, log_format=settings.log_format)

    if args.command == "connect":
        code = asyncio.run(_cmd_connect(settings, args.duration))
        sys.exit(code)

    if args.command == "subscribe":
        code = asyncio.run(_cmd_subscribe(settings, args.duration))
        sys.exit(code)

    if args.command == "record":
        code = asyncio.run(_cmd_record(settings, args.duration))
        sys.exit(code)

    if args.command == "status":
        code = _cmd_status(settings, args.session)
        sys.exit(code)

    if args.command == "validate":
        code = asyncio.run(_cmd_validate(settings, args.session))
        sys.exit(code)

    if args.command == "replay":
        code = asyncio.run(
            _cmd_replay(
                settings,
                args.session,
                speed=args.speed,
                start_seq=args.start_seq,
                end_seq=args.end_seq,
                force=args.force,
            )
        )
        sys.exit(code)

    print(f"Command '{args.command}' not yet implemented. Current release: v{__version__}")
    sys.exit(1)


if __name__ == "__main__":
    main()
