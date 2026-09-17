"""CLI for the Phase 3E-R4.2 correction-only reconciliation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase3e_r4_2_reconciliation import run_reconciliation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = run_reconciliation(args.project_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()


