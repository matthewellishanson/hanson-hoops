"""CLI for the bounded Phase 2B 2023-24 raw-season release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase2b_raw_season import (
    analyze_release,
    create_store,
    dry_run_plan,
    persist_dry_run,
    run_acquisition,
    verify_all_imports_and_dependencies,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--cache-root", type=Path, default=Path("research/pair-fit-v2/cache"))
    result.add_argument("--initialize", action="store_true")
    result.add_argument("--verify-imports", action="store_true")
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--live-acquisition", action="store_true")
    result.add_argument("--analyze", action="store_true")
    result.add_argument("--delay-seconds", type=float, default=1.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.dry_run and args.live_acquisition:
        raise SystemExit("Choose dry-run or live acquisition, not both")
    store = create_store(args.cache_root)
    output: dict[str, object] = {
        "manifest_path": str(store.path),
        "manifest_id": store.expected["manifest_id"],
    }
    if args.initialize:
        output["initialized_pair_entries"] = len(store.create_or_load()["pair_assets"])
    if args.verify_imports:
        output["import_replay"] = verify_all_imports_and_dependencies(store)
    if args.dry_run:
        output["dry_run"] = persist_dry_run(store)
    if args.live_acquisition:
        output["acquisition"] = run_acquisition(
            store,
            live_acquisition=True,
            delay_seconds=args.delay_seconds,
        )
    if args.analyze:
        output["analysis"] = analyze_release(store)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
