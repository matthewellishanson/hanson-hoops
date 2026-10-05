from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import pair_fit_v2_service


KNOWN_A = "2544"
KNOWN_B = "203932"
TARGET_SEASON = "2026-27"


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_package_path_is_cwd_independent(monkeypatch, tmp_path):
    expected = (
        Path(__file__).resolve().parents[2]
        / "research"
        / "pair-fit-v2"
        / "production"
        / "pair-fit-v2.0.0"
    ).resolve()
    monkeypatch.chdir(tmp_path)
    assert pair_fit_v2_service.production_package_path().resolve() == expected
    assert pair_fit_v2_service.verify_production_package()["model_version"] == "pair-fit-v2.0.0"


def test_package_verification_rejects_missing_and_corrupted_files(tmp_path):
    source = pair_fit_v2_service.production_package_path()

    missing = tmp_path / "missing"
    shutil.copytree(source, missing)
    (missing / "metadata.json").unlink()
    with pytest.raises(pair_fit_v2_service.PairFitPackageError, match="inventory mismatch"):
        pair_fit_v2_service.verify_production_package(missing)

    corrupted = tmp_path / "corrupted"
    shutil.copytree(source, corrupted)
    with (corrupted / "model.json").open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(pair_fit_v2_service.PairFitPackageError, match="hash mismatch for model.json"):
        pair_fit_v2_service.verify_production_package(corrupted)


def test_predictor_loads_once_across_requests():
    pair_fit_v2_service._reset_predictor_for_tests()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        first = test_client.get(f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season={TARGET_SEASON}")
        second = test_client.get(f"/fit/v2/pair/{KNOWN_B}/{KNOWN_A}?target_season={TARGET_SEASON}")
    assert first.status_code == second.status_code == 200
    assert pair_fit_v2_service.predictor_load_count() == 1


def test_supported_response_matches_direct_audited_inference(client):
    predictor = pair_fit_v2_service.get_pair_fit_predictor()
    direct = predictor.predict_pair_fit(KNOWN_A, KNOWN_B, TARGET_SEASON)
    response = client.get(f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season={TARGET_SEASON}")
    assert response.status_code == 200
    body = response.json()

    assert body == {
        "supported": True,
        "model_name": "Pair Fit v2",
        "model_version": "pair-fit-v2.0.0",
        "output_definition": "projected shared-court team NET_RATING",
        "units": "points per 100 possessions",
        "player_a_id": KNOWN_A,
        "player_b_id": KNOWN_B,
        "target_season": TARGET_SEASON,
        "projected_net_rating": direct["prediction_full_precision"],
        "display_value": direct["prediction_display"],
        "confidence": direct["confidence"],
        "confidence_meaning": "history completeness, not probability",
        "player_a_profile_season": direct["history"]["players"][KNOWN_A]["selected_profile_season"],
        "player_b_profile_season": direct["history"]["players"][KNOWN_B]["selected_profile_season"],
        "player_a_history_missing": direct["history"]["players"][KNOWN_A]["missing"],
        "player_b_history_missing": direct["history"]["players"][KNOWN_B]["missing"],
        "typical_final_test_error": predictor.model["final_test"]["mae"],
        "error_disclosure": predictor.model["final_test"]["public_disclosure"],
    }
    assert body["confidence"] == "standard"


def test_swapped_player_order_has_identical_result(client):
    forward = client.get(
        f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season={TARGET_SEASON}"
    ).json()
    reverse = client.get(
        f"/fit/v2/pair/{KNOWN_B}/{KNOWN_A}?target_season={TARGET_SEASON}"
    ).json()
    assert forward["projected_net_rating"] == reverse["projected_net_rating"]
    assert forward["display_value"] == reverse["display_value"]
    assert forward["confidence"] == reverse["confidence"]


@pytest.mark.parametrize(
    ("player_a", "player_b", "expected_missing"),
    [
        (KNOWN_A, "999999999", (False, True)),
        ("999999998", "999999999", (True, True)),
    ],
)
def test_missing_history_remains_supported_with_lower_confidence(
    client, player_a, player_b, expected_missing
):
    response = client.get(
        f"/fit/v2/pair/{player_a}/{player_b}?target_season={TARGET_SEASON}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is True
    assert body["confidence"] == "lower"
    assert (
        body["player_a_history_missing"],
        body["player_b_history_missing"],
    ) == expected_missing


@pytest.mark.parametrize(
    ("path", "status", "reason_code"),
    [
        (f"/fit/v2/pair/{KNOWN_A}/{KNOWN_A}?target_season={TARGET_SEASON}", 400, "same_player"),
        (f"/fit/v2/pair/not-an-id/{KNOWN_B}?target_season={TARGET_SEASON}", 422, "invalid_input"),
        (f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season=2026", 422, "invalid_input"),
        (f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season=2013-14", 422, "target_season_before_supported_range"),
        (f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season=2027-28", 422, "target_season_after_supported_range"),
    ],
)
def test_structured_refusals_have_no_prediction(client, path, status, reason_code):
    response = client.get(path)
    assert response.status_code == status
    body = response.json()
    assert body["supported"] is False
    assert body["reason_code"] == reason_code
    assert isinstance(body["message"], str) and body["message"]
    assert "projected_net_rating" not in body
    assert "display_value" not in body


def test_v2_schema_has_no_legacy_fit_concepts(client):
    body = client.get(
        f"/fit/v2/pair/{KNOWN_A}/{KNOWN_B}?target_season={TARGET_SEASON}"
    ).json()
    legacy_fields = {
        "fit_score",
        "drivers_positive",
        "risks",
        "pair_components",
        "axes",
        "primary_handler",
        "weight_version",
    }
    assert legacy_fields.isdisjoint(body)


def test_legacy_pair_endpoint_remains_operational(client):
    response = client.get("/fit/pair/2544/203932?season=2023-24&min_minutes=300")
    assert response.status_code == 200
    assert response.json()["model_version"] == "fit-v1.0.0"
