"""CLI for cache-only Phase 3E-R2 holdout construction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase3e_r2_holdout import build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("curated/phase3e-r2"))
    args = parser.parse_args(argv)
    print(json.dumps(build(args.project_root, args.output_dir), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
