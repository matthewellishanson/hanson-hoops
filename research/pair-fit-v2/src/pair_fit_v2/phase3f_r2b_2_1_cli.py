"""CLI for the offline-only Phase 3F-R2B.2.1 procedural closure."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r2b_2_1_procedural_closure import build_procedural_closure


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline R2B.2.1 procedural closure")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="write the deterministic closure once")
    build.add_argument("--project-root", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    result = build_procedural_closure(arguments.project_root, arguments.output_dir)
    print(result["classification"])


if __name__ == "__main__":
    main()
