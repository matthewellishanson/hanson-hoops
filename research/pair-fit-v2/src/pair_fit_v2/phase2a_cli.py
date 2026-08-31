"""CLI for the bounded Phase 2A historical canary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase2a_historical_canary import (
    CanaryStore,
    analyze_cache,
    dry_run_plan,
    expected_manifest,
    run_acquisition,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--cache-root", type=Path, default=Path("research/pair-fit-v2/cache"))
    result.add_argument("--initialize", action="store_true")
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--live-acquisition", action="store_true")
    result.add_argument("--analyze", action="store_true")
    result.add_argument("--delay-seconds", type=float, default=1.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.dry_run and args.live_acquisition:
        raise SystemExit("Choose dry-run or live acquisition, not both")
    expected = expected_manifest(args.cache_root)
    store = CanaryStore(args.cache_root, expected)
    output: dict[str, object] = {"manifest_path": str(store.path), "manifest_id": expected["manifest_id"]}
    if args.initialize:
        output["initialized"] = len(store.create_or_load()["raw_assets"])
    if args.dry_run:
        if not store.path.exists():
            raise SystemExit("Initialize before dry-run")
        output["dry_run"] = dry_run_plan(store)
    if args.live_acquisition:
        if not store.path.exists():
            raise SystemExit("Initialize before acquisition")
        output["acquisition"] = run_acquisition(
            store, dry_run=False, live_acquisition=True, delay_seconds=args.delay_seconds
        )
    if args.analyze:
        output["analysis"] = analyze_cache(store)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
