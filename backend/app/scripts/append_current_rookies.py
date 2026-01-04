import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerStats, CommonPlayerInfo
from pathlib import Path
import time

SNAPSHOT = Path("app/cache/rookie_snapshot.csv")
CURRENT_SEASON = "2025-26"
ROOKIE_YEAR = 2026  # ending year label

print("Fetching", CURRENT_SEASON)
resp = LeagueDashPlayerStats(
    season=CURRENT_SEASON,
    per_mode_detailed="Totals",
    season_type_all_star="Regular Season"
)
df = resp.get_data_frames()[0]
df.columns = df.columns.str.lower()

print("Players fetched:", len(df))

rookies = []
total_players = len(df)

for idx, (_, row) in enumerate(df.iterrows(), 1):
    pid = row["player_id"]
    player_name = row["player_name"]
    
    print(f"Processing {idx}/{total_players}: {player_name}")

    try:
        info = CommonPlayerInfo(player_id=pid).get_data_frames()[0]
        first_season = info.loc[0, "FROM_YEAR"]

        if int(first_season) == 2025:
            rookies.append({
                "player": row["player_name"],
                "player_id": pid,
                "rookie_season": ROOKIE_YEAR,
                "minutes": row["min"],
                "games": row["gp"],
                "pts": row["pts"],
                "fga": row["fga"],
                "fgm": row["fgm"],
                "fg_pct": row["fg_pct"],
                "pace": row.get("pace"),
                "position": row.get("player_position")
            })
            print(f"✓ Added rookie: {player_name}")

    except Exception as e:
        print(f"Skipping {pid}: {e}")

    time.sleep(0.6)  # rate limit protection

rookies_df = pd.DataFrame(rookies)
print("Rookies found:", len(rookies_df))

existing = pd.read_csv(SNAPSHOT)

combined = pd.concat([existing, rookies_df], ignore_index=True)
combined.to_csv(SNAPSHOT, index=False)

print("Updated snapshot saved:", SNAPSHOT)
