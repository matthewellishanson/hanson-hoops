# backend/app/services/rookies.py

from nba_api.stats.endpoints import LeagueDashPlayerStats, CommonPlayerInfo 
import pandas as pd
from pathlib import Path
import time

CACHE_DIR = Path("app/cache")
CACHE_DIR.mkdir(exist_ok=True)

HEIGHT_CACHE = CACHE_DIR / "player_heights.csv"
STREAM_CACHE = CACHE_DIR / "rookie_heights.csv"


def _load_height_cache():
    if HEIGHT_CACHE.exists():
        return pd.read_csv(HEIGHT_CACHE)
    return pd.DataFrame(columns=["PLAYER_ID", "HEIGHT_IN"])


def _save_height_cache(df):
    df.to_csv(HEIGHT_CACHE, index=False)


def _get_player_height(player_id):
    info = CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
    h = info.loc[0, "HEIGHT"]
    feet, inches = h.split("-")
    return int(feet) * 12 + int(inches)


def _build_rookie_height_stream(start_season, end_season):
    height_cache = _load_height_cache()
    height_map = dict(zip(height_cache.PLAYER_ID, height_cache.HEIGHT_IN))

    rows = []
    if STREAM_CACHE.exists():
        rows = pd.read_csv(STREAM_CACHE).to_dict("records")

    existing_seasons = {r["season"] for r in rows}

    for season in range(start_season, end_season):
        if season in existing_seasons:
            continue
        season_str = f"{season}-{str(season+1)[-2:]}"
        print(f"Fetching {season_str} rookies…")

        stats = LeagueDashPlayerStats(
            season=season_str,
            season_type_all_star="Regular Season"
        ).get_data_frames()[0]

        if "PLAYER_EXPERIENCE" in stats.columns:
            stats = stats[stats["PLAYER_EXPERIENCE"].str.lower() == "rookie"]

        heights = []

        for pid in stats["PLAYER_ID"].unique():
            if pid not in height_map:
                try:
                    height_map[pid] = _get_player_height(pid)
                    print(f"Fetched height for {pid}")
                    time.sleep(0.6)
                except Exception as e:
                    print(f"Height fetch failed for {pid}: {e}")
                    continue

            heights.append({"PLAYER_ID": pid, "HEIGHT_IN": height_map[pid]})

        # Save full height cache safely
        _save_height_cache(pd.DataFrame(
            list(height_map.items()),
            columns=["PLAYER_ID", "HEIGHT_IN"]
        ).drop_duplicates())

        stats = stats.merge(pd.DataFrame(heights), on="PLAYER_ID", how="left")
        stats = stats.dropna(subset=["HEIGHT_IN"])

        grouped = (
            stats.groupby("HEIGHT_IN")
            .agg(players=("PLAYER_ID", "nunique"), minutes=("MIN", "sum"))
            .reset_index()
        )

        grouped["season"] = season
        rows.extend(grouped.to_dict("records"))

        pd.DataFrame(rows).to_csv(STREAM_CACHE, index=False)

    return rows


def get_rookie_height_stream(start_season=2000, end_season=2025):
    if STREAM_CACHE.exists():
        print("Loaded cached rookie height stream")
        df = pd.read_csv(STREAM_CACHE)
        last = int(df["season"].max())
        print(f"Resuming from season {last + 1}")
        new = _build_rookie_height_stream(last + 1, end_season)
        return pd.concat([df, pd.DataFrame(new)]).to_dict("records")

    print("Building rookie height stream cache…")
    data = _build_rookie_height_stream(start_season, end_season)
    return data
