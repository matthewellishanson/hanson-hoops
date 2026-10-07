from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from preview_research.query import (
    QueryResult,
    compare_entity,
    export_result,
    filter_rows,
    join_compatible,
    load_dataset,
    year_over_year,
)
from preview_research.storage import ResearchStore


def result(frame: pd.DataFrame, dataset: str = "sample") -> QueryResult:
    return QueryResult(frame, dataset, ("2024-25", "2025-26"), "Regular Season", [{"source": "fixture"}])


def test_multiple_numeric_conditions_sort_and_limit() -> None:
    frame = pd.DataFrame({"PLAYER_ID": ["1", "2", "3"], "MIN": [900, 1200, 1300], "FG3A": [200, 199, 300], "FG3_PCT": [0.36, 0.40, 0.39]})
    selected = filter_rows(result(frame), conditions=["MIN>=1000", "FG3A>=200"], sort_by="FG3_PCT", descending=True, limit=1)
    assert selected.frame["PLAYER_ID"].tolist() == ["3"]


def test_join_requires_unique_compatible_grain() -> None:
    left = result(pd.DataFrame({"PLAYER_ID": ["1", "1"], "SEASON": ["2024-25", "2024-25"], "PTS": [1, 2]}), "left")
    right = result(pd.DataFrame({"PLAYER_ID": ["1"], "SEASON": ["2024-25"], "TS_PCT": [0.6]}), "right")
    with pytest.raises(ValueError, match="left table is not unique"):
        join_compatible(left, right, keys=["PLAYER_ID", "SEASON"])


def test_default_player_join_does_not_infer_stint_from_team_id() -> None:
    left = result(pd.DataFrame({
        "PLAYER_ID": ["1"], "TEAM_ID": ["10"], "SEASON": ["2024-25"],
        "SEASON_TYPE": ["Regular Season"], "PTS": [100],
    }), "left")
    right = result(pd.DataFrame({
        "PLAYER_ID": ["1"], "TEAM_ID": ["20"], "SEASON": ["2024-25"],
        "SEASON_TYPE": ["Regular Season"], "TS_PCT": [0.6],
    }), "right")
    joined = join_compatible(left, right)
    assert len(joined.frame) == 1
    assert joined.frame.loc[0, "TEAM_ID_LEFT"] == "10"
    assert joined.frame.loc[0, "TEAM_ID_RIGHT"] == "20"


def test_compare_and_yoy_use_stable_ids_and_explicit_seasons() -> None:
    frame = pd.DataFrame({
        "PLAYER_ID": ["1", "1", "2", "2"],
        "PLAYER_NAME": ["A", "A", "B", "B"],
        "SEASON": ["2024-25", "2025-26", "2024-25", "2025-26"],
        "SEASON_TYPE": ["Regular Season"] * 4,
        "PTS": [20.0, 23.0, 10.0, 9.0],
    })
    compared = compare_entity(result(frame), "1", metrics=["PTS"])
    assert compared.frame["PTS"].tolist() == [20.0, 23.0]
    changed = year_over_year(result(frame), "PTS")
    assert changed.frame.loc[changed.frame["PLAYER_ID"].eq("1"), "CHANGE_PTS"].iloc[-1] == 3.0


def test_cached_load_is_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ResearchStore(tmp_path)
    paths = store.paths("sample", "2025-26", "Regular Season")
    frame = pd.DataFrame({"PLAYER_ID": ["1"], "SEASON": ["2025-26"], "PTS": [10]})
    metadata = {"dataset": "sample", "season": "2025-26", "season_type": "Regular Season", "validation_status": "structurally_checked"}
    store.write_processed(paths, frame, metadata)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network must not be used by cached queries")

    monkeypatch.setattr("requests.Session.get", forbidden)
    loaded = load_dataset("sample", ["2025-26"], store=store)
    assert loaded.frame["PTS"].tolist() == [10]


def test_export_writes_exact_rows_and_companion_note(tmp_path: Path) -> None:
    selected = result(pd.DataFrame({"PLAYER_ID": ["1"], "TS_PCT": [0.61]}))
    csv_path, note_path = export_result(selected, tmp_path / "chart.csv", notes="Figure 1")
    assert pd.read_csv(csv_path).shape == (1, 2)
    note = note_path.read_text(encoding="utf-8")
    assert "fraction from 0 to 1" in note
    assert "Figure 1" in note


def test_export_rejects_infinite_values(tmp_path: Path) -> None:
    selected = result(pd.DataFrame({"PLAYER_ID": ["1"], "VALUE": [np.inf]}))
    with pytest.raises(ValueError, match="infinite"):
        export_result(selected, tmp_path / "bad.csv")
