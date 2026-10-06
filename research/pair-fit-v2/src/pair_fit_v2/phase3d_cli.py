"""Thin offline CLI for Pair Fit v2 Phase 3D refinement."""

import argparse
import json

from pair_fit_v2.phase3d_model_refinement import run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline, training-era-only Phase 3D model refinement")
    parser.add_argument("--poss-150-csv", default="curated/phase3b/phase3b_poss_ge_150.csv")
    parser.add_argument("--poss-100-csv", default="curated/phase3b/phase3b_poss_ge_100.csv")
    parser.add_argument("--manifest", default="curated/phase3b/phase3b_feature_manifest.json")
    parser.add_argument("--phase3b-summary", default="curated/phase3b/phase3b_curation_summary.json")
    parser.add_argument("--phase3c-summary", default="modeling/phase3c/summary.json")
    parser.add_argument("--output-dir", default="modeling/phase3d")
    args = parser.parse_args(argv)
    summary = run(
        args.poss_150_csv,
        args.poss_100_csv,
        args.manifest,
        args.phase3b_summary,
        args.phase3c_summary,
        args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
