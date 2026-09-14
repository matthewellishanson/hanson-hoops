"""CLI for Phase 3E-R1 bounded Philadelphia evidence acquisition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase3e_r1_philadelphia import acquire, write_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=Path("cache"))
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("modeling/phase3e-r1"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--live-acquisition", action="store_true")
    mode.add_argument("--replay", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = acquire(
        args.cache_root,
        args.project_root,
        live=args.live_acquisition,
    )
    if args.live_acquisition or args.replay:
        path = write_result(args.output_dir, result)
        result = {**result, "result_path": str(path).replace("\\", "/")}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["completed"] or args.preflight else 2


if __name__ == "__main__":
    raise SystemExit(main())
