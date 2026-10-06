"""CLI for the bounded Phase 3F-R2B.2 continuation."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r2b_2_protected_acquisition_continuation import (
    execute_authorized_continuation,
    initialize_authorization,
    record_official_invocation,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3F-R2B.2 correction-only continuation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("initialize", help="write the machine authorization offline")
    acquire = subparsers.add_parser("acquire", help="run the one official continuation invocation")
    for command in (initialize, acquire):
        command.add_argument("--project-root", type=Path, required=True)
        command.add_argument("--planning-dir", type=Path, required=True)
    acquire.add_argument("--authorization-path", type=Path, required=True)
    acquire.add_argument("--evidence-root", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "initialize":
        document = initialize_authorization(arguments.project_root, arguments.planning_dir)
        print(f"R2B.2 authorization frozen for {len(document['network_authorized_requests'])} network identities")
        return
    record_official_invocation(arguments.planning_dir, arguments.authorization_path)
    result = execute_authorized_continuation(
        arguments.project_root,
        arguments.authorization_path,
        arguments.evidence_root,
        arguments.planning_dir,
    )
    print(result["summary"]["classification"])


if __name__ == "__main__":
    main()
