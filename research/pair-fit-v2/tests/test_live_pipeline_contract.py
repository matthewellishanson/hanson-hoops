from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.live_fetch import format_pair_key, parse_group_players, summarize_lineup_df


def test_parse_group_players_handles_lineup_tokens():
    assert parse_group_players("LeBron James - Anthony Davis") == ["LeBron James", "Anthony Davis"]
    assert parse_group_players("Player 101 - Player 204") == ["Player 101", "Player 204"]
    assert parse_group_players("") == []


def test_format_pair_key_requires_two_players():
    assert format_pair_key(["204", "101"]) == ("101", "204")
    try:
        format_pair_key(["101"])  # should fail
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass


def test_summarize_lineup_df_detects_zero_minutes_and_pair_issues():
    df = pd.DataFrame(
        [
            {"GROUP_ID": "a", "GROUP_NAME": "Player 1 - Player 2", "MIN": 100.0, "ORTG": 110.0, "DRTG": 108.0},
            {"GROUP_ID": "b", "GROUP_NAME": "Player 3", "MIN": 0.0, "ORTG": None, "DRTG": None},
            {"GROUP_ID": "a", "GROUP_NAME": "Player 1 - Player 2", "MIN": 100.0, "ORTG": 110.0, "DRTG": 108.0},
        ]
    )
    summary = summarize_lineup_df(df)
    assert summary["row_count"] == 3
    assert summary["duplicate_group_ids"] == 1
    assert summary["zero_minute_rows"] == 1
    assert summary["malformed_pair_names"] == 1
    assert summary["valid_target_rows"] == 1
