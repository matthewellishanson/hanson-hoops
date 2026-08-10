from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from app.scripts.build_comparison_snapshots import (
    DEFAULT_OUTPUT,
    SHOT_SOURCE_REVISION,
    build_shots,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE = BACKEND_ROOT / "app" / "cache" / "snapshots" / "coverage.json"
SHOT_FILENAME = re.compile(r"shotdetail_(\d{4})\.csv$")


def season_for_path(path: Path) -> str:
    match = SHOT_FILENAME.fullmatch(path.name)
    if not match:
        raise ValueError(f"Expected shotdetail_<start-year>.csv, received {path.name}")
    start = int(match.group(1))
    return f"{start}-{(start + 1) % 100:02d}"


def update_coverage(path: Path, seasons: set[str], generated_at: str) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    known = {item["season"]: item for item in manifest.get("seasons", [])}
    missing = seasons - set(known)
    if missing:
        raise ValueError(f"Coverage manifest is missing seasons: {sorted(missing)}")
    for season in seasons:
        known[season]["shots"] = True
    manifest["generated_at"] = generated_at
    manifest.setdefault("sources", {})["shots"] = {
        "repository": "shufinskiy/nba_data",
        "revision": SHOT_SOURCE_REVISION,
        "license": "Apache-2.0",
        "seasons": ["1996-97", "2025-26"],
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build compact per-season shot snapshots from extracted source archives."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--coverage-manifest", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args()

    inputs = sorted(args.input_dir.glob("shotdetail_*.csv"))
    if not inputs:
        raise ValueError(f"No shotdetail_<start-year>.csv files found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    compression = {"method": "gzip", "compresslevel": 9, "mtime": 0}
    built: dict[str, dict] = {}
    for source_path in inputs:
        season = season_for_path(source_path)
        shots, stats = build_shots(source_path)
        shots.to_csv(
            args.output_dir / f"{season}-shots.csv.gz",
            index=False,
            compression=compression,
        )
        built[season] = stats
        print(f"{season}: {stats['rows']} shots, {stats['players']} players")

    update_coverage(args.coverage_manifest, set(built), args.generated_at)
    print(json.dumps({"built": built, "revision": SHOT_SOURCE_REVISION}, indent=2))


if __name__ == "__main__":
    main()
