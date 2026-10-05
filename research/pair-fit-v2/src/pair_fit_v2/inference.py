"""Pure transparent-bundle inference for Pair Fit v2.

This module intentionally does not import sklearn and never unpickles an
estimator. It reads deterministic JSON/CSV artifacts and evaluates the Ridge
dot product directly.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping


MODEL_VERSION = "pair-fit-v2.0.0"
DIRECT_FIELDS = (
    "AGE", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
)
DERIVED_FIELDS = (
    "effective_field_goal_pct", "true_shooting_pct", "three_point_attempt_rate",
    "free_throw_rate",
)
PLAYER_FIELDS = DIRECT_FIELDS + DERIVED_FIELDS
DISCLOSURE = "Typical final-test error: approximately 7.8 points per 100 possessions."


class InferenceContractError(ValueError):
    """Raised when production artifact content violates the frozen contract."""


def _strict_json(path: Path) -> Any:
    def reject(token: str) -> None:
        raise InferenceContractError(f"nonfinite JSON token: {token}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def _season_start(value: str) -> int:
    try:
        first, second = value.split("-")
        start = int(first)
        if len(first) != 4 or len(second) != 2 or int(second) != (start + 1) % 100:
            raise ValueError
        return start
    except (AttributeError, TypeError, ValueError):
        raise InferenceContractError(f"invalid target-season format: {value!r}") from None


def _player_id(value: Any) -> str:
    if isinstance(value, bool):
        raise InferenceContractError("player ID must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise InferenceContractError("player ID must be a positive integer") from None
    if number <= 0 or str(number) != str(value).strip():
        raise InferenceContractError("player ID must be a positive integer")
    return str(number)


def _round_half_away_from_zero(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def validate_pair_card_seasons(player_a_target_season: str, player_b_target_season: str) -> dict[str, Any]:
    """Product-layer guard for two comparison cards before model inference."""
    try:
        _season_start(player_a_target_season)
        _season_start(player_b_target_season)
    except InferenceContractError as exc:
        return {"supported": False, "refusal_reasons": [{"code": "invalid_target_season", "message": str(exc)}]}
    if player_a_target_season != player_b_target_season:
        return {"supported": False, "refusal_reasons": [{"code": "cross_season_pair", "message": "Pair Fit requires both cards to use one common target season."}]}
    return {"supported": True, "target_season": player_a_target_season, "refusal_reasons": []}


class PairFitPredictor:
    """Load-once predictor backed only by the transparent production bundle."""

    def __init__(self, artifact_dir: Path):
        self.artifact_dir = Path(artifact_dir)
        self.model = _strict_json(self.artifact_dir / "model.json")
        if self.model.get("model_version") != MODEL_VERSION:
            raise InferenceContractError("model version mismatch")
        names = self.model.get("ordered_feature_names")
        coefficients = self.model.get("coefficients")
        if not isinstance(names, list) or len(names) != 45 or len(set(names)) != 45:
            raise InferenceContractError("feature manifest must contain 45 unique ordered names")
        if not isinstance(coefficients, list) or len(coefficients) != 45:
            raise InferenceContractError("coefficient count mismatch")
        self.names = tuple(names)
        self.coefficients = tuple(float(value) for value in coefficients)
        self.intercept = float(self.model["intercept"])
        prep = self.model["preprocessing"]
        self.medians = {key: float(value) for key, value in prep["player_slot_medians"].items()}
        self.fills = {key: float(value) for key, value in prep["symmetric_feature_fill_values"].items()}
        self.means = {key: float(value) for key, value in prep["scaler_means"].items()}
        self.scales = {key: float(value) for key, value in prep["scaler_scales"].items()}
        all_numbers = (*self.coefficients, self.intercept, *self.medians.values(), *self.fills.values(), *self.means.values(), *self.scales.values())
        if not all(math.isfinite(value) for value in all_numbers) or any(value <= 0 for value in self.scales.values()):
            raise InferenceContractError("bundle contains invalid numeric state")
        self.profiles: dict[tuple[str, str], dict[str, Any]] = {}
        with (self.artifact_dir / "player_profiles.csv").open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (row["source_season"], row["player_id"])
                if key in self.profiles:
                    raise InferenceContractError(f"duplicate player-season profile: {key}")
                parsed = dict(row)
                for field in (*[name.lower() for name in DIRECT_FIELDS], *DERIVED_FIELDS, "traded_player_indicator", "gp", "total_min"):
                    parsed[field] = None if row[field] == "" else float(row[field])
                self.profiles[key] = parsed

    def _select_profile(self, player_id: str, target_start: int) -> tuple[str | None, int | None, Mapping[str, Any] | None]:
        for gap in (1, 2, 3):
            start = target_start - gap
            season = f"{start}-{str(start + 1)[2:]}"
            profile = self.profiles.get((season, player_id))
            if profile is not None:
                return season, gap, profile
        return None, None, None

    def _slot(self, profile: Mapping[str, Any] | None) -> dict[str, float]:
        values: dict[str, float] = {}
        for field in PLAYER_FIELDS:
            key = field.lower()
            value = None if profile is None else profile.get(key)
            values[field] = self.medians[key] if value is None else float(value)
        traded = None if profile is None else profile.get("traded_player_indicator")
        values["traded_player_indicator"] = self.medians["traded_player_indicator"] if traded is None else float(traded)
        return values

    def _features(self, left: Mapping[str, float], right: Mapping[str, float]) -> list[float]:
        values: dict[str, float] = {}
        for field in PLAYER_FIELDS:
            values[f"pair_mean.{field}"] = (left[field] + right[field]) / 2.0
            values[f"pair_absolute_difference.{field}"] = abs(left[field] - right[field])
        values["pair_traded_history_count"] = left["traded_player_indicator"] + right["traded_player_indicator"]
        result = []
        for name in self.names:
            value = values.get(name)
            if value is None or not math.isfinite(value):
                value = self.fills[name]
            result.append(float(value))
        return result

    def predict_pair_fit(self, player_a_id: Any, player_b_id: Any, target_season: str) -> dict[str, Any]:
        """Return a symmetric prediction or a structured truthful refusal."""
        base = {
            "model_version": MODEL_VERSION, "target_season": target_season,
            "final_test_mae_disclosure": DISCLOSURE,
        }
        try:
            left_id, right_id = _player_id(player_a_id), _player_id(player_b_id)
            target_start = _season_start(target_season)
        except InferenceContractError as exc:
            return {**base, "supported": False, "refusal_reasons": [{"code": "invalid_input", "message": str(exc)}]}
        if left_id == right_id:
            return {**base, "supported": False, "refusal_reasons": [{"code": "same_player", "message": "Pair Fit requires two different player IDs."}]}
        if target_start < 2014:
            return {**base, "supported": False, "refusal_reasons": [{"code": "target_season_before_supported_range", "message": "Pair Fit supports target seasons beginning with 2014-15."}]}
        if target_start > 2026:
            return {**base, "supported": False, "refusal_reasons": [{"code": "target_season_after_supported_range", "message": "Pair Fit currently supports target seasons through 2026-27."}]}
        left_season, left_gap, left_profile = self._select_profile(left_id, target_start)
        right_season, right_gap, right_profile = self._select_profile(right_id, target_start)
        left_missing, right_missing = left_profile is None, right_profile is None
        features = self._features(self._slot(left_profile), self._slot(right_profile))
        scaled = [(value - self.means[name]) / self.scales[name] for name, value in zip(self.names, features)]
        prediction = self.intercept + math.fsum(coefficient * value for coefficient, value in zip(self.coefficients, scaled))
        if not math.isfinite(prediction):
            raise InferenceContractError("prediction is nonfinite")
        return {
            **base, "supported": True, "refusal_reasons": [],
            "player_ids": sorted((left_id, right_id), key=int),
            "prediction_full_precision": prediction,
            "prediction_display_whole": _round_half_away_from_zero(prediction),
            "prediction_display": f"{_round_half_away_from_zero(prediction):+d}",
            "confidence": "lower" if left_missing or right_missing else "standard",
            "history": {
                "players": {
                    left_id: {"selected_profile_season": left_season, "lookback_seasons": left_gap, "missing": left_missing},
                    right_id: {"selected_profile_season": right_season, "lookback_seasons": right_gap, "missing": right_missing},
                },
                "either_missing": left_missing or right_missing,
            },
        }


_DEFAULT_PREDICTOR: PairFitPredictor | None = None


def predict_pair_fit(player_a_id: Any, player_b_id: Any, target_season: str, *, artifact_dir: Path | None = None) -> dict[str, Any]:
    """Narrow convenience interface; production callers should load once."""
    global _DEFAULT_PREDICTOR
    directory = artifact_dir or Path(__file__).resolve().parents[2] / "production" / MODEL_VERSION
    if _DEFAULT_PREDICTOR is None or _DEFAULT_PREDICTOR.artifact_dir.resolve() != Path(directory).resolve():
        _DEFAULT_PREDICTOR = PairFitPredictor(Path(directory))
    return _DEFAULT_PREDICTOR.predict_pair_fit(player_a_id, player_b_id, target_season)
