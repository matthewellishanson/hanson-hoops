from __future__ import annotations

import inspect
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats

from app.services.nba_http import nba_call, request_timeout_seconds
from app.services.snapshots import load_fit_pool, save_runtime_fit_pool

try:
    from nba_api.stats.endpoints import leaguedashplayerbiostats
except Exception:  # pragma: no cover - endpoint availability varies
    leaguedashplayerbiostats = None


def _to_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    # Normalize mixed-type nba_api fields into numeric series with explicit fallback.
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _height_to_inches(val: object) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str) or "-" not in val:
        return float("nan")
    try:
        feet, inches = val.split("-", 1)
        return float(int(feet) * 12 + int(inches))
    except Exception:
        return float("nan")


def _first_existing(df: pd.DataFrame, candidates: list[str], default: float = 0.0) -> pd.Series:
    for c in candidates:
        if c in df.columns:
            return _to_numeric(df[c], default=default)
    return pd.Series([default] * len(df), index=df.index, dtype="float64")


def _ldps_df(season_fmt: str, measure: str, per_mode: str) -> pd.DataFrame:
    # Compatibility wrapper across nba_api versions where argument names vary.
    kwargs = {
        "season": season_fmt,
        "season_type_all_star": "Regular Season",
        "per_mode_detailed": per_mode,
    }
    try:
        sig = inspect.signature(leaguedashplayerstats.LeagueDashPlayerStats.__init__)
        params = sig.parameters
    except Exception:
        params = {}

    if "measure_type_detailed_def" in params:
        kwargs["measure_type_detailed_def"] = measure
    elif "measure_type_detailed" in params:
        kwargs["measure_type_detailed"] = measure

    if "league_id_nullable" in params:
        kwargs["league_id_nullable"] = "00"
    elif "league_id" in params:
        kwargs["league_id"] = "00"

    if "timeout" in params:
        kwargs["timeout"] = request_timeout_seconds()

    frames = nba_call(
        f"league_dash_player_stats:{measure}:{per_mode}",
        lambda: leaguedashplayerstats.LeagueDashPlayerStats(**kwargs).get_data_frames(),
    )
    return frames[0] if frames and len(frames) > 0 else pd.DataFrame()


def _bio_df(season_fmt: str) -> pd.DataFrame:
    # Bio endpoint is optional; disabled by default to keep first fit call fast.
    if os.getenv("FIT_USE_BIO_ENDPOINT", "0") != "1":
        return pd.DataFrame()
    if leaguedashplayerbiostats is None:
        return pd.DataFrame()

    kwargs = {"season": season_fmt}
    try:
        sig = inspect.signature(leaguedashplayerbiostats.LeagueDashPlayerBioStats.__init__)
        params = sig.parameters
    except Exception:
        params = {}

    if "season_type_all_star" in params:
        kwargs["season_type_all_star"] = "Regular Season"
    if "league_id_nullable" in params:
        kwargs["league_id_nullable"] = "00"
    elif "league_id" in params:
        kwargs["league_id"] = "00"
    if "timeout" in params:
        kwargs["timeout"] = request_timeout_seconds()

    try:
        frames = nba_call(
            "league_dash_player_bio_stats",
            lambda: leaguedashplayerbiostats.LeagueDashPlayerBioStats(**kwargs).get_data_frames(),
        )
        return frames[0] if frames and len(frames) > 0 else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _height_cache_df() -> pd.DataFrame:
    # Local cache fallback for player height when bio endpoint is unavailable/disabled.
    p = Path(__file__).resolve().parents[1] / "cache" / "player_heights.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame()
    out = pd.DataFrame()
    if "PLAYER_ID" in df.columns:
        out["PLAYER_ID"] = _to_numeric(df["PLAYER_ID"]).astype("Int64")
    if "HEIGHT_IN" in df.columns:
        out["height_in"] = _to_numeric(df["HEIGHT_IN"])
    return out


@lru_cache(maxsize=8)
def player_pool(season_fmt: str, min_minutes: int = 300) -> pd.DataFrame:
    # Build the player feature base table used by the fit model.
    # We mix totals + per100 + advanced tables, then filter by minutes.
    model_version = "fit-v1.0.0"
    snapshot, snapshot_source = (None, None)
    if os.getenv("NBA_FORCE_LIVE_REFRESH", "0") != "1":
        snapshot, snapshot_source = load_fit_pool(season_fmt, model_version)
    required_snapshot_columns = {
        "PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN",
        "height_in", "weight_lbs", "USG_PCT", "AST_PCT", "TOV_PCT",
        "PTS_PER100", "FGA_PER100", "FTAR", "FG3A_PER100", "FG3_PCT",
        "TS_PCT", "EFG_PCT", "STL_PER100", "BLK_PER100", "ORB_PCT",
        "DRB_PCT", "PF_PER100",
    }
    if snapshot is not None and required_snapshot_columns.issubset(snapshot.columns):
        snapshot["MIN"] = _to_numeric(snapshot.get("MIN", pd.Series(dtype="float64")))
        result = snapshot[snapshot["MIN"] >= float(min_minutes)].copy().reset_index(drop=True)
        result.attrs["data_source"] = snapshot_source
        return result

    base_totals = _ldps_df(season_fmt, measure="Base", per_mode="Totals")
    base_p100 = _ldps_df(season_fmt, measure="Base", per_mode="Per100Possessions")
    advanced = _ldps_df(season_fmt, measure="Advanced", per_mode="Per100Possessions")

    if base_totals.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["PLAYER_ID"] = _to_numeric(base_totals.get("PLAYER_ID", pd.Series(dtype="float64"))).astype("Int64")
    out["PLAYER_NAME"] = (
        base_totals["PLAYER_NAME"].astype(str)
        if "PLAYER_NAME" in base_totals.columns
        else pd.Series([""] * len(base_totals), index=base_totals.index, dtype="object")
    )
    out["TEAM_ABBREVIATION"] = (
        base_totals["TEAM_ABBREVIATION"].astype(str)
        if "TEAM_ABBREVIATION" in base_totals.columns
        else pd.Series([""] * len(base_totals), index=base_totals.index, dtype="object")
    )
    out["GP"] = _first_existing(base_totals, ["GP"])
    out["MIN"] = _first_existing(base_totals, ["MIN"])
    out["FGA_TOTAL"] = _first_existing(base_totals, ["FGA"])
    out["FTA_TOTAL"] = _first_existing(base_totals, ["FTA"])

    if not base_p100.empty:
        keyed = base_p100.set_index(_to_numeric(base_p100["PLAYER_ID"]).astype("Int64"))
        out = out.set_index("PLAYER_ID")
        out["PTS_PER100"] = _first_existing(keyed, ["PTS"])
        out["FGA_PER100"] = _first_existing(keyed, ["FGA"])
        out["FTA_PER100"] = _first_existing(keyed, ["FTA"])
        out["FG3A_PER100"] = _first_existing(keyed, ["FG3A"])
        out["FG3_PCT"] = _first_existing(keyed, ["FG3_PCT"]) * 100.0
        out["STL_PER100"] = _first_existing(keyed, ["STL"])
        out["BLK_PER100"] = _first_existing(keyed, ["BLK"])
        out["PF_PER100"] = _first_existing(keyed, ["PF"])
        out = out.reset_index()
    else:
        out["PTS_PER100"] = 0.0
        out["FGA_PER100"] = 0.0
        out["FTA_PER100"] = 0.0
        out["FG3A_PER100"] = 0.0
        out["FG3_PCT"] = 0.0
        out["STL_PER100"] = 0.0
        out["BLK_PER100"] = 0.0
        out["PF_PER100"] = 0.0

    if not advanced.empty:
        keyed = advanced.set_index(_to_numeric(advanced["PLAYER_ID"]).astype("Int64"))
        out = out.set_index("PLAYER_ID")
        out["USG_PCT"] = _first_existing(keyed, ["USG_PCT"]) * 100.0
        out["AST_PCT"] = _first_existing(keyed, ["AST_PCT"]) * 100.0
        out["TOV_PCT"] = _first_existing(keyed, ["TOV_PCT"]) * 100.0
        out["TS_PCT"] = _first_existing(keyed, ["TS_PCT"]) * 100.0
        out["EFG_PCT"] = _first_existing(keyed, ["EFG_PCT"]) * 100.0
        out["ORB_PCT"] = _first_existing(keyed, ["OREB_PCT", "ORB_PCT"]) * 100.0
        out["DRB_PCT"] = _first_existing(keyed, ["DREB_PCT", "DRB_PCT"]) * 100.0
        out = out.reset_index()
    else:
        out["USG_PCT"] = 0.0
        out["AST_PCT"] = 0.0
        out["TOV_PCT"] = 0.0
        out["TS_PCT"] = 0.0
        out["EFG_PCT"] = 0.0
        out["ORB_PCT"] = 0.0
        out["DRB_PCT"] = 0.0

    out["FTAR"] = (out["FTA_TOTAL"] / out["FGA_TOTAL"].replace(0, pd.NA)).fillna(0.0)
    out["MIN"] = _to_numeric(out["MIN"])
    out["GP"] = _to_numeric(out["GP"])
    bio = _bio_df(season_fmt)
    if not bio.empty and "PLAYER_ID" in bio.columns:
        body = pd.DataFrame()
        body["PLAYER_ID"] = _to_numeric(bio["PLAYER_ID"]).astype("Int64")
        if "PLAYER_HEIGHT" in bio.columns:
            body["height_in"] = bio["PLAYER_HEIGHT"].map(_height_to_inches)
        if "PLAYER_WEIGHT" in bio.columns:
            body["weight_lbs"] = _to_numeric(bio["PLAYER_WEIGHT"], default=float("nan"))
        out = out.merge(body.drop_duplicates(subset=["PLAYER_ID"]), on="PLAYER_ID", how="left")

    if "height_in" not in out.columns:
        out["height_in"] = float("nan")
    if "weight_lbs" not in out.columns:
        out["weight_lbs"] = float("nan")

    hcache = _height_cache_df()
    if not hcache.empty:
        out = out.merge(hcache, on="PLAYER_ID", how="left", suffixes=("", "_cache"))
        out["height_in"] = out["height_in"].fillna(out.get("height_in_cache"))
        out.drop(columns=[c for c in ["height_in_cache"] if c in out.columns], inplace=True)

    out["height_in"] = _to_numeric(out["height_in"], default=float("nan"))
    out["weight_lbs"] = _to_numeric(out["weight_lbs"], default=float("nan"))
    height_median = out["height_in"].median()
    weight_median = out["weight_lbs"].median()
    out["height_in"] = out["height_in"].fillna(height_median if pd.notna(height_median) else 78.0)
    out["weight_lbs"] = out["weight_lbs"].fillna(weight_median if pd.notna(weight_median) else 215.0)

    keep_cols = [
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ABBREVIATION",
        "GP",
        "MIN",
        "height_in",
        "weight_lbs",
        "USG_PCT",
        "AST_PCT",
        "TOV_PCT",
        "PTS_PER100",
        "FGA_PER100",
        "FTAR",
        "FG3A_PER100",
        "FG3_PCT",
        "TS_PCT",
        "EFG_PCT",
        "STL_PER100",
        "BLK_PER100",
        "ORB_PCT",
        "DRB_PCT",
        "PF_PER100",
    ]
    out = out[keep_cols].copy()
    out["PLAYER_ID"] = out["PLAYER_ID"].astype(int)
    out = out.reset_index(drop=True)
    save_runtime_fit_pool(season_fmt, model_version, out)
    result = out[out["MIN"] >= float(min_minutes)].copy().reset_index(drop=True)
    result.attrs["data_source"] = "live"
    return result
