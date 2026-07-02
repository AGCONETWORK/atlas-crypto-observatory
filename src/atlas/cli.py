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


async def _cmd_connect(settings: AtlasSettings, duration: int) -> int:
    """Test Deribit connection — connect, auth, heartbeat, then shutdown."""
    adapter = DeribitAdapter(settings)
    stop = asyncio.Event()

    def _handle_signal() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    await adapter.connect()
    print(
        f"Connected to Deribit ({settings.deribit_environment}). "
        f"Press Ctrl+C to stop. Auto-stop in {duration}s."
    )

    try:
        await asyncio.wait_for(stop.wait(), timeout=duration)
    except TimeoutError:
        pass
    finally:
        await adapter.disconnect()

    client = adapter.client
    if client:
        print(
            f"Session complete. Reconnects: {client.metrics.reconnect_count}, "
            f"Heartbeats: {client.metrics.heartbeats_received}"
        )
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

    subparsers.add_parser("record", help="Start live evidence capture (v0.4.0)")
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

    print(f"Command '{args.command}' not yet implemented. Current release: v{__version__}")
    sys.exit(1)


if __name__ == "__main__":
    main()
