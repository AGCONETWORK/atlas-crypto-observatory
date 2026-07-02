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
    if summary.session_dir:
        print(f"  Archive path: {summary.session_dir}")
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

    subparsers.add_parser("replay", help="Replay archived evidence (v0.5.0)")
    subparsers.add_parser("validate", help="Validate archive integrity (v0.5.0)")

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

    print(f"Command '{args.command}' not yet implemented. Current release: v{__version__}")
    sys.exit(1)


if __name__ == "__main__":
    main()
