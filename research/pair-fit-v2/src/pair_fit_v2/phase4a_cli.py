"""Command-line interface for Pair Fit v2 Phase 4A production packaging."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pair_fit_v2.inference import PairFitPredictor
from pair_fit_v2.phase4a_production import acquire_2025_26_profiles, build_production_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Pair Fit v2 production package")
    parser.add_argument("command", choices=("acquire-profiles", "build", "predict"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--player-a-id")
    parser.add_argument("--player-b-id")
    parser.add_argument("--target-season")
    args = parser.parse_args()
    if args.command == "acquire-profiles":
        result = acquire_2025_26_profiles(args.project_root.resolve())
    elif args.command == "build":
        output = args.output_dir.resolve() if args.output_dir else None
        result = build_production_package(args.project_root.resolve(), output)
    else:
        if not all((args.player_a_id, args.player_b_id, args.target_season)):
            parser.error("predict requires --player-a-id, --player-b-id and --target-season")
        artifact_dir = args.output_dir or args.project_root / "production/pair-fit-v2.0.0"
        result = PairFitPredictor(artifact_dir.resolve()).predict_pair_fit(
            args.player_a_id, args.player_b_id, args.target_season
        )
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
