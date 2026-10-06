"""CLI for the Phase 3F-R2D.2 exact-seven recovery continuation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pair_fit_v2.phase3f_r2d_2_recovery_continuation import (
    OUTPUT_ROOT,
    cache_only_replay,
    execute_authorized_continuation,
    prepare_checkpoint,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    arguments = parser.parse_args()
    try:
        if arguments.command == "prepare":
            result = prepare_checkpoint(arguments.project_root, arguments.output_root)
            output = {
                "offline_indiana_revalidation": result["preflight"]["offline_indiana_revalidation"],
                "authorized_network_identity_count": result["authorization"]["network_authorized_identity_count"],
            }
        elif arguments.command == "run":
            result = execute_authorized_continuation(arguments.project_root, arguments.output_root)
            output = result["summary"]
        else:
            output = cache_only_replay(arguments.project_root, arguments.output_root)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
