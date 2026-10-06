from __future__ import annotations

import importlib
import json
import sys
from copy import deepcopy
from itertools import combinations
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.multi_team_audit import schema_fingerprint
from pair_fit_v2.phase1d_exhaustiveness import (
    CHARLOTTE_ID,
    PHILADELPHIA_ID,
    DiagnosticTransportError,
    DiagnosticTransportResult,
    analyze_boundary_payload,
    build_diagnostic_ledger,
    compare_pair_populations,
    diagnostic_ledger_path,
    revalidate_stopped_identity_normalization,
    replay_authorized_diagnostics,
    run_authorized_diagnostics,
    validate_diagnostic_isolation,
)


BASE_HEADERS = ["GROUP_ID", "GROUP_NAME", "GP", "MIN", "MIN_RANK"]
OVERALL_HEADERS = ["TEAM_ID", "MIN"]


def pair_row(left: int | str, right: int | str, *, gp: int = 1, minutes: float = 1.0):
    return [f"-{left}-{right}-", f"P{left} - P{right}", gp, minutes, 1]


def team_payload(team_id, rows, *, last_n_games="41"):
    return {
        "resource": "teamdashlineups",
        "parameters": {
            "LeagueID": "00",
            "Season": "2024-25",
            "SeasonType": "Regular Season",
            "TeamID": int(team_id),
            "GroupQuantity": 2,
            "MeasureType": "Base",
            "LastNGames": int(last_n_games),
        },
        "resultSets": [
            {"name": "Overall", "headers": OVERALL_HEADERS, "rowSet": [[int(team_id), 10.0]]},
            {"name": "Lineups", "headers": BASE_HEADERS, "rowSet": list(rows)},
        ],
    }


def league_payload(team_id, rows):
    league_headers = ["TEAM_ID", *BASE_HEADERS]
    return {
        "resource": "leaguedashlineups",
        "parameters": {
            "LeagueID": "00",
            "Season": "2024-25",
            "SeasonType": "Regular Season",
            "TeamID": int(team_id),
            "GroupQuantity": 2,
            "MeasureType": "Base",
            "LastNGames": 0,
        },
        "resultSets": [
            {
                "name": "Lineups",
                "headers": league_headers,
                "rowSet": [[int(team_id), *row] for row in rows],
            }
        ],
    }


def approved_schema():
    payload = team_payload(CHARLOTTE_ID, [pair_row(1, 2)])
    return {
        result_set["name"]: schema_fingerprint(result_set)
        for result_set in payload["resultSets"]
    }


def phase1c_manifest_fixture():
    return {
        "raw_assets": [
            {"asset_id": f"raw-asset:{index:024d}"}
            for index in range(60)
        ]
    }


def full_payloads():
    return {
        CHARLOTTE_ID: team_payload(CHARLOTTE_ID, [pair_row(1, 2)], last_n_games="0"),
        PHILADELPHIA_ID: team_payload(PHILADELPHIA_ID, [pair_row(1, 2)], last_n_games="0"),
    }


def response(payload, latency=0.25):
    return DiagnosticTransportResult(
        status_code=200,
        body=json.dumps(payload).encode("utf-8"),
        elapsed_seconds=latency,
    )


def test_exact_boundary_signal_detection_and_theoretical_pair_count():
    players = list(range(1, 24))
    rows = [pair_row(left, right, minutes=index + 1) for index, (left, right) in enumerate(list(combinations(players, 2))[:250])]
    analysis = analyze_boundary_payload(team_payload(CHARLOTTE_ID, rows), measure_type="Base")

    assert analysis["classification"] == "boundary_signal_present"
    assert analysis["row_count"] == 250
    assert analysis["distinct_player_count"] == 23
    assert analysis["theoretical_unordered_pair_count"] == 253
    assert analysis["absent_theoretical_pair_count"] == 3
    assert analysis["maximum_rank_values"] == {"MIN_RANK": 1.0}


def test_partial_window_pair_set_comparison_with_valid_extra_proves_non_exhaustiveness():
    full = team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(1, 3)], last_n_games="0")
    partial = team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(2, 3, gp=4, minutes=7.5)])

    comparison = compare_pair_populations(full, partial)

    assert comparison["classification"] == "proven_non_exhaustive"
    assert comparison["matched_full_season_keys"] == 1
    assert comparison["diagnostic_only_keys"] == [("2", "3")]
    assert comparison["full_season_only_keys"] == [("1", "3")]
    assert comparison["diagnostic_only_examples"][0]["gp"] == 4
    assert comparison["diagnostic_only_examples"][0]["min"] == 7.5
    assert comparison["diagnostic_only_examples"][0]["structurally_valid"] is True


def test_no_extra_key_is_not_proven_exhaustive():
    full = team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(1, 3)], last_n_games="0")
    partial = team_payload(CHARLOTTE_ID, [pair_row(1, 2)])

    comparison = compare_pair_populations(full, partial)

    assert comparison["classification"] == "not_proven_exhaustive"
    assert comparison["diagnostic_only_key_count"] == 0
    assert "does not prove exhaustiveness" in comparison["proof_basis"]


def test_invalid_pair_key_is_not_treated_as_proof():
    full = team_payload(CHARLOTTE_ID, [pair_row(1, 2)], last_n_games="0")
    invalid_row = ["-3-3-", "Same - Same", 2, 5.0, 1]
    partial = team_payload(CHARLOTTE_ID, [pair_row(1, 2), invalid_row])

    comparison = compare_pair_populations(full, partial)

    assert comparison["classification"] == "not_proven_exhaustive"
    assert comparison["diagnostic_only_key_count"] == 0
    assert comparison["diagnostic_invalid_pair_rows"] == [
        {"row_index": 1, "group_id": "-3-3-", "group_name": "Same - Same"}
    ]


def test_diagnostic_identity_includes_last_n_games_and_cannot_collide_with_phase1c():
    ledger = build_diagnostic_ledger()
    phase1c = phase1c_manifest_fixture()

    isolation = validate_diagnostic_isolation(ledger, phase1c)

    assert ledger["assets"][0]["identity"]["parameters"]["LastNGames"] == "41"
    assert ledger["assets"][1]["identity"]["parameters"]["LastNGames"] == "41"
    assert ledger["assets"][2]["identity"]["parameters"]["LastNGames"] == "0"
    assert all(asset["cache"]["relative_path"].startswith("phase1d/diagnostics/") for asset in ledger["assets"])
    assert isolation["isolated"] is True


def test_early_stop_after_conclusive_request_one(tmp_path):
    calls = []

    def transport(identity, timeout):
        calls.append((identity, timeout))
        return response(team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(2, 3)]))

    result = run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c_manifest_fixture(),
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert result["classification"] == "proven_non_exhaustive"
    assert result["attempted"] == 1
    assert len(calls) == 1
    ledger = json.loads(diagnostic_ledger_path(tmp_path).read_text(encoding="utf-8"))
    assert [asset["status"] for asset in ledger["assets"]] == ["verified", "planned", "planned"]


def test_request_two_runs_only_after_inconclusive_request_one(tmp_path):
    calls = []

    def transport(identity, timeout):
        team_id = identity["parameters"]["team_id"]
        calls.append(team_id)
        rows = [pair_row(1, 2)] if team_id == CHARLOTTE_ID else [pair_row(1, 2), pair_row(4, 5)]
        return response(team_payload(team_id, rows))

    result = run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c_manifest_fixture(),
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert calls == [CHARLOTTE_ID, PHILADELPHIA_ID]
    assert result["classification"] == "proven_non_exhaustive"
    assert result["attempted"] == 2


def test_request_three_runs_only_after_two_inconclusive_results(tmp_path):
    calls = []

    def transport(identity, timeout):
        endpoint = identity["endpoint"]
        team_id = identity["parameters"]["team_id"]
        calls.append((endpoint, team_id))
        if endpoint == "LeagueDashLineups":
            return response(league_payload(team_id, [pair_row(1, 2)]))
        return response(team_payload(team_id, [pair_row(1, 2)]))

    result = run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c_manifest_fixture(),
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert calls == [
        ("TeamDashLineups", CHARLOTTE_ID),
        ("TeamDashLineups", PHILADELPHIA_ID),
        ("LeagueDashLineups", CHARLOTTE_ID),
    ]
    assert result["classification"] == "not_proven_exhaustive"
    assert result["attempted"] == 3


def test_failed_request_stops_without_retry_or_progression(tmp_path):
    calls = []

    def transport(identity, timeout):
        calls.append(identity)
        raise DiagnosticTransportError("timeout", "bounded failure")

    kwargs = {
        "phase1c_manifest": phase1c_manifest_fixture(),
        "full_season_base_payloads": full_payloads(),
        "approved_base_schema": approved_schema(),
    }
    first = run_authorized_diagnostics(tmp_path, **kwargs, live_acquisition=True, transport=transport)
    second = run_authorized_diagnostics(tmp_path, **kwargs, live_acquisition=True, transport=transport)

    assert first["stop_category"] == "timeout"
    assert second["stop_category"] == "timeout"
    assert len(calls) == 1
    assert first["attempted"] == second["attempted"] == 1
    assert list((tmp_path / "phase1d" / "diagnostics").glob("*.metadata.json"))


def test_diagnostic_cache_never_mutates_phase1c_manifest(tmp_path):
    phase1c = phase1c_manifest_fixture()
    before = deepcopy(phase1c)

    def transport(identity, timeout):
        return response(team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(9, 10)]))

    run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c,
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert phase1c == before
    assert not (tmp_path / "phase1c").exists()
    assert list((tmp_path / "phase1d" / "diagnostics").glob("*.json"))


def test_cache_only_replay_cannot_call_transport(tmp_path, monkeypatch):
    def transport(identity, timeout):
        return response(team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(2, 3)]))

    kwargs = {
        "phase1c_manifest": phase1c_manifest_fixture(),
        "full_season_base_payloads": full_payloads(),
        "approved_base_schema": approved_schema(),
    }
    run_authorized_diagnostics(tmp_path, **kwargs, live_acquisition=True, transport=transport)

    def forbidden_session(*args, **kwargs):
        raise AssertionError("cache replay attempted network access")

    monkeypatch.setattr("requests.Session", forbidden_session)
    first = replay_authorized_diagnostics(tmp_path, **kwargs)
    second = replay_authorized_diagnostics(tmp_path, **kwargs)

    assert first == second
    assert first["classification"] == "proven_non_exhaustive"


def test_http_failure_persists_body_and_stops(tmp_path):
    calls = []

    def transport(identity, timeout):
        calls.append(identity)
        return DiagnosticTransportResult(status_code=503, body=b"unavailable", elapsed_seconds=0.1)

    result = run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c_manifest_fixture(),
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert result["stop_category"] == "http_error"
    assert len(calls) == 1
    assert list((tmp_path / "phase1d" / "diagnostics").glob("*.error.bin"))


def test_schema_or_identity_error_stops_without_progression(tmp_path):
    calls = []

    def transport(identity, timeout):
        calls.append(identity)
        payload = team_payload(CHARLOTTE_ID, [pair_row(1, 2)])
        payload["parameters"]["LastNGames"] = 40
        return response(payload)

    result = run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c_manifest_fixture(),
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert result["stop_category"] == "validation_error"
    assert len(calls) == 1


def test_poround_empty_request_and_zero_response_are_identity_equivalent(tmp_path):
    def transport(identity, timeout):
        payload = team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(3, 4)])
        payload["parameters"]["PORound"] = 0
        return response(payload)

    result = run_authorized_diagnostics(
        tmp_path,
        phase1c_manifest=phase1c_manifest_fixture(),
        full_season_base_payloads=full_payloads(),
        approved_base_schema=approved_schema(),
        live_acquisition=True,
        transport=transport,
    )

    assert result["classification"] == "proven_non_exhaustive"
    assert result["failed"] == 0


def test_stopped_poround_case_can_be_revalidated_offline_without_advancing(tmp_path):
    def transport(identity, timeout):
        payload = team_payload(CHARLOTTE_ID, [pair_row(1, 2), pair_row(3, 4)])
        payload["parameters"]["PORound"] = 0
        return response(payload)

    kwargs = {
        "phase1c_manifest": phase1c_manifest_fixture(),
        "full_season_base_payloads": full_payloads(),
        "approved_base_schema": approved_schema(),
    }
    run_authorized_diagnostics(tmp_path, **kwargs, live_acquisition=True, transport=transport)
    path = diagnostic_ledger_path(tmp_path)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    first = ledger["assets"][0]
    first["status"] = "failed"
    first["comparison"] = None
    first["attempt"] = {
        "attempt_number": 1,
        "request_kind": "phase1d_live_diagnostic",
        "status": "failed",
        "error_category": "validation_error",
        "error_detail": "Response request identity mismatch: PORound expected empty, actual 0",
    }
    path.write_text(json.dumps(ledger), encoding="utf-8")

    result = revalidate_stopped_identity_normalization(tmp_path, **kwargs)
    replay = replay_authorized_diagnostics(tmp_path, **kwargs)

    assert result["classification"] == "proven_non_exhaustive"
    assert result["additional_live_requests"] == 0
    assert result["later_requests_untouched"] is True
    assert result["original_attempt"]["status"] == "failed"
    assert replay["classification"] == "proven_non_exhaustive"
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert [asset["attempt_count"] for asset in reloaded["assets"]] == [1, 0, 0]
    assert reloaded["assets"][0]["status"] == "verified_after_offline_revalidation"


def test_import_has_no_live_request(monkeypatch):
    import pair_fit_v2.phase1d_exhaustiveness as module

    def forbidden_session(*args, **kwargs):
        raise AssertionError("module import attempted network access")

    monkeypatch.setattr("requests.Session", forbidden_session)
    importlib.reload(module)
