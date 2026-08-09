from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from app.api.endpoints.players import _profile_payload_from_logs


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = BACKEND_ROOT / "app" / "cache" / "snapshots" / "player-seasons"
DEFAULT_FIT_POOL = (
    BACKEND_ROOT
    / "app"
    / "cache"
    / "snapshots"
    / "fit"
    / "fit-v1.0.0"
    / "2023-24-player-pool.csv"
)

PROFILE_SOURCE_REVISION = "a5f108b5b1f08074d78b9e8e901926a9ce4c06c5"
SHOT_SOURCE_REVISION = "e829d4678be1e075f99e5d41a1c5f97089be446b"


def _last_value(frame: pd.DataFrame, column: str):
    if column not in frame.columns:
        return None
    values = frame[column].dropna()
    if values.empty:
        return None
    value = values.iloc[-1]
    if isinstance(value, str):
        value = value.strip()
    return value if value not in ("", "nan") else None


def _jersey(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def _height_fields(height_in) -> tuple[str | None, int | None]:
    if height_in is None or pd.isna(height_in):
        return None, None
    inches = int(round(float(height_in)))
    return f"{inches // 12}-{inches % 12}", round(inches * 2.54)


def build_profiles(
    box_score_paths: list[Path], season: str, fit_pool_path: Path
) -> tuple[pd.DataFrame, dict]:
    frames = [pd.read_csv(path, low_memory=False) for path in box_score_paths]
    raw = pd.concat(frames, ignore_index=True)
    season_rows = raw[raw["season_year"].astype(str) == season].copy()
    season_rows["game_date"] = pd.to_datetime(season_rows["game_date"], errors="coerce")
    season_rows = season_rows.sort_values("game_date")
    # The source includes DNP/DND roster rows with zero-filled box-score fields.
    # A real appearance always has a minutes value, so exclude those rows before
    # computing per-game averages.
    season_rows = season_rows[season_rows["minutes"].notna()]
    if season_rows.empty:
        raise ValueError(f"No played box-score rows found for {season}")

    fit = pd.read_csv(fit_pool_path) if fit_pool_path.is_file() else pd.DataFrame()
    fit_by_id = {
        str(int(row.PLAYER_ID)): row
        for row in fit.itertuples()
        if pd.notna(getattr(row, "PLAYER_ID", None))
    }
    rename = {
        "points": "PTS",
        "reboundsTotal": "REB",
        "assists": "AST",
        "blocks": "BLK",
        "steals": "STL",
        "turnovers": "TOV",
        "fieldGoalsMade": "FGM",
        "fieldGoalsAttempted": "FGA",
        "threePointersMade": "FG3M",
        "threePointersAttempted": "FG3A",
        "freeThrowsMade": "FTM",
        "freeThrowsAttempted": "FTA",
    }

    records: list[dict] = []
    for player_id_value, group in season_rows.groupby("personId", sort=True):
        player_id = str(int(player_id_value))
        logs = group.rename(columns=rename)
        payload = _profile_payload_from_logs(logs, "cap", season)
        fit_row = fit_by_id.get(player_id)
        height, height_cm = _height_fields(
            getattr(fit_row, "height_in", None) if fit_row is not None else None
        )
        team_city = _last_value(group, "teamCity")
        team_name = _last_value(group, "teamName")
        team = " ".join(str(part) for part in (team_city, team_name) if part)
        records.append(
            {
                "player_id": player_id,
                "name": _last_value(group, "personName"),
                "team": team or _last_value(group, "teamTricode"),
                "position": _last_value(group, "position"),
                "jersey": _jersey(_last_value(group, "jerseyNum")),
                "height": height,
                "height_cm": height_cm,
                "weight_lbs": (
                    int(round(float(fit_row.weight_lbs)))
                    if fit_row is not None and pd.notna(fit_row.weight_lbs)
                    else None
                ),
                **{
                    key: value
                    for key, value in payload.items()
                    if key not in {"season", "scale", "data_source"}
                },
            }
        )

    profiles = pd.DataFrame(records).sort_values("player_id").reset_index(drop=True)
    stats = {
        "rows": len(season_rows),
        "players": int(profiles["player_id"].nunique()),
        "games": int(season_rows["gameId"].nunique()),
    }
    return profiles, stats


def build_shots(shot_path: Path) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(shot_path, low_memory=False)
    columns = [
        "PLAYER_ID",
        "GAME_ID",
        "LOC_X",
        "LOC_Y",
        "SHOT_MADE_FLAG",
        "SHOT_TYPE",
        "SHOT_ZONE_BASIC",
        "SHOT_DISTANCE",
    ]
    columns.extend(
        column for column in ("TEAM_ID", "TEAM_NAME", "HTM", "VTM") if column in raw.columns
    )
    missing = set(columns) - set(raw.columns)
    if missing:
        raise ValueError(f"Shot source is missing columns: {sorted(missing)}")
    shots = raw[columns].copy()
    shots = shots[pd.to_numeric(shots["PLAYER_ID"], errors="coerce").notna()]
    shots["PLAYER_ID"] = shots["PLAYER_ID"].astype("int64").astype(str)
    shots = shots.sort_values(["PLAYER_ID", "GAME_ID"]).reset_index(drop=True)
    stats = {
        "rows": len(shots),
        "players": int(shots["PLAYER_ID"].nunique()),
        "games": int(shots["GAME_ID"].nunique()),
    }
    return shots, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build durable player profile and shot snapshots from downloaded source data."
    )
    parser.add_argument("--season", default="2023-24")
    parser.add_argument("--box-scores", type=Path, nargs="+", required=True)
    parser.add_argument("--shot-details", type=Path, required=True)
    parser.add_argument("--fit-pool", type=Path, default=DEFAULT_FIT_POOL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args()

    profiles, profile_stats = build_profiles(args.box_scores, args.season, args.fit_pool)
    shots, shot_stats = build_shots(args.shot_details)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.season.replace("/", "-").replace("\\", "-")
    compression = {"method": "gzip", "compresslevel": 9, "mtime": 0}
    profiles.to_csv(
        args.output_dir / f"{stem}-profiles.csv.gz",
        index=False,
        compression=compression,
    )
    shots.to_csv(
        args.output_dir / f"{stem}-shots.csv.gz",
        index=False,
        compression=compression,
    )
    metadata = {
        "version": "player-season-snapshot-v1",
        "season": args.season,
        "generated_at": args.generated_at,
        "profiles": {
            **profile_stats,
            "source": "NocturneBear/NBA-Data-2010-2024",
            "revision": PROFILE_SOURCE_REVISION,
            "license": "MIT",
        },
        "shots": {
            **shot_stats,
            "source": "shufinskiy/nba_data",
            "revision": SHOT_SOURCE_REVISION,
            "license": "Apache-2.0",
        },
    }
    (args.output_dir / f"{stem}-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
