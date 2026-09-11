"""Offline CLI for Phase 3C rolling historical baseline modeling."""

import argparse
import json

from pair_fit_v2.phase3c_baseline_modeling import run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Phase 3C Pair Fit v2 baseline modeling")
    parser.add_argument("--primary-csv", default="curated/phase3b/phase3b_poss_ge_150.csv")
    parser.add_argument("--manifest", default="curated/phase3b/phase3b_feature_manifest.json")
    parser.add_argument("--summary", default="curated/phase3b/phase3b_curation_summary.json")
    parser.add_argument("--output-dir", default="modeling/phase3c")
    args = parser.parse_args(argv)
    print(json.dumps(run(args.primary_csv, args.manifest, args.summary, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
