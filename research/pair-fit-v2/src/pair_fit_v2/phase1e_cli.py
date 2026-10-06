"""CLI for the bounded Phase 1E two-window recovery diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pair_fit_v2.phase1c_manifest import read_json
from pair_fit_v2.phase1d_cli import load_phase1c_context
from pair_fit_v2.phase1d_exhaustiveness import replay_authorized_diagnostics
from pair_fit_v2.phase1e_recovery import (
    build_phase1e_ledger,
    replay_phase1e_recovery,
    run_phase1e_recovery,
    validate_phase1e_isolation,
    validate_window_contract,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("research/pair-fit-v2/cache"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--live-acquisition", action="store_true")
    mode.add_argument("--replay", action="store_true")
    return parser


def load_phase1e_context(cache_root: Path):
    phase1c = load_phase1c_context(cache_root)
    phase1d_path = cache_root / "phase1d" / "diagnostic_ledger.json"
    phase1d_ledger = read_json(phase1d_path)
    full_payloads = phase1c["payloads"]
    phase1d_replay = replay_authorized_diagnostics(
        cache_root,
        phase1c_manifest=phase1c["manifest"],
        full_season_base_payloads={team: measures["Base"] for team, measures in full_payloads.items()},
        approved_base_schema=phase1c["schemas"]["Base"],
    )
    if (
        phase1d_replay["classification"] != "proven_non_exhaustive"
        or phase1d_replay["comparison"]["diagnostic_only_key_count"] != 3
    ):
        raise ValueError("Immutable Phase 1D finding did not replay")
    return {
        "phase1c": phase1c,
        "phase1d_ledger": phase1d_ledger,
        "phase1d_replay": phase1d_replay,
        "full_payloads": full_payloads,
        "schemas": phase1c["schemas"],
        "immutable_hashes": {
            "phase1c_manifest_sha256": hashlib.sha256(
                (
                    cache_root
                    / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
                ).read_bytes()
            ).hexdigest(),
            "phase1d_ledger_sha256": hashlib.sha256(phase1d_path.read_bytes()).hexdigest(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    context = load_phase1e_context(args.cache_root)
    expected = build_phase1e_ledger()
    output = {
        "window_contract": validate_window_contract(),
        "immutable_hashes": context["immutable_hashes"],
        "diagnostic_isolation": validate_phase1e_isolation(
            expected,
            context["phase1c"]["manifest"],
            context["phase1d_ledger"],
        ),
        "phase1c_baseline": {
            "asset_count": context["phase1c"]["baseline"]["asset_count"],
            "status_counts": context["phase1c"]["baseline"]["status_counts"],
            "totals": context["phase1c"]["baseline"]["totals"],
            "clean_release": context["phase1c"]["baseline"]["clean_release"],
        },
        "phase1d_baseline": {
            "classification": context["phase1d_replay"]["classification"],
            "diagnostic_only_keys": context["phase1d_replay"]["comparison"][
                "diagnostic_only_keys"
            ],
        },
    }
    kwargs = {
        "phase1c_manifest": context["phase1c"]["manifest"],
        "phase1d_ledger": context["phase1d_ledger"],
        "full_season_payloads": context["full_payloads"],
        "approved_schemas": context["schemas"],
    }
    if args.live_acquisition:
        output["phase1e_run"] = run_phase1e_recovery(
            args.cache_root, **kwargs, live_acquisition=True
        )
    elif args.replay:
        output["phase1e_replay"] = replay_phase1e_recovery(args.cache_root, **kwargs)
    else:
        output["authorized_assets"] = [
            {
                "sequence": asset["sequence"],
                "asset_id": asset["asset_id"],
                "team": asset["team_name"],
                "window": asset["window"],
                "measure": asset["measure"],
                "identity": asset["identity"],
            }
            for asset in expected["assets"]
        ]
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
