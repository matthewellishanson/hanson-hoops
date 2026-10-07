from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from preview_research.datasets import DATASETS
from preview_research.storage import ResearchStore
from preview_research.transform import build_shooting, process_nba_payload


def test_build_shooting_recalculates_percentages_from_counts(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path)
    base = pd.DataFrame({
        "PLAYER_ID": ["1"], "PLAYER_NAME": ["A"], "GP": [10], "MIN": [200],
        "FGM": [50], "FGA": [100], "FG_PCT": [0.999], "FG3M": [20], "FG3A": [50],
        "FG3_PCT": [0.999], "FTM": [10], "FTA": [20], "FT_PCT": [0.999], "PTS": [130],
        "SEASON": ["2025-26"], "SEASON_TYPE": ["Regular Season"],
    })
    advanced = pd.DataFrame({"PLAYER_ID": ["1"], "EFG_PCT": [0.6], "TS_PCT": [0.59]})
    metadata = {"retrieved_at": "2026-10-01T00:00:00Z", "raw_sha256": "abc"}
    store.write_processed(store.paths("player_base_totals", "2025-26", "Regular Season"), base, metadata)
    store.write_processed(store.paths("player_advanced", "2025-26", "Regular Season"), advanced, metadata)
    shooting, _ = build_shooting("player", "2025-26", "Regular Season", store=store)
    assert shooting.loc[0, "CALC_FG_PCT"] == pytest.approx(0.5)
    assert shooting.loc[0, "CALC_FG3_PCT"] == pytest.approx(0.4)
    assert shooting.loc[0, "CALC_FG2_PCT"] == pytest.approx(0.6)
    assert shooting.loc[0, "CALC_EFG_PCT"] == pytest.approx(0.6)


def test_on_off_preserves_state_and_team_grain(tmp_path: Path) -> None:
    rows_on = []
    rows_off = []
    headers = [
        "GROUP_SET", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "VS_PLAYER_ID",
        "VS_PLAYER_NAME", "COURT_STATUS", "GP", "MIN", "PLUS_MINUS",
        "OFF_RATING", "DEF_RATING", "NET_RATING",
    ]
    for index in range(10):
        common = ["Players", 1610612700, "TST", "Test", 100 + index, f"Player {index}"]
        rows_on.append(common + ["On", 10, 100, 2, 115, 110, 5])
        rows_off.append(common + ["Off", 10, 200, -2, 108, 112, -4])
    payload = {"resultSets": [
        {"name": "PlayersOnCourtTeamPlayerOnOffSummary", "headers": headers, "rowSet": rows_on},
        {"name": "PlayersOffCourtTeamPlayerOnOffSummary", "headers": headers, "rowSet": rows_off},
    ]}
    store = ResearchStore(tmp_path)
    frame, metadata = process_nba_payload(
        payload, DATASETS["player_on_off"], "2025-26", "Regular Season",
        team_id="1610612700", store=store,
        raw_metadata={"retrieved_at": "2026-10-01T00:00:00Z", "raw_sha256": "abc"},
    )
    assert set(frame["ON_OFF"]) == {"on", "off"}
    assert not frame.duplicated(["TEAM_ID", "VS_PLAYER_ID", "ON_OFF"]).any()
    assert metadata["row_grain"] == "player x team x season x on/off state"

