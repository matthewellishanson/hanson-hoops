"""CLI for the offline-only Phase 3F-R2D.1 specification build."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase3f_r2d_1_response_echo_contract import (
    OUTPUT_NAMESPACE,
    build_specification,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_NAMESPACE)
    arguments = parser.parse_args()
    result = build_specification(arguments.project_root, arguments.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
