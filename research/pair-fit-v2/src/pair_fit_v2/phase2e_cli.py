"""Explicit operations for the bounded Phase 2E multi-season release."""
import argparse
import json
from pathlib import Path

from pair_fit_v2 import phase2e_multi_season as phase


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=Path("research/pair-fit-v2/cache"))
    operations = parser.add_mutually_exclusive_group(required=True)
    for operation in ("preview", "initialize", "live-acquisition", "analyze", "recover-cleveland-and-continue"):
        operations.add_argument(f"--{operation}", action="store_true")
    args = parser.parse_args(argv)
    phase.verify_prerequisites(args.cache_root)
    stores = phase.create_stores(args.cache_root)
    if args.preview:
        result = phase.preview(stores)
    elif args.initialize:
        result = phase.initialize(stores)
    elif args.recover_cleveland_and_continue:
        print(json.dumps(phase.prepare_recovery(stores), sort_keys=True), flush=True)
        result = phase.acquire(stores, live_acquisition=True)
    elif args.live_acquisition:
        result = phase.acquire(stores, live_acquisition=True)
    else:
        result = phase.analyze(stores)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
