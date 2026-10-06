from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pair_fit_v2.phase1e_recovery as phase1e
from pair_fit_v2.multi_team_audit import schema_fingerprint
from pair_fit_v2.phase1e_recovery import (
    BASE_ADDITIVE_FIELDS,
    CHARLOTTE_ID,
    PHILADELPHIA_ID,
    PHASE1D_PROVING_KEYS,
    WindowTransportError,
    WindowTransportResult,
    audit_additive_reconstruction,
    audit_team_recovery,
    build_phase1e_ledger,
    reconcile_window_measures,
    replay_phase1e_recovery,
    run_phase1e_recovery,
    threshold_sensitivity,
    validate_phase1e_isolation,
    validate_window_contract,
    validate_window_payload,
)


BASE_HEADERS = [
    "GROUP_ID",
    "GROUP_NAME",
    "GP",
    "W",
    "L",
    "MIN",
    "PTS",
    "PLUS_MINUS",
    "SUM_TIME_PLAYED",
]
ADVANCED_HEADERS = [
    "GROUP_ID",
    "GROUP_NAME",
    "GP",
    "MIN",
    "POSS",
    "OFF_RATING",
    "DEF_RATING",
    "NET_RATING",
]


def group_id(key):
    return f"-{key[0]}-{key[1]}-"


def group_name(key):
    return f"P{key[0]} - P{key[1]}"


def base_row(key, gp, minutes, points, plus_minus, *, wins=None, losses=None):
    wins = gp if wins is None else wins
    losses = 0 if losses is None else losses
    return [
        group_id(key),
        group_name(key),
        gp,
        wins,
        losses,
        minutes,
        points,
        plus_minus,
        round(minutes * 60),
    ]


def advanced_row(key, gp, minutes, poss, off, defense, net):
    return [group_id(key), group_name(key), gp, minutes, poss, off, defense, net]


def payload(team_id, measure, rows, *, date_from="", date_to=""):
    headers = BASE_HEADERS if measure == "Base" else ADVANCED_HEADERS
    return {
        "resource": "teamdashlineups",
        "parameters": {
            "LeagueID": "00",
            "Season": "2024-25",
            "SeasonType": "Regular Season",
            "TeamID": int(team_id),
            "GroupQuantity": 2,
            "MeasureType": measure,
            "LastNGames": 0,
            "DateFrom": date_from,
            "DateTo": date_to,
            "PORound": 0,
        },
        "resultSets": [
            {
                "name": "Overall",
                "headers": ["TEAM_ID", "MIN"],
                "rowSet": [[int(team_id), 22.0]],
            },
            {"name": "Lineups", "headers": headers, "rowSet": rows},
        ],
    }


def approved_schemas():
    result = {}
    for measure, row in (
        ("Base", base_row(("1", "2"), 1, 10, 20, 5)),
        ("Advanced", advanced_row(("1", "2"), 1, 10, 20, 100, 75, 25)),
    ):
        example = payload(CHARLOTTE_ID, measure, [row])
        result[measure] = {
            result_set["name"]: schema_fingerprint(result_set)
            for result_set in example["resultSets"]
        }
    return result


def proving_rows(measure, window):
    keys = sorted(PHASE1D_PROVING_KEYS, key=lambda key: (int(key[0]), int(key[1])))
    selected = keys[:2] if window == "early" else keys[2:]
    if measure == "Base":
        return [base_row(key, 1, index + 1, index + 2, 0) for index, key in enumerate(selected)]
    return [advanced_row(key, 1, index + 1, index + 1, 100, 100, 0) for index, key in enumerate(selected)]


def fixture_payloads(team_id, *, include_proving=False):
    main = ("1", "2")
    early_base = [base_row(main, 1, 10, 20, 5)]
    early_advanced = [advanced_row(main, 1, 10, 20, 100, 75, 25)]
    late_base = [base_row(main, 1, 12, 33, 3)]
    late_advanced = [advanced_row(main, 1, 12, 30, 110, 100, 10)]
    if include_proving:
        early_base += proving_rows("Base", "early")
        early_advanced += proving_rows("Advanced", "early")
        late_base += proving_rows("Base", "late")
        late_advanced += proving_rows("Advanced", "late")
    return {
        "full": {
            "Base": payload(team_id, "Base", [base_row(main, 2, 22, 53, 8)]),
            "Advanced": payload(
                team_id, "Advanced", [advanced_row(main, 2, 22, 50, 106, 90, 16)]
            ),
        },
        "windows": {
            "early": {
                "Base": payload(
                    team_id, "Base", early_base, date_from="10/22/2024", date_to="01/31/2025"
                ),
                "Advanced": payload(
                    team_id,
                    "Advanced",
                    early_advanced,
                    date_from="10/22/2024",
                    date_to="01/31/2025",
                ),
            },
            "late": {
                "Base": payload(
                    team_id, "Base", late_base, date_from="02/01/2025", date_to="04/13/2025"
                ),
                "Advanced": payload(
                    team_id,
                    "Advanced",
                    late_advanced,
                    date_from="02/01/2025",
                    date_to="04/13/2025",
                ),
            },
        },
    }


def protected_manifests():
    phase1c = {"raw_assets": [{"asset_id": f"raw-asset:{index:024d}"} for index in range(60)]}
    phase1d = {"assets": [{"asset_id": f"phase1d-diagnostic-asset:{index:024d}"} for index in range(3)]}
    return phase1c, phase1d


def runner_context():
    charlotte = fixture_payloads(CHARLOTTE_ID, include_proving=True)
    philadelphia = fixture_payloads(PHILADELPHIA_ID, include_proving=False)
    phase1c, phase1d = protected_manifests()
    return {
        "phase1c_manifest": phase1c,
        "phase1d_ledger": phase1d,
        "full_season_payloads": {
            CHARLOTTE_ID: charlotte["full"],
            PHILADELPHIA_ID: philadelphia["full"],
        },
        "approved_schemas": approved_schemas(),
    }, {CHARLOTTE_ID: charlotte["windows"], PHILADELPHIA_ID: philadelphia["windows"]}


def test_deterministic_window_identities_and_complete_non_overlapping_bounds():
    first = build_phase1e_ledger()
    second = build_phase1e_ledger()

    assert first == second
    assert validate_window_contract() == first["window_contract"]
    assert [asset["sequence"] for asset in first["assets"]] == list(range(1, 9))
    assert [
        (asset["team_name"], asset["window"], asset["measure"])
        for asset in first["assets"]
    ] == [
        ("Charlotte Hornets", "early", "Base"),
        ("Charlotte Hornets", "early", "Advanced"),
        ("Charlotte Hornets", "late", "Base"),
        ("Charlotte Hornets", "late", "Advanced"),
        ("Philadelphia 76ers", "early", "Base"),
        ("Philadelphia 76ers", "early", "Advanced"),
        ("Philadelphia 76ers", "late", "Base"),
        ("Philadelphia 76ers", "late", "Advanced"),
    ]
    assert first["assets"][0]["identity"]["parameters"]["DateFrom"] == "10/22/2024"
    assert first["assets"][3]["identity"]["parameters"]["DateTo"] == "04/13/2025"


def test_diagnostic_asset_ids_and_paths_are_isolated():
    phase1c, phase1d = protected_manifests()
    ledger = build_phase1e_ledger()

    result = validate_phase1e_isolation(ledger, phase1c, phase1d)

    assert result["isolated"] is True
    assert len({asset["asset_id"] for asset in ledger["assets"]}) == 8
    assert all(asset["asset_id"].startswith("phase1e-diagnostic-asset:") for asset in ledger["assets"])
    assert all(asset["cache"]["relative_path"].startswith("phase1e/windows/") for asset in ledger["assets"])


def test_schema_and_exact_date_identity_are_enforced():
    asset = build_phase1e_ledger()["assets"][0]
    valid = fixture_payloads(CHARLOTTE_ID)["windows"]["early"]["Base"]
    validation = validate_window_payload(valid, asset["identity"], approved_schemas()["Base"])
    assert validation["row_counts"]["Lineups"] == 1

    ignored = deepcopy(valid)
    ignored["parameters"]["DateFrom"] = ""
    with pytest.raises(ValueError, match="Ambiguous or ignored DateFrom"):
        validate_window_payload(ignored, asset["identity"], approved_schemas()["Base"])

    wrong_schema = deepcopy(valid)
    wrong_schema["resultSets"][1]["headers"].append("UNEXPECTED")
    wrong_schema["resultSets"][1]["rowSet"][0].append(1)
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_window_payload(wrong_schema, asset["identity"], approved_schemas()["Base"])


def test_child_window_exact_250_is_rejected():
    asset = build_phase1e_ledger()["assets"][0]
    rows = [base_row((str(index + 1), str(index + 1001)), 1, 1, 1, 0) for index in range(250)]
    response_payload = payload(
        CHARLOTTE_ID, "Base", rows, date_from="10/22/2024", date_to="01/31/2025"
    )
    with pytest.raises(ValueError, match="exact-250"):
        validate_window_payload(response_payload, asset["identity"], approved_schemas()["Base"])


def test_full_outer_reconciliation_preserves_unmatched_zero_and_invalid_rows():
    key = ("1", "2")
    extra = ("3", "4")
    base = payload(CHARLOTTE_ID, "Base", [base_row(key, 1, 1, 1, 0), base_row(extra, 1, 1, 1, 0)])
    advanced = payload(
        CHARLOTTE_ID,
        "Advanced",
        [advanced_row(key, 1, 1, 0, 0, 0, 0), ["-5-5-", "Same", 1, 1, -1, 0, 0, 0]],
    )

    result = reconcile_window_measures(base, advanced)

    assert result["base_only_keys"] == [extra]
    assert result["advanced_same_player_identifiers"]
    assert result["zero_possessions"] == 1
    assert result["negative_possessions"] == 1
    assert result["target_eligible_rows"] == 0
    assert result["full_outer_union_count"] == 2


def test_duplicate_pair_keys_are_rejected_by_structural_gate():
    fixtures = fixture_payloads(CHARLOTTE_ID, include_proving=True)
    fixtures["windows"]["early"]["Base"]["resultSets"][1]["rowSet"].append(
        deepcopy(fixtures["windows"]["early"]["Base"]["resultSets"][1]["rowSet"][0])
    )

    audit = audit_team_recovery(
        CHARLOTTE_ID,
        fixtures["full"]["Base"],
        fixtures["full"]["Advanced"],
        fixtures["windows"],
    )

    assert audit["window_reconciliation"]["early"]["base_duplicate_keys"]
    assert audit["continuation_gate"]["checks"]["base_advanced_reconciliation_structurally_sound"] is False
    assert audit["continuation_gate"]["passed"] is False


def test_canonical_union_recovers_known_omissions_and_full_population():
    fixtures = fixture_payloads(CHARLOTTE_ID, include_proving=True)

    audit = audit_team_recovery(
        CHARLOTTE_ID,
        fixtures["full"]["Base"],
        fixtures["full"]["Advanced"],
        fixtures["windows"],
    )

    assert audit["union"]["full_season_only_keys"] == []
    assert set(audit["union"]["window_union_only_keys"]) == PHASE1D_PROVING_KEYS
    assert set(audit["union"]["phase1d_proving_keys_present"]) == PHASE1D_PROVING_KEYS
    assert audit["union"]["increase_above_full_season_response"] == 3
    assert audit["recovered_only"]["count"] == 3


def test_additive_totals_and_possession_weighted_rates_recompose():
    fixtures = fixture_payloads(CHARLOTTE_ID, include_proving=True)

    result = audit_additive_reconstruction(
        fixtures["full"]["Base"], fixtures["full"]["Advanced"], fixtures["windows"]
    )

    assert "MIN" in BASE_ADDITIVE_FIELDS
    assert "PTS" in BASE_ADDITIVE_FIELDS
    assert "PLUS_MINUS" in BASE_ADDITIVE_FIELDS
    assert result["additive_totals_reproduced"] is True
    assert result["rate_recomposition_within_0_2_every_row"] is True
    assert result["rate_recomposition"]["OFF_RATING"]["maximum_absolute_error"] == 0
    assert result["base_points_plus_minus_derived_ratings"]["classification"] == "validated"


def test_zero_possession_is_preserved_but_excluded_from_rate_arithmetic():
    fixtures = fixture_payloads(CHARLOTTE_ID)
    zero = ("9", "10")
    fixtures["windows"]["early"]["Base"]["resultSets"][1]["rowSet"].append(
        base_row(zero, 1, 0.1, 0, 0)
    )
    fixtures["windows"]["early"]["Advanced"]["resultSets"][1]["rowSet"].append(
        advanced_row(zero, 1, 0, 0, 0, 0, 0)
    )

    audit = audit_team_recovery(
        CHARLOTTE_ID,
        fixtures["full"]["Base"],
        fixtures["full"]["Advanced"],
        fixtures["windows"],
    )

    assert audit["window_reconciliation"]["early"]["zero_possessions"] == 1
    recovered = {tuple(row["pair_ids"]): row for row in audit["recovered_only"]["pairs"]}
    assert zero in recovered
    assert recovered[zero]["advanced_possessions"] == 0
    assert recovered[zero]["reconstructed_ratings"] is None


def test_threshold_sensitivity_reports_known_omission_retention():
    full = fixture_payloads(CHARLOTTE_ID)["full"]["Advanced"]
    recovered = [
        {"pair_ids": ("1", "2"), "advanced_possessions": 50},
        {"pair_ids": ("3", "4"), "advanced_possessions": 7},
    ]
    omitted = [recovered[1]]

    result = threshold_sensitivity(recovered, omitted, full)

    by_threshold = {row["threshold_possessions"]: row for row in result}
    assert by_threshold[5]["known_omission_remains_model_eligible"] is True
    assert by_threshold[10]["known_omission_remains_model_eligible"] is False
    assert by_threshold[5]["recovered_only_rows_retained"] == 1
    assert by_threshold[10]["recovered_only_rows_retained"] == 0


def test_request_budget_order_and_successful_both_team_classification(tmp_path):
    context, windows = runner_context()
    calls = []

    def transport(identity, timeout):
        parameters = identity["parameters"]
        team_id = parameters["team_id"]
        window = "early" if parameters["DateFrom"] == "10/22/2024" else "late"
        measure = parameters["measure_type"]
        calls.append((team_id, window, measure, timeout))
        return WindowTransportResult(
            status_code=200,
            body=json.dumps(windows[team_id][window][measure]).encode(),
            elapsed_seconds=0.1,
        )

    result = run_phase1e_recovery(
        tmp_path, **context, live_acquisition=True, transport=transport
    )

    assert len(calls) == 8
    assert calls[:4] == [
        (CHARLOTTE_ID, "early", "Base", 30),
        (CHARLOTTE_ID, "early", "Advanced", 30),
        (CHARLOTTE_ID, "late", "Base", 30),
        (CHARLOTTE_ID, "late", "Advanced", 30),
    ]
    assert result["attempted"] == result["verified"] == 8
    assert result["classification"] == "window recovery and target recomposition demonstrated for both affected team-seasons"


def test_stop_on_failure_has_no_retry_or_progression(tmp_path):
    context, _ = runner_context()
    calls = []

    def transport(identity, timeout):
        calls.append(identity)
        raise WindowTransportError("timeout", "bounded failure")

    first = run_phase1e_recovery(
        tmp_path, **context, live_acquisition=True, transport=transport
    )
    second = run_phase1e_recovery(
        tmp_path, **context, live_acquisition=True, transport=transport
    )

    assert first["stop_category"] == second["stop_category"] == "timeout"
    assert first["attempted"] == second["attempted"] == 1
    assert len(calls) == 1


def test_charlotte_gate_failure_skips_philadelphia(tmp_path):
    context, windows = runner_context()
    calls = []
    # Remove the immutable full key from Charlotte's late and early windows.
    for window in windows[CHARLOTTE_ID].values():
        for measure_payload in window.values():
            measure_payload["resultSets"][1]["rowSet"] = [
                row for row in measure_payload["resultSets"][1]["rowSet"] if row[0] != "-1-2-"
            ]

    def transport(identity, timeout):
        p = identity["parameters"]
        team = p["team_id"]
        window = "early" if p["DateFrom"] == "10/22/2024" else "late"
        calls.append(team)
        return WindowTransportResult(200, json.dumps(windows[team][window][p["measure_type"]]).encode(), 0.1)

    result = run_phase1e_recovery(
        tmp_path, **context, live_acquisition=True, transport=transport
    )

    assert len(calls) == 4
    assert set(calls) == {CHARLOTTE_ID}
    assert result["stop_category"] == "charlotte_continuation_gate_failed"


def test_cache_only_replay_is_identical_and_has_no_network_surface(tmp_path, monkeypatch):
    context, windows = runner_context()

    def transport(identity, timeout):
        p = identity["parameters"]
        window = "early" if p["DateFrom"] == "10/22/2024" else "late"
        return WindowTransportResult(
            200, json.dumps(windows[p["team_id"]][window][p["measure_type"]]).encode(), 0.1
        )

    run_phase1e_recovery(tmp_path, **context, live_acquisition=True, transport=transport)

    def forbidden(*args, **kwargs):
        raise AssertionError("cache replay attempted network access")

    monkeypatch.setattr("requests.Session", forbidden)
    ledger_path = tmp_path / "phase1e" / "recovery_ledger.json"
    ledger_before_replay = ledger_path.read_bytes()
    first = replay_phase1e_recovery(tmp_path, **context)
    second = replay_phase1e_recovery(tmp_path, **context)

    assert first == second
    assert ledger_path.read_bytes() == ledger_before_replay
    assert first["attempted"] == 8
    assert first["classification"].endswith("both affected team-seasons")


def test_phase1c_manifest_mapping_is_never_mutated(tmp_path):
    context, windows = runner_context()
    original = deepcopy(context["phase1c_manifest"])

    def transport(identity, timeout):
        p = identity["parameters"]
        window = "early" if p["DateFrom"] == "10/22/2024" else "late"
        return WindowTransportResult(
            200, json.dumps(windows[p["team_id"]][window][p["measure_type"]]).encode(), 0.1
        )

    run_phase1e_recovery(tmp_path, **context, live_acquisition=True, transport=transport)

    assert context["phase1c_manifest"] == original
    assert not (tmp_path / "phase1c").exists()
