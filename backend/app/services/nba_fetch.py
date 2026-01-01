# app/services/nba_fetch.py
from nba_api.stats.endpoints import commonplayerinfo

def fetch_player_bio_raw(player_id: int, timeout=60):
    frames = commonplayerinfo.CommonPlayerInfo(
        player_id=player_id,
        timeout=timeout
    ).get_data_frames()

    if not frames or frames[0].empty:
        return None

    return frames[0].iloc[0]
