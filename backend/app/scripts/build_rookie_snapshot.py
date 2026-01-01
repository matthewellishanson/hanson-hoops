# backend/app/scripts/build_rookie_snapshot.py

"""
Build a canonical rookie-season snapshot table for cross-era analysis.

Output: rookie_snapshot.csv

Each row = one player's rookie season (subject to minutes cutoff)
"""

from nba_api.stats.endpoints import LeagueDashPlayerStats, CommonPlayerInfo
from nba_api.stats.static import players as static_players
import pandas as pd
from pathlib import Path
import time
import unicodedata
import re
import random
from app.utils.seasons import format_season, current_nba_season


# ------------------------
# Configuration
# ------------------------

CURRENT_SEASON = current_nba_season()

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR.parent / "cache"  # backend/app/cache

CACHE_DIR.mkdir(exist_ok=True)

DRAFT_CLASSES_PATH = CACHE_DIR / "draft_classes.csv"
OUTPUT_PATH = CACHE_DIR / "rookie_snapshot.csv"

MIN_MINUTES = 300
MAX_MINUTES = None  # set to 1200 if you want a hard upper bound

SLEEP_BETWEEN_CALLS = 0.6

PROGRESS_PATH = CACHE_DIR / "rookie_snapshot_partial.csv"


# ------------------------
# Helpers
# ------------------------

def with_retries(fn, *, retries=5, base_sleep=2):
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            if i == retries - 1:
                raise
            sleep = base_sleep * (2 ** i) + random.uniform(0, 1)
            print(f"Retry {i+1}/{retries} after error: {e} — sleeping {sleep:.1f}s")
            time.sleep(sleep)


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^a-z ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

def format_season(year: int) -> str:
    """Convert 2004 -> '2004-05'"""
    return f"{year}-{str(year+1)[-2:]}"


def fetch_player_bio_raw(player_id: int) -> dict:
    """Fetch bio fields from CommonPlayerInfo."""
    info = CommonPlayerInfo(player_id=player_id, timeout=60).get_data_frames()[0].iloc[0]

    height = info.get("HEIGHT")
    weight = info.get("WEIGHT")

    def height_to_inches(h):
        if isinstance(h, str) and "-" in h:
            f, i = h.split("-")
            return int(f) * 12 + int(i)
        return None

    return {
        "height_in": height_to_inches(height),
        "weight_lbs": int(weight) if str(weight).isdigit() else None,
        "position": info.get("POSITION"),
        "birthdate": info.get("BIRTHDATE"),
    }

def build_name_to_nba_id_map():
    all_players = static_players.get_players()
    return {
        normalize_name(p["full_name"]): p["id"]
        for p in all_players
    }




# ------------------------
# Core Builder
# ------------------------

def build_rookie_snapshot(draft_classes: pd.DataFrame, name_to_nba: dict) -> pd.DataFrame:

    rows = []

    # ---- Resume support ----
    existing_ids = set()
    if PROGRESS_PATH.exists():
        existing = pd.read_csv(PROGRESS_PATH)
        existing_ids = set(existing["player_id"])
        print(f"Resuming — {len(existing_ids)} players already processed")

    # ---- Cache season stats across players ----
    season_cache = {}

    def get_season_stats(season_fmt):
        if season_fmt not in season_cache:
            print(f"Fetching league stats for {season_fmt}…")
            season_cache[season_fmt] = with_retries(lambda: LeagueDashPlayerStats(
                season=season_fmt,
                season_type_all_star="Regular Season",
                measure_type_detailed_defense="Base",
                per_mode_detailed="Totals",
                timeout=60
            ).get_data_frames()[0])
        return season_cache[season_fmt]

    for _, player in draft_classes.iterrows():
        player_name = normalize_name(player["player"])
        pid = name_to_nba.get(player_name)

        if pid is None:
            print(f"Skipping {player['player']} — no NBA ID match")
            continue

        # ---- Skip already processed ----
        if pid in existing_ids:
            continue

        rookie_end_year = int(player["rookie_season"])
        season_start_year = rookie_end_year - 1
        season_fmt = format_season(season_start_year)

        if season_fmt > CURRENT_SEASON:
            print(f"Skipping {player['player']} — season {season_fmt} not available yet")
            continue

        print(f"Fetching {player['player']} ({season_fmt})")

        try:
            stats = get_season_stats(season_fmt)

            row = stats[stats["PLAYER_ID"] == pid]
            if row.empty:
                continue

            row = row.iloc[0]

            minutes = float(row.get("MIN", 0))
            if minutes < MIN_MINUTES:
                continue
            if MAX_MINUTES and minutes > MAX_MINUTES:
                continue

            bio = with_retries(lambda: fetch_player_bio_raw(pid))

            snapshot = {
                "player_id": pid,
                "player": player["player"],
                "draft_year": player["draft_year"],
                "rookie_season": player["rookie_season"],

                "age": None,
                "height_in": bio["height_in"],
                "weight_lbs": bio["weight_lbs"],
                "position": bio["position"],

                "games": row.get("GP"),
                "minutes": row.get("MIN"),
                "mpg": row.get("MIN") / row.get("GP") if row.get("GP") else None,

                "usg_pct": row.get("USG_PCT"),

                "pts": row.get("PTS"),
                "reb": row.get("REB"),
                "ast": row.get("AST"),
                "stl": row.get("STL"),
                "blk": row.get("BLK"),
                "tov": row.get("TOV"),

                "fga": row.get("FGA"),
                "fgm": row.get("FGM"),
                "fg_pct": row.get("FG_PCT"),
                "fg3a": row.get("FG3A"),
                "fg3m": row.get("FG3M"),
                "fg3_pct": row.get("FG3_PCT"),
                "fta": row.get("FTA"),
                "ftm": row.get("FTM"),
                "ft_pct": row.get("FT_PCT"),
                "ftr": (row.get("FTA") / row.get("FGA")) if row.get("FGA") else None,

                "off_rating": row.get("OFF_RATING"),
                "def_rating": row.get("DEF_RATING"),
                "net_rating": row.get("NET_RATING"),
                "pace": row.get("PACE"),
                "bpm": row.get("BPM"),
                "vorp": row.get("VORP"),
            }

            rows.append(snapshot)

            # ---- Persist progress after each success ----
            pd.DataFrame(rows).to_csv(PROGRESS_PATH, index=False)

            time.sleep(SLEEP_BETWEEN_CALLS)

        except Exception as e:
            print(f"Failed for {player['player']}: {e}")
            continue

    return pd.DataFrame(rows)

# ------------------------
# Entrypoint
# ------------------------

if __name__ == "__main__":
    print("Loading draft_classes.csv…")
    draft_classes = pd.read_csv(DRAFT_CLASSES_PATH)

    print("Building name → NBA ID map…")
    name_to_nba = build_name_to_nba_id_map()

    print(f"Resolved NBA IDs for {sum(1 for _ in name_to_nba)} players")

    df = build_rookie_snapshot(draft_classes, name_to_nba)

    print(f"Saving {len(df)} rows to {OUTPUT_PATH}")
    df.to_csv(OUTPUT_PATH, index=False)
