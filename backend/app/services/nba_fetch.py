# app/services/nba_fetch.py
from nba_api.stats.endpoints import commonplayerinfo

from app.services.nba_http import nba_call, request_timeout_seconds

def fetch_player_bio_raw(player_id: int, timeout=None):
    frames = nba_call(
        "common_player_info_service",
        lambda: commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=timeout or request_timeout_seconds(),
        ).get_data_frames(),
    )

    if not frames or frames[0].empty:
        return None

    return frames[0].iloc[0]
