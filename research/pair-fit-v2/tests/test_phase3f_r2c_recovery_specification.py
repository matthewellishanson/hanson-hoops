from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
import requests

from pair_fit_v2 import phase3f_r2c_recovery_specification as r2c


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def source_html(*, start: bool = True, end: bool = True) -> bytes:
    pieces = [
        "<html><head><title>NBA announces schedule for 2025-26 regular season</title>",
        '<meta property="article:published_time" content="2025-08-14T19:00:00Z"></head><body>',
    ]
    if start:
        pieces.append("The 2025-26 NBA regular season will tip off on Tuesday, Oct. 21, 2025.")
    if end:
        pieces.append("The regular season will conclude on Sunday, April 12, 2026.")
    pieces.append("</body></html>")
    return "".join(pieces).encode()


class FakeSession:
    def __init__(self, response: requests.Response):
        self.response = response
        self.trust_env = False
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response

    def close(self):
        self.closed = True


def fake_response(body: bytes | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.url = r2c.PUBLIC_URL
    response.headers["Content-Type"] = "text/html; charset=UTF-8"
    response._content = source_html() if body is None else body
    return response


def full_parameters(team_id: str, measure: str) -> dict[str, str]:
    return {
        "DateFrom": "", "DateTo": "", "GameID": "", "GameSegment": "",
        "GroupQuantity": "2", "LastNGames": "0", "LeagueID": "00", "Location": "",
        "MeasureType": measure, "Month": "0", "OpponentTeamID": "0", "Outcome": "",
        "PORound": "", "PaceAdjust": "N", "PerMode": "Totals", "Period": "0",
        "PlusMinus": "N", "Rank": "N", "Season": "2025-26", "SeasonSegment": "",
        "SeasonType": "Regular Season", "ShotClockRange": "", "TeamID": team_id,
        "VsConference": "", "VsDivision": "",
    }


def triggering_requests() -> list[dict]:
    output = []
    for team in r2c.TEAM_SPECS:
        for key, measure in (("base", "Base"), ("advanced", "Advanced")):
            trigger = team[key]
            output.append({"ordinal": trigger["ordinal"], "request_id": trigger["request_id"],
                           "endpoint": "teamdashlineups", "parameters": full_parameters(team["team_id"], measure)})
    return output


def prepare_project(root: Path) -> Path:
    for namespace in r2c.HISTORICAL_NAMESPACES:
        path = root / namespace
        path.mkdir(parents=True, exist_ok=True)
        (path / "sentinel.txt").write_text(namespace.as_posix(), encoding="utf-8")
    exact = {"teams": []}
    for team in r2c.TEAM_SPECS:
        exact["teams"].append({
            "team_id": team["team_id"], "structural_disposition": "exact_250_unresolved",
            "triggering_identities": [
                {"measure": "Base", **team["base"]}, {"measure": "Advanced", **team["advanced"]},
            ],
        })
    (root / r2c.R2B2_EXACT_250_PATH).write_text(json.dumps(exact), encoding="utf-8")
    (root / r2c.R2B2_REQUESTS_PATH).write_text(json.dumps(triggering_requests()), encoding="utf-8")
    (root / r2c.R2B1_CONTRACT_PATH).write_text(
        json.dumps({"correction_contract_identity": r2c.R2B1_CONTRACT_IDENTITY}), encoding="utf-8"
    )
    transport = PROJECT_ROOT / r2c.R2B21_TRANSPORT_PATH
    (root / r2c.R2B21_TRANSPORT_PATH).write_bytes(transport.read_bytes())
    public = root / r2c.PUBLIC_SOURCE_NAMESPACE
    session = FakeSession(fake_response())
    r2c.acquire_public_source(public, session_factory=lambda: session,
                              clock=iter(["2026-10-02T12:00:00Z", "2026-10-02T12:00:01Z"]).__next__)
    return root


def test_exact_public_url_allowlist_and_transport_restrictions():
    r2c.validate_public_request(url=r2c.PUBLIC_URL)
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_public_request(url=r2c.PUBLIC_URL + "?x=1")
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_public_request(url=r2c.PUBLIC_URL, method="POST")
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_public_request(url=r2c.PUBLIC_URL, allow_redirects=True)
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_public_request(url=r2c.PUBLIC_URL, automatic_retries=1)
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_public_request(url=r2c.PUBLIC_URL, fallback_urls=("https://example.com",))
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_public_request(url=r2c.PUBLIC_URL, attempt_number=2)


def test_public_acquisition_is_one_get_without_redirects_or_retries(tmp_path):
    session = FakeSession(fake_response())
    result = r2c.acquire_public_source(tmp_path / "public", session_factory=lambda: session,
                                      clock=iter(["a", "b"]).__next__)
    assert len(session.calls) == 1
    assert session.calls[0] == (r2c.PUBLIC_URL, {"timeout": 30, "allow_redirects": False})
    assert session.closed and result["request_count"] == 1
    assert sorted(path.name for path in (tmp_path / "public").iterdir()) == sorted(r2c.PUBLIC_FILES)


def test_expected_boundaries_and_missing_statement_failures():
    result = r2c.extract_verified_source(source_html(), content_type="text/html")
    assert (result["season_start"], result["season_end"]) == ("2025-10-21", "2026-04-12")
    with pytest.raises(r2c.SourceVerificationError):
        r2c.extract_verified_source(source_html(start=False), content_type="text/html")
    with pytest.raises(r2c.SourceVerificationError):
        r2c.extract_verified_source(source_html(end=False), content_type="text/html")
    with pytest.raises(r2c.SourceVerificationError):
        r2c.extract_verified_source(source_html(), content_type="application/json")


def test_redirect_and_second_or_partial_namespace_are_refused(tmp_path):
    response = fake_response()
    response.status_code = 302
    response.headers["Location"] = "https://example.com"
    response._content = b"redirect"
    with pytest.raises(r2c.SourceVerificationError):
        r2c.acquire_public_source(tmp_path / "public", session_factory=lambda: FakeSession(response),
                                  clock=iter(["a", "b"]).__next__)
    with pytest.raises(r2c.SpecificationError):
        r2c.acquire_public_source(tmp_path / "public", session_factory=lambda: FakeSession(fake_response()))


def test_exact_window_coverage():
    proof = r2c.prove_window_coverage()
    assert proof["both_within_verified_interval"]
    assert proof["nonoverlapping"] and proof["contiguous"] and proof["complete_coverage"]
    assert proof["verified_interval_day_count"] == proof["window_union_day_count"]


def test_exact_two_teams_eight_identities_and_order():
    identities = r2c.build_recovery_identities(triggering_requests())
    assert [item["team_id"] for item in identities] == ["1610612754"] * 4 + ["1610612763"] * 4
    assert [item["ordinal"] for item in identities] == list(range(1, 9))
    assert [(item["window"]["name"], item["measure"]) for item in identities] == [
        ("early", "Base"), ("early", "Advanced"), ("late", "Base"), ("late", "Advanced")
    ] * 2


def test_identity_parameters_triggers_contracts_and_namespaces():
    source = {item["request_id"]: item for item in triggering_requests()}
    identities = r2c.build_recovery_identities(list(source.values()))
    for item in identities:
        assert item["endpoint_identity"] == "TeamDashLineups"
        assert item["parameters"]["GroupQuantity"] == "2"
        assert item["parameters"]["PerMode"] == "Totals"
        assert item["parameters"]["Season"] == "2025-26"
        assert item["parameters"]["SeasonType"] == "Regular Season"
        assert item["parameters"]["DateFrom"] == item["window"]["DateFrom"]
        assert item["parameters"]["DateTo"] == item["window"]["DateTo"]
        assert item["corrected_response_contract_identity"] == r2c.R2B1_CONTRACT_IDENTITY
        assert item["future_protected_transport_contract"]["sha256"] == r2c.R2B21_TRANSPORT_SHA256
        assert item["future_output_namespace"].startswith(r2c.FUTURE_PROTECTED_NAMESPACE.as_posix())
        for trigger in item["triggering_full_season_identities"].values():
            assert len(trigger["raw_sha256"]) == len(trigger["canonical_json_sha256"]) == 64
        original = source[item["triggering_full_season_identities"][item["measure"]]["request_id"]]
        expected = dict(original["parameters"])
        expected.update(DateFrom=item["window"]["DateFrom"], DateTo=item["window"]["DateTo"])
        assert item["parameters"] == expected


@pytest.mark.parametrize(("field", "value"), [
    ("team_id", "1610612744"), ("endpoint", "other"), ("measure", "Usage"),
    ("season", "2024-25"), ("season_type", "Playoffs"),
    ("request_id", "teamdashlineups:other"), ("future_output_namespace", "cache/other"),
])
def test_inventory_rejects_other_team_endpoint_or_measure(field, value):
    identities = r2c.build_recovery_identities(triggering_requests())
    identities[0][field] = value
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_recovery_inventory(identities)


@pytest.mark.parametrize(("field", "value"), [
    ("Season", "2024-25"), ("SeasonType", "Playoffs"), ("GroupQuantity", "3"),
    ("MeasureType", "Usage"), ("DateFrom", "2025-10-22"), ("DateTo", "2026-04-11"),
])
def test_inventory_rejects_other_seasons_group_measure_or_windows(field, value):
    identities = r2c.build_recovery_identities(triggering_requests())
    identities[0]["parameters"][field] = value
    with pytest.raises(r2c.SpecificationError):
        r2c.validate_recovery_inventory(identities)


def test_ninth_identity_is_rejected():
    identities = r2c.build_recovery_identities(triggering_requests())
    identities.append(copy.deepcopy(identities[-1]))
    with pytest.raises(r2c.SpecificationError, match="exactly eight"):
        r2c.validate_recovery_inventory(identities)


def test_numeric_pair_canonicalization_and_zero_possession_independence():
    assert r2c.canonical_pair_key(("20", "3")) == (3, 20)
    assert r2c.canonical_pair_population(((2, 1), (4, 3))) == {(1, 2), (3, 4)}


@pytest.mark.parametrize(("rows", "field"), [
    ([(1, 2), (2, 1)], "duplicate"), ([(-1, 2)], "malformed"), ([(1, 1)], "same_player"),
    ([(1, 2, 3)], "malformed"),
])
def test_duplicate_malformed_and_same_player_rejection(rows, field):
    with pytest.raises(r2c.PairPopulationError) as exc:
        r2c.canonical_pair_population(rows)
    assert exc.value.diagnostics[field] == 1


def operational_record(**changes):
    record = {
        "all_four_authenticated_and_structurally_valid": True,
        "every_window_below_250": True,
        "base_advanced_equal_within_each_window": True,
        "complete_complementary_coverage": True,
        "recovered_only_count": 0, "full_season_only_count": 0,
        "duplicate_count": 0, "malformed_count": 0, "same_player_count": 0,
        "base_only_count": 0, "advanced_only_count": 0,
    }
    record.update(changes)
    return record


def test_recovered_only_classification_and_later_exclusion_implication():
    disposition = r2c.classify_disposition(operational_record(recovered_only_count=1))
    assert disposition == "proven_non_exhaustive"
    assert r2c.whole_team_exclusion_implication(disposition)
    assert not r2c.whole_team_exclusion_implication("recovery_unresolved")


def test_exact_operational_resolution_conditions_and_limiters():
    assert r2c.classify_disposition(operational_record()) == "operationally_resolved_no_observed_omission"
    assert r2c.classify_disposition(operational_record(every_window_below_250=False)) == "recovery_unresolved"
    assert r2c.classify_disposition(operational_record(full_season_only_count=1)) == "recovery_unresolved"
    assert r2c.classify_disposition(operational_record(base_only_count=1)) == "recovery_unresolved"
    assert r2c.classify_disposition(operational_record(all_four_authenticated_and_structurally_valid=False)) == "recovery_unresolved"


def test_base_advanced_mismatch_is_unresolved():
    record = operational_record(base_advanced_equal_within_each_window=False, advanced_only_count=1)
    assert r2c.classify_disposition(record) == "recovery_unresolved"


def test_write_once_deterministic_dual_build_and_exact_inventory(tmp_path):
    project = prepare_project(tmp_path / "project")
    one = r2c.build_specification(project, tmp_path / "one")
    two = r2c.build_specification(project, tmp_path / "two")
    assert one == two
    result = r2c.write_specification(project, tmp_path / "official")
    assert set(result["artifacts"]) == set(r2c.PLANNING_FILES)
    assert sorted(path.name for path in (tmp_path / "official").iterdir()) == sorted(r2c.PLANNING_FILES)
    with pytest.raises(r2c.SpecificationError):
        r2c.write_specification(project, tmp_path / "official")
    partial = tmp_path / "partial"
    partial.mkdir()
    with pytest.raises(r2c.SpecificationError):
        r2c.write_specification(project, partial)


def test_plan_freezes_no_rating_aggregation_target_reconstruction_or_r2c_exclusion(tmp_path):
    project = prepare_project(tmp_path / "project")
    plan = json.loads(r2c.build_specification(project, tmp_path / "out")["recovery_plan.json"])
    reconciliation = plan["population_reconciliation"]
    assert reconciliation["rating_aggregation"] is False
    assert reconciliation["full_season_target_reconstruction"] is False
    assert reconciliation["rating_values_affect_retention"] is False
    assert plan["dispositions"]["proven_non_exhaustive"]["applied_during_r2c"] is False
    assert "not proof of universal or mathematical endpoint exhaustiveness" in plan["dispositions"]["operationally_resolved_no_observed_omission"]["limitation"]


def test_build_has_no_protected_acquisition_or_model_capability():
    source = (PROJECT_ROOT / "src/pair_fit_v2/phase3f_r2c_recovery_specification.py").read_text(encoding="utf-8")
    assert "stats.nba.com" not in source
    assert "sklearn" not in source
    assert ".fit(" not in source and ".predict(" not in source
    assert "pickle" not in source and "joblib" not in source
    assert "sqlite" not in source and "duckdb" not in source
    assert "FastAPI" not in source and "flask" not in source.lower()
    assert "react" not in source.lower() and "deployment" in source


def test_git_ignore_behavior():
    for path in (r2c.PUBLIC_SOURCE_NAMESPACE / "x", r2c.PLANNING_NAMESPACE / "x"):
        result = subprocess.run(["git", "check-ignore", str(path)], cwd=PROJECT_ROOT,
                                capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
