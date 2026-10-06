from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pytest
from sklearn.linear_model import Ridge

from pair_fit_v2 import phase4a_production
from pair_fit_v2.inference import PairFitPredictor, validate_pair_card_seasons
from pair_fit_v2.phase4a_production import (
    FEATURES,
    MODEL_VERSION,
    ProductionError,
    build_production_package,
    build_profile_rows,
    load_production_population,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "production" / MODEL_VERSION


@pytest.fixture(scope="module")
def predictor() -> PairFitPredictor:
    return PairFitPredictor(ARTIFACTS)


def _season(start: int) -> str:
    return f"{start}-{str(start + 1)[2:]}"


def _find_lookback(predictor: PairFitPredictor, target_start: int, wanted_gap: int) -> str:
    seasons_by_player: dict[str, set[str]] = {}
    for season, player_id in predictor.profiles:
        seasons_by_player.setdefault(player_id, set()).add(season)
    for player_id, seasons in seasons_by_player.items():
        if _season(target_start - wanted_gap) not in seasons:
            continue
        if all(_season(target_start - gap) not in seasons for gap in range(1, wanted_gap)):
            return player_id
    raise AssertionError(f"no player found with {wanted_gap}-season lookback")


def test_production_population_and_frozen_feature_contract() -> None:
    rows, diagnostics = load_production_population(ROOT)
    assert len(rows) == diagnostics["unique_observation_keys"] == 32_512
    assert len(FEATURES) == len(set(FEATURES)) == 45
    assert diagnostics["season_counts"]["2025-26"] == 2_811
    excluded = {
        ("2024-25", "1610612766"), ("2024-25", "1610612755"),
        ("2025-26", "1610612754"), ("2025-26", "1610612763"),
    }
    assert not {(row["target_season"], row["team_id"]) for row in rows} & excluded
    assert all(float(row["pair_possessions"]) >= 150 for row in rows)
    assert all("recover" not in (row.get("raw_pair_base_path", "") + row.get("raw_pair_advanced_path", "")).lower() for row in rows[:29_701])
    assert all(row["direct_full_season_source"] == "1" and row["recovered_or_window_source"] == "0" for row in rows[29_701:])


def test_transparent_bundle_and_full_matrix_parity_record() -> None:
    model = json.loads((ARTIFACTS / "model.json").read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    metadata = json.loads((ARTIFACTS / "metadata.json").read_text(encoding="utf-8"))
    assert model["estimator"] == {
        "alpha": 3000.0, "calibrator": None, "ensemble": None,
        "fit_count": 1, "type": "sklearn.linear_model.Ridge",
    }
    assert model["ordered_feature_names"] == list(FEATURES)
    assert len(model["coefficients"]) == 45
    assert all(math.isfinite(value) for value in model["coefficients"] + [model["intercept"]])
    assert metadata["parity"]["rows"] == 32_512
    assert metadata["parity"]["maximum_absolute_error"] <= metadata["parity"]["predeclared_absolute_tolerance"] == 1e-10
    assert metadata["preprocessing"]["learned_from_rows"] == 32_512
    assert metadata["preprocessing"]["scaled_exactly_once"] is True
    assert metadata["fit"]["fit_count"] == 1
    assert not any(path.suffix in {".pkl", ".joblib"} for path in ARTIFACTS.iterdir())


def test_frozen_fit_and_public_fsum_parity() -> None:
    rows, _ = load_production_population(ROOT)
    scaled, preprocessing, _ = phase4a_production._build_matrix(rows)
    target = np.asarray([float(row["target_net_rating"]) for row in rows], dtype=np.float64)
    fitted = Ridge(alpha=3000.0).fit(scaled, target)
    model = json.loads((ARTIFACTS / "model.json").read_text(encoding="utf-8"))
    coefficients = np.asarray(model["coefficients"], dtype=np.float64)
    intercept = float(model["intercept"])
    assert preprocessing["unique_training_player_season_profiles"] == 4_667
    assert intercept == float(fitted.intercept_) == -1.3521345964567502
    assert np.array_equal(coefficients, np.asarray(fitted.coef_, dtype=np.float64))
    vectorized = scaled @ coefficients + intercept
    assert float(np.max(np.abs(fitted.predict(scaled) - vectorized))) == 0.0
    public_arithmetic = np.asarray([
        intercept + math.fsum(coefficient * value for coefficient, value in zip(coefficients, row))
        for row in scaled
    ])
    public_max_error = float(np.max(np.abs(vectorized - public_arithmetic)))
    assert public_max_error == pytest.approx(1.4210854715202004e-14)
    assert public_max_error <= 1e-10


def test_profile_bundle_identity_determinism_and_safe_fields() -> None:
    rows, diagnostics = build_profile_rows(ROOT)
    assert len(rows) == diagnostics["rows"] == 6_942
    assert list(diagnostics["season_counts"]) == [_season(year) for year in range(2013, 2026)]
    keys = [(row["source_season"], row["player_id"]) for row in rows]
    assert len(keys) == len(set(keys))
    with (ARTIFACTS / "player_profiles.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        forbidden = {"target_net_rating", "pair_possessions", "pair_minutes", "prediction", "team_id", "shot_zone"}
        assert not any(any(token in column.lower() for token in forbidden) for column in reader.fieldnames)
        bundled = list(reader)
    assert len(bundled) == 6_942
    assert all(row["source_per100_sha256"] and row["source_totals_sha256"] for row in bundled)


def test_support_refusals_and_cross_season_contract(predictor: PairFitPredictor) -> None:
    assert predictor.predict_pair_fit(1, 1, "2026-27")["refusal_reasons"][0]["code"] == "same_player"
    assert predictor.predict_pair_fit(1, 2, "2013-14")["refusal_reasons"][0]["code"] == "target_season_before_supported_range"
    assert predictor.predict_pair_fit(1, 2, "2027-28")["refusal_reasons"][0]["code"] == "target_season_after_supported_range"
    assert predictor.predict_pair_fit(1, 2, "2026/27")["refusal_reasons"][0]["code"] == "invalid_input"
    assert validate_pair_card_seasons("2025-26", "2026-27")["refusal_reasons"][0]["code"] == "cross_season_pair"
    assert validate_pair_card_seasons("2026-27", "2026-27")["supported"] is True


def test_history_lookbacks_confidence_rounding_and_no_legacy_outputs(predictor: PairFitPredictor) -> None:
    target_start = 2026
    players = [_find_lookback(predictor, target_start, gap) for gap in (1, 2, 3)]
    for wanted_gap, player_id in enumerate(players, start=1):
        other = players[0] if player_id != players[0] else players[1]
        result = predictor.predict_pair_fit(player_id, other, "2026-27")
        assert result["supported"] is True
        assert result["history"]["players"][player_id]["lookback_seasons"] == wanted_gap
        assert result["confidence"] == "standard"
        assert result["prediction_display"] == f"{result['prediction_display_whole']:+d}"
        assert result["final_test_mae_disclosure"] == "Typical final-test error: approximately 7.8 points per 100 possessions."
        prohibited = {"confidence_score", "fit_score", "top_drivers", "risk_flags", "primary_handler", "sliders"}
        assert not prohibited & set(result)
    one_missing = predictor.predict_pair_fit(players[0], 99_999_991, "2026-27")
    both_missing = predictor.predict_pair_fit(99_999_991, 99_999_992, "2026-27")
    assert one_missing["confidence"] == both_missing["confidence"] == "lower"
    assert one_missing["history"]["either_missing"] is both_missing["history"]["either_missing"] is True
    assert "confidence_score" not in one_missing and "confidence_score" not in both_missing


def test_swap_invariance_and_equal_valued_missing_features(predictor: PairFitPredictor) -> None:
    complete_ids = sorted({player_id for season, player_id in predictor.profiles if season == "2025-26"}, key=int)[:2]
    for left, right in ((complete_ids[0], complete_ids[1]), (complete_ids[0], "99999991"), ("99999991", "99999992")):
        forward = predictor.predict_pair_fit(left, right, "2026-27")
        reverse = predictor.predict_pair_fit(right, left, "2026-27")
        assert forward == reverse
        assert math.isfinite(forward["prediction_full_precision"])


def test_traded_profile_inference(predictor: PairFitPredictor) -> None:
    traded = next(row for (season, _), row in predictor.profiles.items() if season == "2025-26" and row["traded_player_indicator"] == 1.0)
    other = next(row for (season, _), row in predictor.profiles.items() if season == "2025-26" and row["player_id"] != traded["player_id"])
    result = predictor.predict_pair_fit(traded["player_id"], other["player_id"], "2026-27")
    assert result["supported"] is True
    assert result["confidence"] == "standard"


def test_manifest_nonrecursive_coverage_and_hashes() -> None:
    manifest = json.loads((ARTIFACTS / "artifact_manifest.json").read_text(encoding="utf-8"))
    actual = {path.name for path in ARTIFACTS.iterdir() if path.is_file() and path.name != "artifact_manifest.json"}
    assert actual == set(manifest["files"])
    for name, identity in manifest["files"].items():
        body = (ARTIFACTS / name).read_bytes()
        assert len(body) == identity["bytes"]
        assert hashlib.sha256(body).hexdigest() == identity["sha256"]


def _destination_fingerprint(path: Path) -> dict[str, tuple[str, int, str | None, int]]:
    fingerprint: dict[str, tuple[str, int, str | None, int]] = {}
    for entry in sorted(path.rglob("*")):
        relative = entry.relative_to(path).as_posix()
        stat = entry.stat()
        if entry.is_file():
            body = entry.read_bytes()
            fingerprint[relative] = ("file", len(body), hashlib.sha256(body).hexdigest(), stat.st_mtime_ns)
        else:
            fingerprint[relative] = ("directory", 0, None, stat.st_mtime_ns)
    return fingerprint


def _copy_artifact(destination: Path, name: str) -> None:
    shutil.copyfile(ARTIFACTS / name, destination / name)


@pytest.mark.parametrize(
    "scenario",
    (
        "unexpected_file",
        "conflicting_profile_only",
        "matching_first_missing_later",
        "matching_and_conflicting",
        "complete_plus_extra",
        "unexpected_subdirectory",
        "first_output_absent",
    ),
)
def test_populated_destination_refuses_without_mutation(tmp_path: Path, scenario: str) -> None:
    output = tmp_path / "package"
    output.mkdir()
    if scenario == "unexpected_file":
        (output / "unexpected.txt").write_bytes(b"unexpected")
    elif scenario == "conflicting_profile_only":
        (output / "player_profiles.csv").write_bytes(b"conflicting")
    elif scenario == "matching_first_missing_later":
        _copy_artifact(output, "model.json")
    elif scenario == "matching_and_conflicting":
        _copy_artifact(output, "model.json")
        (output / "player_profiles.csv").write_bytes(b"conflicting")
    elif scenario == "complete_plus_extra":
        for source in ARTIFACTS.iterdir():
            _copy_artifact(output, source.name)
        (output / "unexpected.txt").write_bytes(b"unexpected")
    elif scenario == "unexpected_subdirectory":
        nested = output / "stale-publication"
        nested.mkdir()
        (nested / "temporary.json").write_bytes(b"stale")
    elif scenario == "first_output_absent":
        _copy_artifact(output, "metadata.json")
    before = _destination_fingerprint(output)
    with pytest.raises(ProductionError, match="absent or completely empty"):
        build_production_package(ROOT, output)
    assert _destination_fingerprint(output) == before


def test_completed_official_destination_refuses_without_mutation() -> None:
    before = _destination_fingerprint(ARTIFACTS)
    with pytest.raises(ProductionError, match="absent or completely empty"):
        build_production_package(ROOT, ARTIFACTS)
    assert _destination_fingerprint(ARTIFACTS) == before


def test_destination_preflight_precedes_fit_and_serialization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "package"
    output.mkdir()
    (output / ".stale-publication").write_bytes(b"stale")
    reached_fit_inputs = False

    def fail_if_called(project_root: Path) -> tuple[list[dict[str, str]], dict[str, object]]:
        nonlocal reached_fit_inputs
        reached_fit_inputs = True
        raise AssertionError(f"fit inputs reached for {project_root}")

    monkeypatch.setattr(phase4a_production, "load_production_population", fail_if_called)
    before = _destination_fingerprint(output)
    with pytest.raises(ProductionError, match=".stale-publication"):
        build_production_package(ROOT, output)
    assert reached_fit_inputs is False
    assert _destination_fingerprint(output) == before
