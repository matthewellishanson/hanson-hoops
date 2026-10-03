"""CLI for the bounded Phase 3F-R2C specification checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r2c_recovery_specification import acquire_public_source, write_specification


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire the one public source or build the R2C specification")
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("acquire-public-source")
    acquire.add_argument("--output-dir", required=True, type=Path)
    build = commands.add_parser("build")
    build.add_argument("--project-root", required=True, type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.command == "acquire-public-source":
        result = acquire_public_source(arguments.output_dir)
        print(result["raw_sha256"])
    else:
        result = write_specification(arguments.project_root, arguments.output_dir)
        print(result["classification"])


if __name__ == "__main__":
    main()
