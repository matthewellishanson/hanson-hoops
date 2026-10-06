"""CLI for the cache-only Phase 3F-R3 final-test readiness checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from pair_fit_v2.phase3f_r3_final_test_readiness import build


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("curated/phase3f-r3"))
    parser.add_argument("--initial-clean-preflight-confirmed", action="store_true", required=True)
    args = parser.parse_args()
    summary = build(
        args.project_root,
        args.output_dir,
        initial_clean_preflight_confirmed=args.initial_clean_preflight_confirmed,
    )
    print(summary["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
