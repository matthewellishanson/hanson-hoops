import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r2b_1_response_contract as phase


PROJECT = Path(__file__).resolve().parents[1]


def _row(headers, values):
    return [values.get(header, 0) for header in headers]


def request(measure="Base", team_id="1610612737"):
    return {
        "request_id": f"teamdashlineups:{team_id}:{measure.lower()}",
        "endpoint": "teamdashlineups",
        "parameters": {
            "TeamID": team_id,
            "MeasureType": measure,
            "Season": "2025-26",
        },
    }


def payload(measure="Base", pairs=((1, 2),), team_id=1610612737):
    overall_headers = list(phase.SCHEMAS[measure]["Overall"])
    lineups_headers = list(phase.SCHEMAS[measure]["Lineups"])
    overall = _row(
        overall_headers,
        {
            "GROUP_SET": "Overall",
            "GROUP_VALUE": "2025-26",
            "TEAM_ID": team_id,
            "TEAM_ABBREVIATION": "ATL",
            "TEAM_NAME": "Atlanta Hawks",
        },
    )
    lineups = []
    for left, right in pairs:
        values = {
            "GROUP_SET": "Lineups",
            "GROUP_ID": f"-{left}-{right}-",
            "GROUP_NAME": f"{left} - {right}",
            "MIN": 1.0,
            "SUM_TIME_PLAYED": 60.0,
            "POSS": 10.0,
            "NET_RATING": 1.5,
        }
        lineups.append(_row(lineups_headers, values))
    return {
        "resource": "teamdashlineups",
        "parameters": {"TeamID": team_id},
        "resultSets": [
            {"name": "Overall", "headers": overall_headers, "rowSet": [overall]},
            {"name": "Lineups", "headers": lineups_headers, "rowSet": lineups},
        ],
    }


def body(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def validate(value, measure="Base"):
    return phase.validate_response_contract(body(value), request(measure))


def test_exact_overall_plus_lineups_acceptance_and_named_selection_overall_first():
    result = validate(payload())
    assert result["observed_result_set_order"] == ["Overall", "Lineups"]
    assert result["overall_row_count"] == 1
    assert result["lineups_row_count"] == 1
    assert result["canonical_unordered_pair_count"] == 1


@pytest.mark.parametrize("kept", ["Overall", "Lineups"])
def test_one_set_missing_named_set_rejected(kept):
    value = payload()
    value["resultSets"] = [item for item in value["resultSets"] if item["name"] == kept]
    with pytest.raises(phase.ContractError, match="exactly Overall and Lineups"):
        validate(value)


def test_duplicate_and_unexpected_result_set_names_rejected():
    duplicate = payload()
    duplicate["resultSets"][1]["name"] = "Overall"
    with pytest.raises(phase.ContractError, match="duplicate result-set name"):
        validate(duplicate)

    unexpected = payload()
    unexpected["resultSets"][1]["name"] = "Other"
    with pytest.raises(phase.ContractError, match="membership mismatch"):
        validate(unexpected)


def test_malformed_result_set_duplicate_header_and_row_width_rejected():
    malformed = payload()
    malformed["resultSets"][1] = "Lineups"
    with pytest.raises(phase.ContractError, match="malformed result-set object"):
        validate(malformed)

    duplicate_header = payload()
    duplicate_header["resultSets"][1]["headers"][1] = "GROUP_SET"
    with pytest.raises(phase.ContractError, match="malformed Lineups headers"):
        validate(duplicate_header)

    wrong_width = payload()
    wrong_width["resultSets"][1]["rowSet"][0].pop()
    with pytest.raises(phase.ContractError, match="row-width mismatch"):
        validate(wrong_width)


def test_singleton_overall_and_established_order_required():
    multiple = payload()
    multiple["resultSets"][0]["rowSet"].append(
        deepcopy(multiple["resultSets"][0]["rowSet"][0])
    )
    with pytest.raises(phase.ContractError, match="exactly one"):
        validate(multiple)

    reversed_sets = payload()
    reversed_sets["resultSets"].reverse()
    with pytest.raises(phase.ContractError, match="Overall then Lineups"):
        validate(reversed_sets)


def test_exact_measure_specific_schemas_and_base_field_ownership():
    result = validate(payload("Base"))
    assert result["base_poss_absent_as_expected"] is True
    assert "POSS" not in phase.BASE_LINEUPS_HEADERS
    assert "NET_RATING" not in phase.BASE_LINEUPS_HEADERS
    assert {"GROUP_ID", "MIN", "SUM_TIME_PLAYED"} <= set(phase.BASE_LINEUPS_HEADERS)

    missing_exposure = payload("Base")
    index = missing_exposure["resultSets"][1]["headers"].index("SUM_TIME_PLAYED")
    missing_exposure["resultSets"][1]["headers"].pop(index)
    missing_exposure["resultSets"][1]["rowSet"][0].pop(index)
    with pytest.raises(phase.ContractError, match="exact frozen schema"):
        validate(missing_exposure)

    invalid_exposure = payload("Base")
    min_index = invalid_exposure["resultSets"][1]["headers"].index("MIN")
    invalid_exposure["resultSets"][1]["rowSet"][0][min_index] = -1
    with pytest.raises(phase.ContractError, match="Base MIN must be nonnegative"):
        validate(invalid_exposure)


def test_advanced_poss_and_net_rating_required_and_validated():
    valid = validate(payload("Advanced"), "Advanced")
    assert valid["measure"] == "Advanced"
    assert {"GROUP_ID", "POSS", "NET_RATING"} <= set(phase.ADVANCED_LINEUPS_HEADERS)

    for field in ("POSS", "NET_RATING"):
        missing = payload("Advanced")
        index = missing["resultSets"][1]["headers"].index(field)
        missing["resultSets"][1]["headers"].pop(index)
        missing["resultSets"][1]["rowSet"][0].pop(index)
        with pytest.raises(phase.ContractError, match="exact frozen schema"):
            validate(missing, "Advanced")

    for value in (None, "bad", "inf"):
        invalid = payload("Advanced")
        index = invalid["resultSets"][1]["headers"].index("POSS")
        invalid["resultSets"][1]["rowSet"][0][index] = value
        with pytest.raises(phase.ContractError, match="Advanced POSS"):
            validate(invalid, "Advanced")
    negative = payload("Advanced")
    poss = negative["resultSets"][1]["headers"].index("POSS")
    negative["resultSets"][1]["rowSet"][0][poss] = -0.1
    with pytest.raises(phase.ContractError, match="nonnegative"):
        validate(negative, "Advanced")

    invalid_target = payload("Advanced")
    target = invalid_target["resultSets"][1]["headers"].index("NET_RATING")
    invalid_target["resultSets"][1]["rowSet"][0][target] = "nan"
    with pytest.raises(phase.ContractError, match="Advanced NET_RATING"):
        validate(invalid_target, "Advanced")


def test_team_identity_uses_request_returned_parameters_and_overall_not_lineups():
    value = payload()
    assert "TEAM_ID" not in value["resultSets"][1]["headers"]
    result = validate(value)
    assert result["team_context"] == {
        "authorized_request": "1610612737",
        "returned_parameters": "1610612737",
        "overall_row": "1610612737",
    }

    no_returned_parameters = payload()
    no_returned_parameters.pop("parameters")
    result = validate(no_returned_parameters)
    assert set(result["team_context"]) == {"authorized_request", "overall_row"}

    returned_mismatch = payload()
    returned_mismatch["parameters"]["TeamID"] = 1610612738
    with pytest.raises(phase.ContractError, match="team identity mismatch"):
        validate(returned_mismatch)

    overall_mismatch = payload()
    team_index = overall_mismatch["resultSets"][0]["headers"].index("TEAM_ID")
    overall_mismatch["resultSets"][0]["rowSet"][0][team_index] = 1610612738
    with pytest.raises(phase.ContractError, match="team identity mismatch"):
        validate(overall_mismatch)


def test_canonical_pair_validation_duplicates_malformed_same_and_invalid_ids():
    assert phase.canonical_pair("-20-3-") == ("3", "20")
    duplicate = payload(pairs=((20, 3), (3, 20)))
    with pytest.raises(phase.ContractError, match="duplicate canonical"):
        validate(duplicate)
    for group_id, message in [
        ("bad", "malformed"),
        ("-3-3-", "same-player"),
        ("-03-20-", "malformed"),
        ("--20-", "malformed"),
    ]:
        value = payload()
        index = value["resultSets"][1]["headers"].index("GROUP_ID")
        value["resultSets"][1]["rowSet"][0][index] = group_id
        with pytest.raises(phase.ContractError, match=message):
            validate(value)


def test_exact_250_is_visible_and_unresolved_not_rejected():
    pairs = tuple((index + 1, index + 1001) for index in range(250))
    result = validate(payload(pairs=pairs))
    assert result["lineups_row_count"] == 250
    assert result["exact_250"] is True


def test_atlanta_offline_compatibility_expected_findings():
    auth = json.loads((PROJECT / "planning/phase3f-r2b/authorization.json").read_text())
    response = (
        PROJECT
        / "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-response.bin"
    ).read_bytes()
    result = phase.validate_response_contract(response, auth["authorized_requests"][0])
    assert result["strict_json_valid"] is True
    assert result["overall_header_count"] == 57
    assert result["overall_row_count"] == 1
    assert result["lineups_header_count"] == 56
    assert result["lineups_row_count"] == 200
    assert result["row_width_error_count"] == 0
    assert result["canonical_unordered_pair_count"] == 200
    assert result["duplicate_canonical_pair_count"] == 0
    assert result["malformed_group_identifier_count"] == 0
    assert result["same_player_pair_count"] == 0
    assert result["invalid_player_id_count"] == 0
    assert result["exact_250"] is False
    assert result["base_poss_absent_as_expected"] is True


def test_historical_60_response_schema_pinning():
    result = phase._validate_historical_2024_25(PROJECT)
    assert result["response_count"] == 60
    assert result["measure_counts"] == {"Advanced": 30, "Base": 30}
    assert result["result_set_order_counts"] == {"Overall,Lineups": 60}
    assert result["row_width_error_count"] == 0
    assert len(result["responses"]) == 60


def test_build_preserves_failure_and_freezes_future_eligibility(tmp_path):
    output = tmp_path / "specification"
    result = phase.build_specification(PROJECT, output)
    summary = json.loads((output / "summary.json").read_text())
    contract = json.loads((output / "response_contract.json").read_text())
    continuation = json.loads((output / "continuation_plan.json").read_text())
    assert result["classification"] == phase.CLASSIFICATION
    assert summary["original_r2b_status"].startswith("FAILED")
    assert summary["atlanta_remains_quarantined"] is True
    assert contract["permanent_historical_status"]["r2b_1_rewrites_or_repairs_failed_execution"] is False
    assert continuation["atlanta_base"]["network_eligible"] is False
    assert continuation["atlanta_base"]["second_attempt_allowed"] is False
    assert continuation["remaining_request_count"] == 59
    assert [item["ordinal"] for item in continuation["remaining_requests"]] == list(range(2, 61))
    assert all(item["currently_network_authorized"] is False for item in continuation["remaining_requests"])
    assert continuation["contains_executable_network_authorization"] is False
    assert continuation["rules"]["automatic_retries"] == 0
    assert continuation["rules"]["recovery_windows_authorized"] is False


def test_deterministic_build_and_populated_or_partial_namespace_refusal(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    phase.build_specification(PROJECT, first)
    phase.build_specification(PROJECT, second)
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    with pytest.raises(phase.ContractError, match="already exists"):
        phase.build_specification(PROJECT, first)
    empty = tmp_path / "empty-but-existing"
    empty.mkdir()
    with pytest.raises(phase.ContractError, match="already exists"):
        phase.build_specification(PROJECT, empty)
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "summary.json").write_text("{}")
    with pytest.raises(phase.ContractError, match="already exists"):
        phase.build_specification(PROJECT, partial)


def test_no_positional_selection_network_or_model_operations():
    sources = [
        PROJECT / "src/pair_fit_v2/phase3f_r2b_1_response_contract.py",
        PROJECT / "src/pair_fit_v2/phase3f_r2b_1_cli.py",
    ]
    forbidden_imports = {
        "requests", "urllib", "httpx", "aiohttp", "socket", "sklearn", "numpy",
        "pandas", "joblib", "pickle",
    }
    forbidden_calls = {"post", "request", "fit", "fit_transform", "predict", "score", "dump"}
    for source in sources:
        source_text = source.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
        }
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not imports & forbidden_imports
        assert not calls & forbidden_calls
        assert 'payload["resultSets"][0]' not in source_text
        assert "session" not in source_text.lower()
        assert "https://" not in source_text.lower()


def test_generated_inventory_is_exact_and_hash_manifest_is_correct(tmp_path):
    output = tmp_path / "specification"
    phase.build_specification(PROJECT, output)
    assert sorted(path.name for path in output.iterdir()) == sorted(phase.OUTPUT_FILES)
    hashes = json.loads((output / "artifact_hashes.json").read_text())
    assert set(hashes["artifacts"]) == set(phase.OUTPUT_FILES) - {"artifact_hashes.json"}
    for name, expected in hashes["artifacts"].items():
        raw = (output / name).read_bytes()
        assert expected == {"bytes": len(raw), "sha256": phase.sha256_bytes(raw)}
