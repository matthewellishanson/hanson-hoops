"""CLI for the one-time Phase 3F-R4 final evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase3f_r4_final_evaluation import run_official


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--authorized-one-time-final-evaluation", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorized_one_time_final_evaluation:
        parser.error("the explicit one-time final-evaluation authorization flag is required")
    print(json.dumps(run_official(args.project_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
