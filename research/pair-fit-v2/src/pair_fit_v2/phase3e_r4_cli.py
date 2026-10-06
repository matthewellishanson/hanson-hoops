"""Command-line entry point for the single authorized Phase 3E-R4 run."""

from __future__ import annotations

import argparse
import json

from pair_fit_v2.phase3e_r4_evaluation import run_official_evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    print(json.dumps(run_official_evaluation(args.project_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
