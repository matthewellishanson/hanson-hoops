import pandas as pd
import time
from nba_api.stats.endpoints import LeagueDashPlayerStats

OUT = "docs/data/true_total_minutes.csv"

all_rows = []

for season in range(2000, 2027):
    season_str = f"{season}-{str(season+1)[-2:]}"
    print(f"Fetching {season_str}...")

    success = False
    for attempt in range(3):
        try:
            stats = LeagueDashPlayerStats(
                season=season_str,
                season_type_all_star="Regular Season",
                per_mode_detailed="Totals",
                timeout=60
            )

            df = stats.get_data_frames()[0]
            df = df[["PLAYER_ID", "MIN"]].copy()
            df["rookie_season"] = season + 1
            df = df.rename(columns={"PLAYER_ID": "player_id", "MIN": "minutes"})

            all_rows.append(df)
            success = True
            break

        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(10)

    if not success:
        print(f"❌ Skipping {season_str} after 3 failed attempts")

    # polite delay to avoid being rate limited
    time.sleep(5)

# Save after loop
minutes = pd.concat(all_rows, ignore_index=True)
minutes.to_csv(OUT, index=False)

print(f"\nSaved {len(minutes)} rows → {OUT}")
print(minutes.describe())
