"""Command-line entry point for the explicit Phase 1C raw-season workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.phase1c_acquisition import run_manifest_acquisition
from pair_fit_v2.phase1c_manifest import (
    ManifestStore,
    build_operational_manifest,
    derive_approved_schema_contract,
    reconcile_pilot_assets,
    validate_standings_snapshot,
)
from pair_fit_v2.phase1c_validation import validate_raw_season


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("research/pair-fit-v2/cache"),
    )
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--reconcile-pilot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live-acquisition", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.live_acquisition and args.dry_run:
        raise SystemExit("Choose either --dry-run or --live-acquisition, not both")
    teams = validate_standings_snapshot(args.cache_root)
    schemas = derive_approved_schema_contract(args.cache_root)
    expected = build_operational_manifest(teams, schemas)
    store = ManifestStore(args.cache_root, expected)
    output: dict[str, object] = {
        "standings_team_count": len(teams),
        "manifest_path": str(store.path),
        "manifest_id": expected["manifest_id"],
    }
    if args.initialize:
        manifest = store.create_or_load()
        output["initialized_asset_count"] = len(manifest["raw_assets"])
    if args.reconcile_pilot:
        manifest = store.create_or_load()
        output["pilot_reconciliation"] = reconcile_pilot_assets(manifest, store)
    if args.dry_run or args.live_acquisition:
        if not store.path.exists():
            raise SystemExit("Initialize and reconcile the manifest before acquisition")
        output["acquisition"] = run_manifest_acquisition(
            store,
            dry_run=args.dry_run,
            live_acquisition=args.live_acquisition,
            retry_failed=args.retry_failed,
            delay_seconds=args.delay_seconds,
        )
    if args.validate:
        if not store.path.exists():
            raise SystemExit("Persisted manifest does not exist")
        output["validation"] = validate_raw_season(store)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
