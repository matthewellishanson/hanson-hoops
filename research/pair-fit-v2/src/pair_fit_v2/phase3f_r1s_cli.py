"""Command-line entry point for the offline Phase 3F-R1S plan build."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r1s_acquisition_plan import build


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline Phase 3F-R1S acquisition plan")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    summary = build(arguments.project_root, arguments.output_dir)
    print(
        "Phase 3F-R1S plan built: "
        f"{summary['protected_request_count']} protected requests, "
        f"{summary['missing_non_protected_dependency_count']} missing dependencies"
    )


if __name__ == "__main__":
    main()

