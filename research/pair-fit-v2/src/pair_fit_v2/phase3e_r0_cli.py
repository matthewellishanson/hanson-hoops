"""Thin CLI for the cache-only Phase 3E-R0 checkpoint."""

from __future__ import annotations

import argparse
import json

from pair_fit_v2.phase3a_population_audit import network_prohibited
from pair_fit_v2.phase3e_r0_evidence_reconciliation import build_summary, write_summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Cache-only Phase 3E-R0 evidence reconciliation")
    parser.add_argument("--cache-root", default="cache")
    parser.add_argument("--output-dir", default="modeling/phase3e-r0")
    args = parser.parse_args(argv)
    with network_prohibited():
        summary = build_summary(args.cache_root)
        path = write_summary(args.output_dir, summary)
    print(json.dumps({"artifact": str(path), "deterministic_content_sha256": summary["deterministic_content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

