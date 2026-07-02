"""ATLAS CLI — commands added per release milestone."""

import argparse
import sys

from atlas import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="ATLAS Market Event Recorder — evidence pipeline",
    )
    parser.add_argument("--version", action="version", version=f"atlas-mer {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("record", help="Start live evidence capture (v0.4.0)")
    subparsers.add_parser("replay", help="Replay archived evidence (v0.5.0)")
    subparsers.add_parser("validate", help="Validate archive integrity (v0.5.0)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    print(f"Command '{args.command}' not yet implemented. Current release: v{__version__}")
    sys.exit(1)


if __name__ == "__main__":
    main()
