"""Command-line entry point for the bounded Phase 1D endpoint diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pair_fit_v2.phase1c_manifest import (
    ManifestStore,
    build_operational_manifest,
    derive_approved_schema_contract,
    validate_standings_snapshot,
    verify_asset_cache,
)
from pair_fit_v2.phase1c_validation import validate_raw_season
from pair_fit_v2.phase1d_exhaustiveness import (
    CHARLOTTE_ID,
    PHILADELPHIA_ID,
    analyze_boundary_payload,
    build_diagnostic_ledger,
    revalidate_stopped_identity_normalization,
    replay_authorized_diagnostics,
    run_authorized_diagnostics,
    validate_diagnostic_isolation,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("research/pair-fit-v2/cache"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pre-request-analysis", action="store_true")
    mode.add_argument("--live-acquisition", action="store_true")
    mode.add_argument("--replay", action="store_true")
    mode.add_argument("--revalidate-stopped", action="store_true")
    return parser


def load_phase1c_context(cache_root: Path) -> dict[str, Any]:
    teams = validate_standings_snapshot(cache_root)
    schemas = derive_approved_schema_contract(cache_root)
    store = ManifestStore(cache_root, build_operational_manifest(teams, schemas))
    baseline = validate_raw_season(store)
    expected_totals = {
        "base_raw_pair_rows": 5297,
        "advanced_raw_pair_rows": 5297,
        "full_outer_union_count": 5297,
        "matched_pairs": 5297,
        "base_only_pairs": 0,
        "advanced_only_pairs": 0,
    }
    if (
        not baseline["manifest_gate"]["valid"]
        or not baseline["clean_release"]
        or baseline["asset_count"] != 60
        or baseline["status_counts"] != {"verified": 60}
        or baseline["totals"] != expected_totals
        or baseline["target_eligibility"]["ineligible"] != 8
    ):
        raise ValueError("Phase 1C cache-only baseline differs from the approved release")
    manifest = store.load()
    payloads: dict[str, dict[str, Any]] = {}
    for asset in manifest["raw_assets"]:
        parameters = asset["identity"]["parameters"]
        if parameters["team_id"] not in {CHARLOTTE_ID, PHILADELPHIA_ID}:
            continue
        replay = verify_asset_cache(asset, cache_root, schemas)
        payloads.setdefault(parameters["team_id"], {})[parameters["measure_type"]] = replay["payload"]
    return {
        "manifest": manifest,
        "schemas": schemas,
        "baseline": baseline,
        "payloads": payloads,
    }


def _baseline_summary(baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest_id": baseline["manifest_id"],
        "manifest_gate_valid": baseline["manifest_gate"]["valid"],
        "clean_release": baseline["clean_release"],
        "asset_count": baseline["asset_count"],
        "status_counts": baseline["status_counts"],
        "cache_error_count": len(baseline["cache_errors"]),
        "totals": baseline["totals"],
        "target_eligibility": baseline["target_eligibility"],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    context = load_phase1c_context(args.cache_root)
    full_base = {
        team_id: measures["Base"] for team_id, measures in context["payloads"].items()
    }
    output: dict[str, Any] = {
        "phase1c_baseline": _baseline_summary(context["baseline"]),
        "diagnostic_isolation": validate_diagnostic_isolation(
            build_diagnostic_ledger(), context["manifest"]
        ),
    }
    if args.pre_request_analysis or (
        not args.live_acquisition and not args.replay and not args.revalidate_stopped
    ):
        output["boundary_analysis"] = {
            team_id: {
                measure: analyze_boundary_payload(payload, measure_type=measure)
                for measure, payload in measures.items()
            }
            for team_id, measures in context["payloads"].items()
        }
    elif args.live_acquisition:
        output["diagnostic_run"] = run_authorized_diagnostics(
            args.cache_root,
            phase1c_manifest=context["manifest"],
            full_season_base_payloads=full_base,
            approved_base_schema=context["schemas"]["Base"],
            live_acquisition=True,
        )
    elif args.replay:
        output["diagnostic_replay"] = replay_authorized_diagnostics(
            args.cache_root,
            phase1c_manifest=context["manifest"],
            full_season_base_payloads=full_base,
            approved_base_schema=context["schemas"]["Base"],
        )
    else:
        output["offline_revalidation"] = revalidate_stopped_identity_normalization(
            args.cache_root,
            phase1c_manifest=context["manifest"],
            full_season_base_payloads=full_base,
            approved_base_schema=context["schemas"]["Base"],
        )
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
