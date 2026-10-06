"""CLI for the configured Phase 2D 2021-22 raw-season release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase2d_raw_season import (
    analyze_release,
    create_store,
    dry_run_plan,
    persist_initial_plan,
    run_acquisition,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--cache-root", type=Path, default=Path("research/pair-fit-v2/cache"))
    result.add_argument("--initialize", action="store_true")
    result.add_argument("--preview", action="store_true")
    result.add_argument("--live-acquisition", action="store_true")
    result.add_argument("--analyze", action="store_true")
    result.add_argument("--delay-seconds", type=float, default=1.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if sum((args.initialize, args.preview, args.live_acquisition, args.analyze)) != 1:
        raise SystemExit("Choose exactly one Phase 2D operation")
    store = create_store(args.cache_root)
    if args.initialize:
        output = persist_initial_plan(store)
    elif args.preview:
        output = dry_run_plan(store)
    elif args.live_acquisition:
        output = run_acquisition(
            store, live_acquisition=True, delay_seconds=args.delay_seconds
        )
    else:
        output = analyze_release(store)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
