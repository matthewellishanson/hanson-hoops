import time
import pandas as pd
from pathlib import Path
from nba_api.stats.endpoints import LeagueDashPlayerStats

OUT = Path("docs/data/pts_per_100_api_cache.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

if OUT.exists():
    cache = pd.read_csv(OUT)
    done = set(cache["rookie_season"])
    print("Resuming. Already have:", sorted(done))
else:
    cache = pd.DataFrame(columns=["player_id", "rookie_season", "pts_per_100"])
    done = set()

seasons = range(2001, 2026)

rows = []

for season in seasons:
    if season in done:
        continue

    season_str = f"{season-1}-{str(season)[-2:]}"
    print("Fetching", season_str)

    try:
        stats = LeagueDashPlayerStats(
            season=season_str,
            per_mode_detailed="Per100Possessions"
        ).get_data_frames()[0]

        stats = stats.rename(columns={
            "PLAYER_ID": "player_id",
            "PTS": "pts_per_100"
        })

        stats["rookie_season"] = season
        rows.append(stats[["player_id", "rookie_season", "pts_per_100"]])

        time.sleep(2)

    except Exception as e:
        print("⚠️ Failed:", season, e)
        time.sleep(5)

if rows:
    cache = pd.concat([cache, *rows], ignore_index=True)
    cache.to_csv(OUT, index=False)

print("Saved cache:", OUT)
print(cache.tail())
