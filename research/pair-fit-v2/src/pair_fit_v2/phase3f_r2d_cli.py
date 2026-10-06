"""CLI for Phase 3F-R2D exact-250 recovery acquisition."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pair_fit_v2.phase3f_r2d_recovery_acquisition import (
    execute_authorized_recovery,
    initialize_authorization,
    verify_completed_checkpoint,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the exact-eight Phase 3F-R2D checkpoint")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("authorize", "run", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--project-root", required=True, type=Path)
        command.add_argument("--authorization", type=Path)
        command.add_argument("--evidence-root", required=True, type=Path)
        command.add_argument("--planning-dir", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.command == "authorize":
        result = initialize_authorization(
            arguments.project_root, arguments.planning_dir, arguments.evidence_root
        )
        print(result["phase"])
        return
    if arguments.authorization is None:
        parser.error("--authorization is required for run and verify")
    if arguments.command == "run":
        try:
            result = execute_authorized_recovery(
                arguments.project_root, arguments.authorization,
                arguments.evidence_root, arguments.planning_dir,
            )
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        else:
            print(result["stdout"])
        return
    result = verify_completed_checkpoint(
        arguments.project_root, arguments.authorization,
        arguments.evidence_root, arguments.planning_dir,
    )
    print(result)


if __name__ == "__main__":
    main()
