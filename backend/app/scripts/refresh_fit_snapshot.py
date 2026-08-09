from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh a packaged fit-model player pool.")
    parser.add_argument("--season", required=True, help="NBA season in YYYY-YY form")
    parser.add_argument("--model-version", default="fit-v1.0.0")
    args = parser.parse_args()

    # This script is the explicit refresh boundary. User-facing request handlers
    # remain cache-first and do not set this flag.
    os.environ["NBA_FORCE_LIVE_REFRESH"] = "1"
    from app.feature_engineering.fetch_stats import player_pool
    from app.services.snapshots import PACKAGE_CACHE_ROOT

    frame = player_pool(args.season, min_minutes=0)
    if frame.empty:
        raise SystemExit("NBA returned no rows; existing packaged snapshot was not changed.")

    target_dir = PACKAGE_CACHE_ROOT / "fit" / args.model_version
    target_dir.mkdir(parents=True, exist_ok=True)
    csv_path = target_dir / f"{args.season}-player-pool.csv"
    metadata_path = target_dir / f"{args.season}-metadata.json"
    temp_csv = csv_path.with_suffix(".tmp")
    temp_metadata = metadata_path.with_suffix(".tmp")
    frame.to_csv(temp_csv, index=False)
    temp_metadata.write_text(
        json.dumps(
            {
                "season": args.season,
                "model_version": args.model_version,
                "generated_at": datetime.now(UTC).isoformat(),
                "rows": len(frame),
                "source": "NBA Stats API live refresh",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temp_csv.replace(csv_path)
    temp_metadata.replace(metadata_path)
    print(f"wrote {len(frame)} rows to {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
