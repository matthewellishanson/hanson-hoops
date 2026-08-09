from __future__ import annotations

import logging

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from requests.exceptions import ProxyError, ReadTimeout

from app.api.endpoints import fit, players
from app.main import app
from app.services import nba_http
from app.services.nba_http import NBAUpstreamError

PAGES_ORIGIN = "https://matthewellishanson.github.io"
ORIGIN_HEADERS = {"Origin": PAGES_ORIGIN}


@app.get("/_tests/unexpected-error")
def _unexpected_error_fixture():
    raise RuntimeError("fixture unexpected failure")


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_health_success_has_pages_cors(client):
    response = client.get("/health", headers=ORIGIN_HEADERS)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.headers["x-request-id"]


def test_packaged_player_bio_is_real_and_labeled(client):
    players._BIO_CACHE.clear()
    response = client.get(
        "/player_bio?player_id=2544&season=2023-24", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["name"] == "LeBron James"
    assert response.json()["data_source"] == "packaged_snapshot"
    assert response.json()["height"] == "6-9"


def test_successful_mocked_player_bio(client, monkeypatch):
    player_id = "999001"
    players._BIO_CACHE.pop(player_id, None)
    monkeypatch.setattr(players, "load_player_snapshot", lambda _: None)

    class FakeCommonPlayerInfo:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] <= 30

        def get_data_frames(self):
            return [
                pd.DataFrame(
                    [
                        {
                            "DISPLAY_FIRST_LAST": "Fixture Player",
                            "TEAM_NAME": "Fixture Team",
                            "POSITION": "Guard",
                            "HEIGHT": "6-4",
                            "WEIGHT": "205",
                            "JERSEY": "7",
                            "BIRTHDATE": "1990-01-02T00:00:00",
                        }
                    ]
                )
            ]

    monkeypatch.setattr(players.commonplayerinfo, "CommonPlayerInfo", FakeCommonPlayerInfo)
    response = client.get(
        f"/player_bio?player_id={player_id}&season=2023-24", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Fixture Player"
    assert response.json()["data_source"] == "live"


def test_player_bio_timeout_is_structured_502_with_cors(client, monkeypatch):
    player_id = "999002"
    players._BIO_CACHE.pop(player_id, None)
    monkeypatch.setattr(players, "load_player_snapshot", lambda _: None)

    class TimeoutCommonPlayerInfo:
        def __init__(self, **kwargs):
            raise ReadTimeout("fixture timeout")

    monkeypatch.setattr(players.commonplayerinfo, "CommonPlayerInfo", TimeoutCommonPlayerInfo)
    response = client.get(
        f"/player_bio?player_id={player_id}&season=2023-24", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 502
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.headers["x-request-id"]
    assert response.json()["detail"]["code"] == "nba_upstream_unavailable"
    assert response.json()["detail"]["retryable"] is True


def test_profile_proxy_failure_is_not_zero_valued_200(client, monkeypatch):
    monkeypatch.setattr(players, "load_player_snapshot", lambda _: None)

    class FailedPlayerGameLog:
        def __init__(self, **kwargs):
            raise ProxyError("fixture proxy failure")

    monkeypatch.setattr(players.playergamelog, "PlayerGameLog", FailedPlayerGameLog)
    response = client.get(
        "/player_profile_stats?player_id=999003&season=2023-24&scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "nba_upstream_unavailable"
    assert "points" not in response.json()


def test_shot_timeout_is_structured_502(client, monkeypatch):
    players._player_shots_for_season.cache_clear()
    monkeypatch.setattr(players, "load_player_shot_snapshot", lambda *_args: (None, {}))

    class FailedShotChart:
        def __init__(self, **kwargs):
            raise ReadTimeout("fixture timeout")

    monkeypatch.setattr(players.shotchartdetail, "ShotChartDetail", FailedShotChart)
    response = client.get(
        "/player_shots?player_id=999004&season=2023-24", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 502
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.json()["detail"]["code"] == "nba_upstream_unavailable"


def test_added_player_uses_league_profile_and_bio_snapshots(client):
    players._BIO_CACHE.clear()
    bio = client.get(
        "/player_bio?player_id=1630162&season=2023-24", headers=ORIGIN_HEADERS
    )
    profile = client.get(
        "/player_profile_stats?player_id=1630162&season=2023-24&scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    assert bio.status_code == 200
    assert bio.json()["name"] == "Anthony Edwards"
    assert bio.json()["data_source"] == "packaged_snapshot"
    assert profile.status_code == 200
    assert profile.json()["raw_points"] == 25.9
    assert profile.json()["data_source"] == "packaged_snapshot"


def test_default_player_shots_use_packaged_snapshot_with_cors(client):
    response = client.get(
        "/player_shots?player_id=203932&season=2023-24", headers=ORIGIN_HEADERS
    )
    body = response.json()
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert body["data_source"] == "packaged_snapshot"
    assert body["attempts"] == 716
    assert body["makes"] == 398
    assert body["shots"][0]["shot_type"] in {"2PT Field Goal", "3PT Field Goal"}


def test_fit_table_upstream_failure_is_structured_502(client, monkeypatch):
    fit._feature_table.cache_clear()
    monkeypatch.setattr(
        fit,
        "player_pool",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(NBAUpstreamError("fixture_fit")),
    )
    response = client.get(
        "/fit/pair/2544/203932?season=2099-00&min_minutes=300", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 502
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.json()["detail"]["code"] == "nba_upstream_unavailable"


def test_unexpected_failure_is_structured_and_keeps_cors(client):
    response = client.get("/_tests/unexpected-error", headers=ORIGIN_HEADERS)
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.headers["x-request-id"]
    assert response.json()["detail"]["code"] == "internal_error"


def test_known_pair_uses_deterministic_packaged_snapshot(client):
    fit._feature_table.cache_clear()
    response = client.get(
        "/fit/pair/2544/203932?season=2023-24&min_minutes=300", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "packaged_snapshot"
    assert body["model_version"] == "fit-v1.0.0"
    assert body["player_a"]["name"] == "LeBron James"
    assert body["player_b"]["name"] == "Aaron Gordon"
    assert 0 <= body["fit_score"] <= 100


def test_cross_season_pair_uses_each_players_season(client, monkeypatch):
    fit._feature_table.cache_clear()
    fixture = fit._feature_table("2023-24", 300)

    def feature_table_for_requested_season(season, min_minutes=None):
        result = fixture.copy()
        result.attrs["data_source"] = f"fixture_{season}"
        return result

    monkeypatch.setattr(fit, "_feature_table", feature_table_for_requested_season)
    response = client.get(
        "/fit/pair/2544/203932?season_a=2012-13&season_b=2023-24&min_minutes=300",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["season"] is None
    assert body["season_a"] == "2012-13"
    assert body["season_b"] == "2023-24"
    assert body["player_a"]["season"] == "2012-13"
    assert body["player_b"]["season"] == "2023-24"
    assert body["data_source_a"] == "fixture_2012-13"
    assert body["data_source_b"] == "fixture_2023-24"


def test_same_player_can_be_compared_across_seasons(client, monkeypatch):
    fixture = fit._feature_table("2023-24", 300)
    monkeypatch.setattr(fit, "_feature_table", lambda *_args, **_kwargs: fixture)
    response = client.get(
        "/fit/pair/2544/2544?season_a=2012-13&season_b=2023-24&min_minutes=300",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["player_a"]["season"] == "2012-13"
    assert response.json()["player_b"]["season"] == "2023-24"


def test_same_player_same_season_is_rejected(client):
    response = client.get(
        "/fit/pair/2544/2544?season_a=2023-24&season_b=2023-24",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Choose two different player-seasons."


def test_proxy_credentials_are_absent_from_logs(monkeypatch, caplog):
    secret_username = "never-log-this-user"
    secret_password = "never-log-this-password"
    monkeypatch.setenv(
        "PROXY_URL", f"http://{secret_username}:{secret_password}@proxy.example.test:8080"
    )
    with caplog.at_level(logging.INFO):
        session = nba_http.configure_nba_http()
    rendered = caplog.text
    assert secret_username not in rendered
    assert secret_password not in rendered
    assert "proxy.example.test" in rendered
    from nba_api.stats.library.http import NBAStatsHTTP

    assert NBAStatsHTTP.get_session() is session
    monkeypatch.delenv("PROXY_URL")
    nba_http.configure_nba_http()
