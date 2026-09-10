import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3a1_shot_zone_acquisition as phase

CACHE = Path(__file__).parents[1] / "cache"

def payload(player="7", attempts=3):
    return {"resultSets":[{"name":z,"headers":["PLAYER_ID","TEAM_ID","FGM","FGA","FG_PCT"],"rowSet":[[player,"0",min(1,attempts),attempts,.3]]} for z in phase.EXPECTED_ZONES]}

def nested_payload(player="7"):
    categories=list(phase.EXPECTED_ZONES)+["Corner 3"]
    columns=["PLAYER_ID","PLAYER_NAME","TEAM_ID","TEAM_ABBREVIATION","AGE","NICKNAME"] + [x for _ in categories for x in ("FGM","FGA","FG_PCT")]
    triples=[[1,2,.5] for _ in categories]
    triples[3]=[None,None,None]
    triples[4]=[None,None,None]
    triples[7]=[None,None,None]
    row=[player,"P","0","NBA",20,"P"] + sum(triples,[])
    return {"resultSets":{"name":"ShotLocations","headers":[{"name":"SHOT_CATEGORY","columnsToSkip":6,"columnSpan":3,"columnNames":categories},{"name":"columns","columnSpan":1,"columnNames":columns}],"rowSet":[row]}}

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

def test_2013_discrepancy_diagnosis_is_deterministic_and_does_not_relax_exactness():
    first=phase.diagnose_2013_discrepancy(CACHE)
    second=phase.diagnose_2013_discrepancy(CACHE)
    assert first["deterministic_analysis_sha256"] == second["deterministic_analysis_sha256"]
    assert first["exact_matches"] == 441 and first["affected_players"] == 41
    assert first["aggregate_signed_differences"] == {"fgm":-13,"fga":-46}
    assert first["implementation_checks"]["backcourt_included"]
    assert first["implementation_checks"]["corner_aggregate_excluded_from_overall_sum"]
    assert first["implementation_checks"]["all_zone_totals_below_or_equal_base"]

def test_residual_policy_accepts_only_structurally_valid_nonnegative_residuals():
    body=nested_payload()
    totals={"7":{"FGM":5,"FGA":10,"TEAM_COUNT":0}}
    accepted=phase.audit_shot_payload(body,totals,policy=phase.STRICT_RECONCILIATION_POLICY)
    assert accepted["exact_count_players"] == 1
    assert accepted["aggregate_unclassified_fgm"] == 0
    assert accepted["affected_player_zone_cells"] == 3
    residual_totals=deepcopy(totals); residual_totals["7"]={"FGM":6,"FGA":12,"TEAM_COUNT":0}
    accepted=phase.audit_shot_payload(body,residual_totals,policy=phase.RESIDUAL_RECONCILIATION_POLICY)
    assert accepted["reconciliation_policy_id"] == "phase3a1.residual-v1"
    assert accepted["players_with_residuals"] == 1
    assert accepted["aggregate_unclassified_fgm"] == 1
    assert accepted["aggregate_unclassified_fga"] == 2
    with pytest.raises(ValueError,match="semantic reconciliation"):
        phase.audit_shot_payload(body,residual_totals,policy=phase.STRICT_RECONCILIATION_POLICY)
    for invalid in (None,"","phase3a1.residual-v2"):
        with pytest.raises(ValueError,match="unrecognized Phase 3A.1 reconciliation policy"):
            phase.audit_shot_payload(body,residual_totals,policy=invalid)
    negative=deepcopy(totals); negative["7"]={"FGM":5,"FGA":9,"TEAM_COUNT":0}
    with pytest.raises(ValueError,match="semantic reconciliation"):
        phase.audit_shot_payload(body,negative,policy=phase.RESIDUAL_RECONCILIATION_POLICY)
    makes_exceed=deepcopy(totals); makes_exceed["7"]={"FGM":6,"FGA":10,"TEAM_COUNT":0}
    with pytest.raises(ValueError,match="semantic reconciliation"):
        phase.audit_shot_payload(body,makes_exceed,policy=phase.RESIDUAL_RECONCILIATION_POLICY)

def test_invalid_acquisition_policy_stops_before_session_construction(tmp_path):
    constructed=[]
    def session_factory():
        constructed.append(True)
        raise AssertionError("session must not be constructed")
    with pytest.raises(ValueError,match="unrecognized Phase 3A.1 reconciliation policy"):
        phase.acquire(tmp_path,live=True,session_factory=session_factory,policy="phase3a1.residual-v2")
    assert not constructed
    assert not (tmp_path/"phase3a1").exists()

def test_residual_window_replay_is_deterministic_and_network_blocked():
    first=phase.analyze_residual_window(CACHE,policy=phase.RESIDUAL_RECONCILIATION_POLICY)
    second=phase.analyze_residual_window(CACHE,policy=phase.RESIDUAL_RECONCILIATION_POLICY)
    assert first["deterministic_analysis_sha256"] == second["deterministic_analysis_sha256"]
    assert first["reconciliation_policy_id"] == "phase3a1.residual-v1"
    assert first["seasons"]["2013-14"]["semantic_audit"]["aggregate_unclassified_fga"] == 46
    assert first["seasons"]["2023-24"]["semantic_audit"]["players_with_residuals"] == 0
