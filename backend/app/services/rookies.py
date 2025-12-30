from nba_api.stats.endpoints import LeagueDashPlayerStats, CommonPlayerInfo
import pandas as pd
import json
from pathlib import Path
import time

CACHE_PATH = Path("backend/app/data/rookie_height_stream.json")
CACHE_PATH.parent.mkdir(exist_ok=True, parents=True)


HEIGHT_CACHE = Path("backend/app/cache/rookie_heights.csv")

def _build_rookie_height_stream(start_season: int, end_season: int):
    frames = []

    for season in range(start_season, end_season):
        season_str = f"{season}-{str(season+1)[-2:]}"
        print(f"Fetching {season_str} rookies…")

        stats = LeagueDashPlayerStats(
            season=season_str,
            season_type_all_star="Regular Season",
            player_experience_nullable="Rookie"
        ).get_data_frames()[0]

        frames.append(stats)

        time.sleep(1)

    df = pd.concat(frames, ignore_index=True)

    # -------------------------------
    # Load or initialize height cache
    # -------------------------------
    if HEIGHT_CACHE.exists():
        height_df = pd.read_csv(HEIGHT_CACHE)
        heights = dict(zip(height_df.PLAYER_ID, height_df.HEIGHT_IN))
        print(f"Loaded {len(heights)} cached heights")
    else:
        heights = {}

    player_ids = df["PLAYER_ID"].dropna().unique()
    to_fetch = [pid for pid in player_ids if pid not in heights]

    print(f"Need to fetch {len(to_fetch)} new heights")

    for i, pid in enumerate(to_fetch, 1):
        try:
            info = CommonPlayerInfo(player_id=pid).get_data_frames()[0]
            h = info.loc[0, "HEIGHT"]
            if isinstance(h, str) and "-" in h:
                ft, inch = h.split("-")
                heights[pid] = int(ft) * 12 + int(inch)
            else:
                heights[pid] = None

        except Exception:
            heights[pid] = None

        # checkpoint every 25
        if i % 25 == 0:
            print(f"  heights: {i}/{len(to_fetch)} — checkpointing")
            pd.DataFrame(
                [(k, v) for k, v in heights.items()],
                columns=["PLAYER_ID", "HEIGHT_IN"]
            ).to_csv(HEIGHT_CACHE, index=False)

        time.sleep(0.6)

    # final save
    pd.DataFrame(
        [(k, v) for k, v in heights.items()],
        columns=["PLAYER_ID", "HEIGHT_IN"]
    ).to_csv(HEIGHT_CACHE, index=False)

    df["HEIGHT_IN"] = df["PLAYER_ID"].map(heights)

    grouped = (
        df.groupby(["SEASON", "HEIGHT_IN"])
        .agg(players=("PLAYER_ID", "nunique"), minutes=("MIN", "sum"))
        .reset_index()
    )

    grouped["season"] = grouped["SEASON"].str[:4].astype(int)

    return grouped[["season", "HEIGHT_IN", "players", "minutes"]]



def get_rookie_height_stream(start_season=2000, end_season=2025):
    if CACHE_PATH.exists():
        print("Loading cached rookie height stream")
        return json.loads(CACHE_PATH.read_text())

    print("Cache missing — building rookie height stream")
    data = _build_rookie_height_stream(start_season, end_season)

    CACHE_PATH.write_text(json.dumps(data))
    return data
