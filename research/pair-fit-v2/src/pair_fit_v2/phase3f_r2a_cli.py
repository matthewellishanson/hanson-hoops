"""Command line for the bounded Phase 3F-R2A prior-profile checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r2a_prior_profile_acquisition import (
    execute_authorized_acquisition,
    initialize_authorization,
    record_official_invocation,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3F-R2A prior-profile acquisition")
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("initialize", help="write the offline authorization record")
    acquire = subparsers.add_parser("acquire", help="perform the one authorized official invocation")
    for item in (initialize, acquire):
        item.add_argument("--project-root", type=Path, required=True)
        item.add_argument("--planning-dir", type=Path, required=True)
    acquire.add_argument("--authorization-path", type=Path, required=True)
    acquire.add_argument("--evidence-root", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "initialize":
        document = initialize_authorization(arguments.project_root, arguments.planning_dir)
        print(f"Phase 3F-R2A authorization frozen for {len(document['authorized_requests'])} requests")
        return
    record_official_invocation(arguments.planning_dir)
    result = execute_authorized_acquisition(
        arguments.project_root,
        arguments.authorization_path,
        arguments.evidence_root,
        arguments.planning_dir,
    )
    print(result["summary"]["classification"])


if __name__ == "__main__":
    main()
