"""CLI for the offline Phase 3F-R0 final-test freeze builder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase3f_r0_final_test_freeze import build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("curated/phase3f-r0"))
    args = parser.parse_args(argv)
    result = build(args.project_root, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
