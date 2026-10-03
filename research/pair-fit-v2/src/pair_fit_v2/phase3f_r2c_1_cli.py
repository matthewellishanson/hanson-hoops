"""CLI for the offline Phase 3F-R2C.1 correction build."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r2c_1_recovery_specification import write_specification


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline R2C.1 correction bundle")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    arguments = parser.parse_args()
    result = write_specification(arguments.project_root, arguments.output_dir)
    print(result["classification"])


if __name__ == "__main__":
    main()
