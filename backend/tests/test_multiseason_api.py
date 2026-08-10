import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints import players, teams
from app.main import app
from app.services import snapshots
from app.services.nba_http import NBAUpstreamError


PAGES_ORIGIN = "https://matthewellishanson.github.io"
ORIGIN_HEADERS = {"Origin": PAGES_ORIGIN}


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_profiles_cover_first_and_latest_nba_seasons(client):
    first = client.get(
        "/player_profile_stats?player_id=76137&season=1946-47&scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    latest = client.get(
        "/player_profile_stats?player_id=2544&season=2025-26&scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    assert first.status_code == 200
    assert first.json()["data_source"] == "packaged_snapshot"
    assert first.json()["raw_points"] > 0
    assert latest.status_code == 200
    assert latest.json()["data_source"] == "packaged_snapshot"
    assert latest.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_current_player_shots_use_packaged_snapshot(client):
    response = client.get(
        "/player_shots?player_id=2544&season=2025-26", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["data_source"] == "packaged_snapshot"
    assert response.json()["attempts"] == 919


@pytest.mark.parametrize(
    ("player_id", "season", "attempts", "makes"),
    [
        ("201951", "2012-13", 971, 448),
        ("1630162", "2021-22", 1245, 549),
        ("893", "1996-97", 1892, 920),
    ],
)
def test_historical_player_shots_use_packaged_snapshots(
    client, monkeypatch, player_id, season, attempts, makes
):
    snapshots._player_shot_rows.cache_clear()
    monkeypatch.setattr(
        players,
        "_player_shots_for_season",
        lambda *_args: pytest.fail("historical packaged shots must not call stats.nba.com"),
    )
    response = client.get(
        f"/player_shots?player_id={player_id}&season={season}",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.json()["data_source"] == "packaged_snapshot"
    assert response.json()["attempts"] == attempts
    assert response.json()["makes"] == makes


def test_player_shot_snapshot_coverage_matches_packaged_files():
    root = Path(__file__).resolve().parents[1] / "app" / "cache" / "snapshots"
    coverage = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
    supported = [
        item
        for item in coverage["seasons"]
        if 1996 <= int(item["season"].split("-", 1)[0]) <= 2025
    ]
    assert len(supported) == 30
    assert all(item["shots"] is True for item in supported)
    assert all(
        (root / "player-seasons" / f"{item['season']}-shots.csv.gz").is_file()
        for item in supported
    )


def test_player_shots_before_location_era_do_not_call_upstream(client, monkeypatch):
    monkeypatch.setattr(
        players,
        "_player_shots_for_season",
        lambda *_args: pytest.fail("pre-1996 requests must not call stats.nba.com"),
    )
    response = client.get(
        "/player_shots?player_id=893&season=1995-96", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.json()["data_source"] == "not_available_for_era"
    assert response.json()["attempts"] == 0


def test_fit_before_supported_tracking_era_is_truthful(client):
    response = client.get(
        "/fit/pair/76137/76254?season_a=1946-47&season_b=1946-47",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "fit_data_unavailable"
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_team_profiles_are_independent_by_season(client):
    current = client.get(
        "/team_profile_stats?team_id=1610612747&season=2025-26&scale=percentile&opp_scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    historical = client.get(
        "/team_profile_stats?team_id=1610612747&season=2012-13&scale=percentile&opp_scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    assert current.status_code == historical.status_code == 200
    assert current.json()["data_source"] == historical.json()["data_source"] == "packaged_snapshot"
    assert current.json()["raw_points"] != historical.json()["raw_points"]


def test_team_profile_upstream_failure_is_not_zero_200(client, monkeypatch):
    monkeypatch.setattr(
        teams,
        "_ldt_compat",
        lambda **_kwargs: (_ for _ in ()).throw(NBAUpstreamError("team_fixture")),
    )
    response = client.get(
        "/team_profile_stats?team_id=999123&season=2099-00&scale=percentile&opp_scale=percentile",
        headers=ORIGIN_HEADERS,
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "nba_upstream_unavailable"
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_current_team_shots_use_packaged_snapshot(client):
    teams._league_shots_for_season.cache_clear()
    response = client.get(
        "/team_shots?team_id=1610612747&season=2025-26", headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "packaged_snapshot"
    assert body["data_available"] is True
    assert body["summary_for"]["fga"] > 0
    assert body["summary_against"]["fga"] > 0
