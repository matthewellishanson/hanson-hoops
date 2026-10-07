from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from preview_research.datasets import DATASETS
from preview_research.validation import (
    ValidationError,
    combined_percentage,
    safe_percentage,
    validate_dataset,
    validate_general,
)


def test_combined_percentage_uses_summed_makes_and_attempts() -> None:
    frame = pd.DataFrame({"FGM": [1, 9], "FGA": [2, 30], "FG_PCT": [0.5, 0.3]})
    assert combined_percentage(frame, "FGM", "FGA") == pytest.approx(10 / 32)
    assert combined_percentage(frame, "FGM", "FGA") != pytest.approx(frame["FG_PCT"].mean())


def test_safe_percentage_preserves_missing_and_zero_attempts() -> None:
    result = safe_percentage(pd.Series([1, 0, np.nan]), pd.Series([2, 0, 4]))
    assert result.iloc[0] == pytest.approx(0.5)
    assert math.isnan(result.iloc[1])
    assert math.isnan(result.iloc[2])


def test_duplicate_grain_is_rejected() -> None:
    frame = pd.DataFrame({"PLAYER_ID": ["1", "1"], "FG_PCT": [0.4, 0.5]})
    with pytest.raises(ValidationError, match="Duplicate row grain"):
        validate_general(frame, ["PLAYER_ID"])


def test_team_stints_remain_distinct_when_team_is_in_key() -> None:
    frame = pd.DataFrame({
        "PLAYER_ID": ["1", "1", "1"],
        "TEAM_ID": ["10", "20", "0"],
        "ROW_SCOPE": ["team_stint", "team_stint", "combined"],
        "PTS": [100, 200, 300],
    })
    report = validate_general(frame, ["PLAYER_ID", "TEAM_ID", "ROW_SCOPE"])
    assert report.status == "structurally_checked"
    with pytest.raises(ValidationError, match="Duplicate row grain"):
        validate_general(frame, ["PLAYER_ID"])


def test_percentage_points_are_not_accepted_as_fractions() -> None:
    frame = pd.DataFrame({"PLAYER_ID": ["1"], "FG_PCT": [47.5]})
    with pytest.raises(ValidationError, match="fraction units"):
        validate_general(frame, ["PLAYER_ID"])


def test_infinite_values_rejected_but_nan_is_preserved() -> None:
    okay = pd.DataFrame({"PLAYER_ID": ["1", "2"], "PTS": [np.nan, 2.0]})
    assert validate_general(okay, ["PLAYER_ID"]).status == "structurally_checked"
    bad = pd.DataFrame({"PLAYER_ID": ["1"], "PTS": [np.inf]})
    with pytest.raises(ValidationError, match="Infinite"):
        validate_general(bad, ["PLAYER_ID"])


def test_expected_population_is_not_just_nonempty() -> None:
    spec = DATASETS["team_base_totals"]
    row = {column: 1 for column in spec.required_columns}
    row.update({"TEAM_ID": "1", "TEAM_NAME": "Example", "FG_PCT": 0.5, "FG3_PCT": 0.4, "FT_PCT": 0.8})
    with pytest.raises(ValidationError, match="Unexpected team_base_totals population"):
        validate_dataset(pd.DataFrame([row]), spec)
