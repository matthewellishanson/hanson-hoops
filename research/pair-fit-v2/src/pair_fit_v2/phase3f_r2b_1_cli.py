"""CLI for the offline-only Phase 3F-R2B.1 specification build."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r2b_1_response_contract import build_specification


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Phase 3F-R2B.1 correction specification")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="write the deterministic offline specification")
    build.add_argument("--project-root", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    result = build_specification(arguments.project_root, arguments.output_dir)
    print(result["classification"])


if __name__ == "__main__":
    main()

