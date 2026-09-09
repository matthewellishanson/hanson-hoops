import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3a1_shot_zone_acquisition as phase

def payload(player="7", attempts=3):
    return {"resultSets":[{"name":z,"headers":["PLAYER_ID","TEAM_ID","FGM","FGA","FG_PCT"],"rowSet":[[player,"0",min(1,attempts),attempts,.3]]} for z in phase.EXPECTED_ZONES]}

def test_exact_authorized_order_allowlist_and_protected_seasons(tmp_path):
    plan=phase.planned(tmp_path)
    assert tuple(plan["order"]) == phase.SEASONS
    assert plan["order"][:2] == list(phase.CANARIES)
    assert len(plan["entries"]) == 11 and len({x["asset_id"] for x in plan["entries"]}) == 11
    with pytest.raises(ValueError): phase.identity("2024-25")

def test_identity_is_complete_and_exact():
    got=phase.request_parameters(phase.identity("2013-14"))
    assert got["Season"] == "2013-14" and got["DistanceRange"] == "By Zone"
    assert got["PerMode"] == "Totals" and got["MeasureType"] == "Base"
    assert got["PaceAdjust"] == got["PlusMinus"] == got["Rank"] == "N"
    assert got["LastNGames"] == "0" and got["DateFrom"] == got["DateTo"] == ""

def test_nested_headers_zone_identity_and_denominator_safety():
    parsed=phase.parse(payload(attempts=0))
    profile=parsed["profiles"]["7"]
    assert profile["represented_fga"] == 0 and profile["shares"]["Mid-Range"] is None
    bad=payload(); bad["resultSets"][0]["headers"].remove("FGA")
    with pytest.raises(ValueError,match="nested headers"): phase.parse(bad)
    bad=payload(); bad["resultSets"].pop()
    with pytest.raises(ValueError,match="zone structure"): phase.parse(bad)

def test_actual_nested_header_contract_is_parsed_by_category_not_position():
    categories=list(phase.EXPECTED_ZONES)+["Corner 3"]
    columns=["PLAYER_ID","PLAYER_NAME","TEAM_ID","TEAM_ABBREVIATION","AGE","NICKNAME"] + [x for _ in categories for x in ("FGM","FGA","FG_PCT")]
    row=["7","P","0","NBA",20,"P"] + sum(([1,2,.5] for _ in categories), [])
    actual={"resultSets":{"name":"ShotLocations","headers":[{"name":"SHOT_CATEGORY","columnsToSkip":6,"columnSpan":3,"columnNames":categories},{"name":"columns","columnSpan":1,"columnNames":columns}],"rowSet":[row]}}
    parsed=phase.parse(actual)
    assert parsed["result_set_headers"]["zone_categories"][-1] == "Corner 3"
    assert parsed["profiles"]["7"]["corner_three_fga"] == 4

def test_strict_ids_duplicates_and_nonadditive_grain_rejected():
    bad=payload(player="07")
    with pytest.raises(ValueError,match="PLAYER_ID"): phase.parse(bad)
    bad=payload(); bad["resultSets"][0]["rowSet"].append(["7","0",1,1,1])
    with pytest.raises(ValueError,match="duplicate"): phase.parse(bad)

def test_aggregate_counts_before_percentages():
    assert phase.safe_rate(3, 6) == .5
    assert phase.safe_rate(0, 0) is None
    assert phase.safe_rate(1, 0) is None

def test_immutable_storage_failure_body_and_interrupted_stop(tmp_path):
    phase.initialize(tmp_path)
    event={"season":"2023-24","attempt":1}
    stored=phase._persist_attempt(tmp_path,"2023-24",b'{"x":1}',event,quarantine=True)
    assert (tmp_path/stored["body_path"]).read_bytes() == b'{"x":1}'
    with pytest.raises(FileExistsError): phase._persist_attempt(tmp_path,"2023-24",b'{"x":2}',event,quarantine=True)

def test_cache_replay_network_prohibition_and_attempt_ceiling(tmp_path,monkeypatch):
    phase.initialize(tmp_path)
    manifest=phase.load(tmp_path,"manifest"); manifest["assets"][0]["status"]="verified"; manifest["assets"][0]["cache"]={"body_path":"phase3a1/raw/missing.json"}
    ledger=phase.load(tmp_path,"ledger"); phase._write_state(tmp_path,manifest,ledger)
    with pytest.raises(RuntimeError,match="network prohibited"):
        with phase.network_prohibited(): __import__("requests").Session()
    assert phase.MAX_ATTEMPTS == phase.MAX_FIRST_ATTEMPTS + phase.MAX_RETRIES

def test_schema_drift_and_reconciliation_summary(tmp_path,monkeypatch):
    body=json.dumps(payload()).encode()
    monkeypatch.setattr(phase,"_base_profiles",lambda root:{"2013-14":{"7":{"TOTAL_MIN":10},"9":{}}})
    summary=phase.analyze_payload(payload(),body,"2013-14",tmp_path)
    assert summary["reconciliation"]["matched_player_ids"] == 1
    assert summary["reconciliation"]["base_only_player_ids"] == ["9"]
    drift=payload(); drift["resultSets"][0]["name"]="Different"
    with pytest.raises(ValueError,match="zone structure"): phase.parse(drift)
