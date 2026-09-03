"""CLI for the bounded Phase 2B 2023-24 raw-season release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase2b_raw_season import (
    activate_continuation,
    analyze_release,
    continuation_preview,
    create_store,
    dry_run_plan,
    persist_initial_plan,
    run_acquisition,
    verify_all_imports_and_dependencies,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--cache-root", type=Path, default=Path("research/pair-fit-v2/cache"))
    result.add_argument("--initialize", action="store_true")
    result.add_argument("--verify-imports", action="store_true")
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--persist-initial-plan", action="store_true")
    result.add_argument("--continuation-preview", action="store_true")
    result.add_argument("--activate-continuation", action="store_true")
    result.add_argument("--live-acquisition", action="store_true")
    result.add_argument("--analyze", action="store_true")
    result.add_argument("--delay-seconds", type=float, default=1.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    exclusive = (
        args.dry_run,
        args.persist_initial_plan,
        args.continuation_preview,
        args.activate_continuation,
        args.live_acquisition,
    )
    if sum(exclusive) > 1:
        raise SystemExit(
            "Choose initial preview/persistence, continuation preview/activation, or live acquisition"
        )
    if args.dry_run and args.initialize:
        raise SystemExit("Read-only preview cannot be combined with initialization")
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
        output["dry_run"] = {
            **dry_run_plan(store),
            "command_semantics": "read_only_preview",
            "side_effects": [],
        }
    if args.persist_initial_plan:
        output["initial_plan"] = persist_initial_plan(store)
    if args.continuation_preview:
        output["continuation_preview"] = continuation_preview(store)
    if args.activate_continuation:
        output["continuation_authorization"] = activate_continuation(store)
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
