from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from nba_api.stats.static import players as static_players
from nba_api.stats.static import teams as static_teams

from app.api.endpoints.players import _profile_payload_from_logs


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_ROOT = BACKEND_ROOT / "app" / "cache" / "snapshots"
FIT_MODEL = "fit-v1.0.0"


BOX_RENAME = {
    "points": "PTS", "reboundsTotal": "REB", "assists": "AST",
    "blocks": "BLK", "steals": "STL", "turnovers": "TOV",
    "fieldGoalsMade": "FGM", "fieldGoalsAttempted": "FGA",
    "threePointersMade": "FG3M", "threePointersAttempted": "FG3A",
    "freeThrowsMade": "FTM", "freeThrowsAttempted": "FTA",
    "reboundsOffensive": "OREB", "reboundsDefensive": "DREB",
    "foulsPersonal": "PF",
}
STAT_COLUMNS = ["PTS", "REB", "AST", "BLK", "STL", "TOV", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "PF"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _minutes(value) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value)
    if ":" in text:
        minutes, seconds = text.split(":", 1)
        return float(minutes) + float(seconds) / 60.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{end_year % 100:02d}"


def _canonical_historical(paths: list[Path]) -> pd.DataFrame:
    raw = pd.concat([pd.read_csv(path, low_memory=False) for path in paths], ignore_index=True)
    raw = raw[raw["minutes"].notna()].copy()
    frame = raw.rename(columns=BOX_RENAME)
    frame["season"] = frame["season_year"].astype(str)
    frame["game_id"] = frame["gameId"].astype(str)
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    frame["player_id"] = pd.to_numeric(frame["personId"], errors="coerce").astype("Int64")
    frame["player_name"] = frame["personName"]
    frame["team_id"] = pd.to_numeric(frame["teamId"], errors="coerce").astype("Int64")
    frame["team_name"] = (frame["teamCity"].fillna("").astype(str).str.strip() + " " + frame["teamName"].fillna("").astype(str).str.strip()).str.strip()
    frame["team_abbreviation"] = frame["teamTricode"]
    frame["position"] = frame["position"]
    frame["jersey"] = frame["jerseyNum"]
    frame["minutes_number"] = frame["minutes"].map(_minutes)
    return frame[["season", "game_id", "game_date", "player_id", "player_name", "team_id", "team_name", "team_abbreviation", "position", "jersey", "minutes_number", *STAT_COLUMNS]]


def _canonical_espn(paths: list[Path]) -> tuple[pd.DataFrame, list[dict]]:
    player_ids: dict[str, int] = {}
    for item in static_players.get_players():
        player_ids.setdefault(str(item["full_name"]).casefold(), int(item["id"]))
    team_ids = {str(item["full_name"]).casefold(): int(item["id"]) for item in static_teams.get_teams()}
    frames: list[pd.DataFrame] = []
    source_records: list[dict] = []
    for path in paths:
        raw = pd.read_csv(path, low_memory=False)
        raw = raw[(raw["season_type"] == 2) & (~raw["did_not_play"].fillna(False)) & raw["minutes"].notna()].copy()
        raw["player_id"] = raw["athlete_display_name"].astype(str).str.casefold().map(player_ids)
        raw["team_id"] = raw["team_display_name"].astype(str).str.casefold().map(team_ids)
        unmatched = raw.loc[raw["player_id"].isna(), "athlete_display_name"].dropna().drop_duplicates().sort_values().tolist()
        raw = raw[raw["player_id"].notna() & raw["team_id"].notna()].copy()
        rename = {
            "points": "PTS", "rebounds": "REB", "assists": "AST", "blocks": "BLK",
            "steals": "STL", "turnovers": "TOV", "field_goals_made": "FGM",
            "field_goals_attempted": "FGA", "three_point_field_goals_made": "FG3M",
            "three_point_field_goals_attempted": "FG3A", "free_throws_made": "FTM",
            "free_throws_attempted": "FTA", "offensive_rebounds": "OREB",
            "defensive_rebounds": "DREB", "fouls": "PF",
        }
        frame = raw.rename(columns=rename)
        frame["season"] = raw["season"].map(lambda value: _season_label(int(value)))
        frame["game_id"] = raw["game_id"].astype(str)
        frame["game_date"] = pd.to_datetime(raw["game_date"], errors="coerce")
        frame["player_name"] = raw["athlete_display_name"]
        frame["team_name"] = raw["team_display_name"]
        frame["team_abbreviation"] = raw["team_abbreviation"]
        frame["position"] = raw["athlete_position_abbreviation"]
        frame["jersey"] = raw["athlete_jersey"]
        frame["minutes_number"] = pd.to_numeric(raw["minutes"], errors="coerce").fillna(0.0)
        frames.append(frame[["season", "game_id", "game_date", "player_id", "player_name", "team_id", "team_name", "team_abbreviation", "position", "jersey", "minutes_number", *STAT_COLUMNS]])
        source_records.append({"path": str(path), "sha256": _sha256(path), "unmatched_player_names": unmatched})
    return pd.concat(frames, ignore_index=True), source_records


def _canonical_kaggle(path: Path) -> pd.DataFrame:
    usecols = [
        "firstName", "lastName", "personId", "gameId", "gameType", "gameDate",
        "playerteamId", "playerteamCity", "playerteamName", "startingPosition",
        "numMinutes", "points", "assists", "blocks", "steals",
        "fieldGoalsAttempted", "fieldGoalsMade", "threePointersAttempted",
        "threePointersMade", "freeThrowsAttempted", "freeThrowsMade",
        "reboundsDefensive", "reboundsOffensive", "reboundsTotal",
        "foulsPersonal", "turnovers",
    ]
    team_abbreviations = {int(item["id"]): item["abbreviation"] for item in static_teams.get_teams()}
    chunks = []
    for raw in pd.read_csv(path, usecols=usecols, chunksize=150_000, low_memory=False, compression=None):
        raw = raw[(raw["gameType"] == "Regular Season") & raw["numMinutes"].notna()].copy()
        raw["game_date"] = pd.to_datetime(raw["gameDate"], errors="coerce")
        raw = raw[raw["game_date"].notna()].copy()
        years = raw["game_date"].dt.year
        start_years = years.where(raw["game_date"].dt.month >= 7, years - 1)
        raw["season"] = start_years.astype(int).astype(str) + "-" + ((start_years + 1) % 100).astype(int).astype(str).str.zfill(2)
        rename = {
            "points": "PTS", "reboundsTotal": "REB", "assists": "AST", "blocks": "BLK",
            "steals": "STL", "turnovers": "TOV", "fieldGoalsMade": "FGM",
            "fieldGoalsAttempted": "FGA", "threePointersMade": "FG3M",
            "threePointersAttempted": "FG3A", "freeThrowsMade": "FTM",
            "freeThrowsAttempted": "FTA", "reboundsOffensive": "OREB",
            "reboundsDefensive": "DREB", "foulsPersonal": "PF",
        }
        frame = raw.rename(columns=rename)
        frame["game_id"] = raw["gameId"].astype(str)
        frame["player_id"] = pd.to_numeric(raw["personId"], errors="coerce").astype("Int64")
        frame["player_name"] = (raw["firstName"].fillna("").astype(str).str.strip() + " " + raw["lastName"].fillna("").astype(str).str.strip()).str.strip()
        frame["team_id"] = pd.to_numeric(raw["playerteamId"], errors="coerce").astype("Int64")
        frame["team_name"] = (raw["playerteamCity"].fillna("").astype(str).str.strip() + " " + raw["playerteamName"].fillna("").astype(str).str.strip()).str.strip()
        frame["team_abbreviation"] = frame["team_id"].map(team_abbreviations).fillna(raw["playerteamName"].astype(str).str[:3].str.upper())
        frame["position"] = raw["startingPosition"]
        frame["jersey"] = None
        frame["minutes_number"] = pd.to_numeric(raw["numMinutes"], errors="coerce").fillna(0.0)
        chunks.append(frame[["season", "game_id", "game_date", "player_id", "player_name", "team_id", "team_name", "team_abbreviation", "position", "jersey", "minutes_number", *STAT_COLUMNS]])
    return pd.concat(chunks, ignore_index=True)


def _last(group: pd.DataFrame, column: str):
    values = group.sort_values("game_date")[column].dropna()
    return None if values.empty else values.iloc[-1]


def _height_map() -> dict[int, float]:
    path = BACKEND_ROOT / "app" / "cache" / "player_heights.csv"
    frame = pd.read_csv(path)
    return dict(zip(frame["PLAYER_ID"].astype(int), pd.to_numeric(frame["HEIGHT_IN"], errors="coerce")))


def _profile_frame(rows: pd.DataFrame, season: str, heights: dict[int, float]) -> pd.DataFrame:
    records = []
    for player_id, group in rows.groupby("player_id", sort=True):
        logs = group.rename(columns={"game_date": "GAME_DATE"})
        payload = _profile_payload_from_logs(logs, "cap", season)
        height_in = heights.get(int(player_id))
        records.append({
            "player_id": str(int(player_id)), "name": _last(group, "player_name"),
            "team": _last(group, "team_name"), "position": _last(group, "position"),
            "jersey": _last(group, "jersey"),
            "height": None if pd.isna(height_in) else f"{int(height_in) // 12}-{int(height_in) % 12}",
            "height_cm": None if pd.isna(height_in) else round(float(height_in) * 2.54),
            "weight_lbs": None,
            **{key: value for key, value in payload.items() if key not in {"season", "scale", "data_source"}},
        })
    return pd.DataFrame(records).sort_values("player_id").reset_index(drop=True)


def _fit_frame(rows: pd.DataFrame, heights: dict[int, float]) -> pd.DataFrame:
    grouped = rows.groupby("player_id", sort=True)
    totals = grouped[STAT_COLUMNS + ["minutes_number"]].sum(numeric_only=True)
    totals["GP"] = grouped["game_id"].nunique()
    totals["PLAYER_NAME"] = grouped["player_name"].last()
    totals["TEAM_ABBREVIATION"] = grouped["team_abbreviation"].last()
    minutes = totals["minutes_number"].replace(0, np.nan)
    play_load = totals["FGA"] + 0.44 * totals["FTA"] + totals["TOV"]
    league_load_per_minute = float(play_load.sum() / minutes.sum()) if minutes.sum() else 1.0
    per100_factor = 48.0 / minutes
    result = pd.DataFrame(index=totals.index)
    result["PLAYER_ID"] = result.index.astype(int)
    result["PLAYER_NAME"] = totals["PLAYER_NAME"]
    result["TEAM_ABBREVIATION"] = totals["TEAM_ABBREVIATION"]
    result["GP"] = totals["GP"]
    result["MIN"] = totals["minutes_number"]
    result["height_in"] = [heights.get(int(pid), 78.0) for pid in result.index]
    result["height_in"] = pd.to_numeric(result["height_in"], errors="coerce").fillna(78.0)
    result["weight_lbs"] = 215.0
    result["USG_PCT"] = (20.0 * (play_load / minutes) / max(league_load_per_minute, 0.01)).clip(0, 50)
    result["AST_PCT"] = (totals["AST"] * per100_factor).clip(0, 60)
    result["TOV_PCT"] = (totals["TOV"] / play_load.replace(0, np.nan) * 100.0).fillna(0.0)
    for source, target in (("PTS", "PTS_PER100"), ("FGA", "FGA_PER100"), ("FG3A", "FG3A_PER100"), ("STL", "STL_PER100"), ("BLK", "BLK_PER100"), ("PF", "PF_PER100")):
        result[target] = totals[source] * per100_factor
    result["FTAR"] = (totals["FTA"] / totals["FGA"].replace(0, np.nan)).fillna(0.0)
    result["FG3_PCT"] = (totals["FG3M"] / totals["FG3A"].replace(0, np.nan) * 100.0).fillna(0.0)
    result["TS_PCT"] = (totals["PTS"] / (2.0 * (totals["FGA"] + 0.44 * totals["FTA"])).replace(0, np.nan) * 100.0).fillna(0.0)
    result["EFG_PCT"] = ((totals["FGM"] + 0.5 * totals["FG3M"]) / totals["FGA"].replace(0, np.nan) * 100.0).fillna(0.0)
    result["ORB_PCT"] = (totals["OREB"] * per100_factor).clip(0, 30)
    result["DRB_PCT"] = (totals["DREB"] * per100_factor).clip(0, 50)
    return result.reset_index(drop=True)


def _team_game_rows(player_rows: pd.DataFrame) -> pd.DataFrame:
    grouped = player_rows.groupby(["season", "game_id", "team_id"], sort=False)
    games = grouped[STAT_COLUMNS].sum().reset_index()
    games["TEAM_NAME"] = grouped["team_name"].last().to_numpy()
    games["TEAM_ABBREVIATION"] = grouped["team_abbreviation"].last().to_numpy()
    return games


def _team_profiles(games: pd.DataFrame, season: str) -> pd.DataFrame:
    rows = games[games["season"] == season].copy()
    opponent = rows[["game_id", "team_id", *STAT_COLUMNS]].copy()
    opponent = opponent.rename(columns={"team_id": "opponent_team_id", **{column: f"OPP_{column}" for column in STAT_COLUMNS}})
    paired = rows.merge(opponent, on="game_id", how="left")
    paired = paired[paired["team_id"] != paired["opponent_team_id"]]
    grouped = paired.groupby("team_id", sort=True)
    raw = grouped[[*STAT_COLUMNS, *[f"OPP_{column}" for column in STAT_COLUMNS]]].mean()
    raw["team_name"] = grouped["TEAM_NAME"].last()
    raw["team_abbreviation"] = grouped["TEAM_ABBREVIATION"].last()
    raw["games"] = grouped["game_id"].nunique()

    def pct(series: pd.Series, inverse=False) -> pd.Series:
        ranked = series.rank(pct=True) * 100.0
        return (100.0 - ranked if inverse else ranked).round(1)

    result = pd.DataFrame(index=raw.index)
    result["team_id"] = result.index.astype(int)
    result["team_name"] = raw["team_name"]
    result["team_abbreviation"] = raw["team_abbreviation"]
    result["games"] = raw["games"]
    mapping = {"points": "PTS", "rebounds": "REB", "assists": "AST", "blocks": "BLK", "steals": "STL", "fg_pct": "FG_PCT", "fg3_pct": "FG3_PCT", "turnovers": "TOV"}
    raw["FG_PCT"] = raw["FGM"] / raw["FGA"].replace(0, np.nan) * 100.0
    raw["FG3_PCT"] = raw["FG3M"] / raw["FG3A"].replace(0, np.nan) * 100.0
    raw["OPP_FG_PCT"] = raw["OPP_FGM"] / raw["OPP_FGA"].replace(0, np.nan) * 100.0
    raw["OPP_FG3_PCT"] = raw["OPP_FG3M"] / raw["OPP_FG3A"].replace(0, np.nan) * 100.0
    raw["OPP_FT_PCT"] = raw["OPP_FTM"] / raw["OPP_FTA"].replace(0, np.nan) * 100.0
    for output, source in mapping.items():
        result[output] = pct(raw[source], inverse=(output == "turnovers"))
        result[f"raw_{output if output != 'turnovers' else 'tov'}"] = raw[source].round(1)
    opp_mapping = {"opp_points": "OPP_PTS", "opp_fg_pct": "OPP_FG_PCT", "opp_fg3_pct": "OPP_FG3_PCT", "opp_ast": "OPP_AST", "opp_reb": "OPP_REB", "opp_ftm": "OPP_FTM", "opp_ft_pct": "OPP_FT_PCT"}
    for output, source in opp_mapping.items():
        result[output] = pct(raw[source], inverse=True)
        result[f"raw_{output}"] = raw[source].round(1)
    result["scale"] = "percentile"
    result["scale_used"] = "percentile"
    result["opp_scale"] = "percentile"
    result["opponent_scale"] = "percentile"
    result["season"] = season
    result["data_source"] = "packaged_snapshot"
    return result.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build versioned comparison snapshots for every supplied season.")
    parser.add_argument("--historical-box", type=Path, nargs="*", default=[])
    parser.add_argument("--espn-box", type=Path, nargs="*", default=[])
    parser.add_argument("--kaggle-player-stats", type=Path)
    parser.add_argument("--output-root", type=Path, default=SNAPSHOT_ROOT)
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args()

    if not args.kaggle_player_stats and not args.historical_box and not args.espn_box:
        parser.error("provide --kaggle-player-stats or at least one box-score source")
    historical = _canonical_historical(args.historical_box) if args.historical_box else pd.DataFrame()
    espn, espn_sources = _canonical_espn(args.espn_box) if args.espn_box else (pd.DataFrame(), [])
    broad = _canonical_kaggle(args.kaggle_player_stats) if args.kaggle_player_stats else pd.DataFrame()
    # The broad NBA-ID source is authoritative when present. Other inputs remain
    # supported for incremental refreshes, not for narrowing historical scope.
    rows = broad if not broad.empty else pd.concat([historical, espn], ignore_index=True)
    heights = _height_map()
    compression = {"method": "gzip", "compresslevel": 9, "mtime": 0}
    coverage = []
    profile_frames = []
    fit_frames = []
    team_frames = []
    for season in sorted(rows["season"].dropna().unique()):
        season_rows = rows[rows["season"] == season].copy()
        profiles = _profile_frame(season_rows, season, heights)
        fit_supported = int(season.split("-", 1)[0]) >= 1996
        fit = _fit_frame(season_rows, heights) if fit_supported else None
        team_profiles = _team_profiles(_team_game_rows(season_rows), season)
        player_dir = args.output_root / "player-seasons"
        fit_dir = args.output_root / "fit" / FIT_MODEL
        team_dir = args.output_root / "team-seasons"
        for directory in (player_dir, fit_dir, team_dir):
            directory.mkdir(parents=True, exist_ok=True)
        profiles.insert(0, "season", season)
        profile_frames.append(profiles)
        if fit is not None:
            fit.insert(0, "season", season)
            fit_frames.append(fit)
        team_frames.append(team_profiles)
        coverage.append({"season": season, "profiles": True, "fit": fit_supported, "teams": True, "shots": (player_dir / f"{season}-shots.csv.gz").is_file(), "complete": True})
    pd.concat(profile_frames, ignore_index=True).to_csv(
        args.output_root / "player-seasons" / "profiles.csv.gz",
        index=False,
        compression=compression,
    )
    pd.concat(fit_frames, ignore_index=True).to_csv(
        args.output_root / "fit" / FIT_MODEL / "player-pools.csv.gz",
        index=False,
        compression=compression,
    )
    pd.concat(team_frames, ignore_index=True).to_csv(
        args.output_root / "team-seasons" / "profiles.csv.gz",
        index=False,
        compression=compression,
    )
    sources = {
        "shots": {
            "repository": "shufinskiy/nba_data",
            "revision": "e829d4678be1e075f99e5d41a1c5f97089be446b",
            "license": "Apache-2.0",
        },
    }
    if args.historical_box:
        sources["historical"] = {
            "repository": "NocturneBear/NBA-Data-2010-2024",
            "revision": "a5f108b5b1f08074d78b9e8e901926a9ce4c06c5",
            "license": "MIT",
            "inputs": [{"filename": path.name, "sha256": _sha256(path)} for path in args.historical_box],
        }
    if espn_sources:
        sources["supplemental_current"] = {
            "repository": "sportsdataverse/sportsdataverse-data",
            "release": "espn_nba_player_boxscores",
            "license": "MIT",
            "inputs": espn_sources,
        }
    if args.kaggle_player_stats:
        sources["broad_history"] = {
            "dataset": "eoinamoore/historical-nba-data-and-player-box-scores",
            "version": 515,
            "license": "CC0-1.0",
            "source": "NBA.com",
            "input": {"filename": args.kaggle_player_stats.name, "sha256": _sha256(args.kaggle_player_stats)},
        }
    manifest = {
        "version": "comparison-coverage-v1", "generated_at": args.generated_at,
        "seasons": sorted(coverage, key=lambda item: item["season"], reverse=True),
        "sources": sources,
    }
    (args.output_root / "coverage.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seasons": len(coverage), "latest": coverage[-1]["season"]}, indent=2))


if __name__ == "__main__":
    main()
