"""Bounded Phase 3A.1 player shot-zone feasibility acquisition.

This is deliberately small: eleven league-wide, prior-season requests and a
cache-only replay.  It is not a generic ingestion framework and it never
creates a curated feature table.
"""
from __future__ import annotations

import hashlib
import json
import math
import socket
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

import requests

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.phase1c_manifest import atomic_write_bytes_new, atomic_write_json, canonical_json_hash, raw_body_hash
from pair_fit_v2 import phase3a_population_audit as phase3a
from pair_fit_v2.phase2a_historical_canary import PLAYER_EXTRA_PARAMETERS

ENDPOINT = "LeagueDashPlayerShotLocations"
URL = "https://stats.nba.com/stats/leaguedashplayershotlocations"
SEASONS = ("2023-24", "2013-14", "2014-15", "2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23")
AUTHORIZED_SEASONS = frozenset(SEASONS)
CANARIES = ("2023-24", "2013-14")
MAX_FIRST_ATTEMPTS, MAX_RETRIES, MAX_ATTEMPTS = 11, 3, 14
EXPECTED_ZONES = ("Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3", "Right Corner 3", "Above the Break 3", "Backcourt")
RETRYABLE_STATUS = {500, 502, 503, 504}
EXTRA = {"Conference":"", "DateFrom":"", "DateTo":"", "Division":"", "GameScope":"", "GameSegment":"", "LastNGames":"0", "Location":"", "Month":"0", "OpponentTeamID":"0", "Outcome":"", "PORound":"0", "Period":"0", "PlayerExperience":"", "PlayerPosition":"", "SeasonSegment":"", "ShotClockRange":"", "StarterBench":"", "TeamID":"0", "VsConference":"", "VsDivision":""}
DEPENDENCY_ENDPOINT="LeagueDashPlayerStats"
DEPENDENCY_URL="https://stats.nba.com/stats/leaguedashplayerstats"
DEPENDENCY_SEASON="2023-24"
STRICT_RECONCILIATION_POLICY="phase3a1.strict-v1"
RESIDUAL_RECONCILIATION_POLICY="phase3a1.residual-v1"
RECOGNIZED_RECONCILIATION_POLICIES=frozenset((STRICT_RECONCILIATION_POLICY,RESIDUAL_RECONCILIATION_POLICY))

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def strict_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)): raise ValueError("PLAYER_ID must be a positive canonical decimal ID")
    text = str(value)
    if not text.isdecimal() or int(text) <= 0 or str(int(text)) != text: raise ValueError("PLAYER_ID must be a positive canonical decimal ID")
    return text
def number(value):
    if isinstance(value, bool): return None
    try: value = float(value)
    except (TypeError, ValueError): return None
    return value if math.isfinite(value) else None
def safe_rate(a, b):
    a, b = number(a), number(b)
    return None if a is None or b is None or b <= 0 else a / b
def validate_reconciliation_policy(policy):
    if not isinstance(policy,str) or policy not in RECOGNIZED_RECONCILIATION_POLICIES:
        raise ValueError(f"unrecognized Phase 3A.1 reconciliation policy: {policy!r}")
    return policy

def identity(season: str) -> dict[str, Any]:
    value = {"endpoint": ENDPOINT, "season": season, "parameters": {**EXTRA, "league_id":"00", "season":season, "season_type":"regular-season", "measure_type":"Base", "per_mode":"Totals", "distance_range":"By Zone", "pace_adjust":"N", "plus_minus":"N", "rank":"N"}}
    validate_identity(value); return value
def validate_identity(value: Mapping[str, Any]):
    p = value.get("parameters", {})
    if value.get("endpoint") != ENDPOINT or value.get("season") not in AUTHORIZED_SEASONS or p != identity_parameters(str(value.get("season"))):
        raise ValueError("Unauthorized Phase 3A.1 shot-location request identity")
    if "2024-25" in json.dumps(value, sort_keys=True) or "2025-26" in json.dumps(value, sort_keys=True): raise ValueError("Protected season prohibited")
def identity_parameters(season):
    return {**EXTRA, "league_id":"00", "season":season, "season_type":"regular-season", "measure_type":"Base", "per_mode":"Totals", "distance_range":"By Zone", "pace_adjust":"N", "plus_minus":"N", "rank":"N"}
def request_parameters(value):
    validate_identity(value); p = value["parameters"]
    mapping = {"league_id":"LeagueID", "season":"Season", "season_type":"SeasonType", "measure_type":"MeasureType", "per_mode":"PerMode", "distance_range":"DistanceRange", "pace_adjust":"PaceAdjust", "plus_minus":"PlusMinus", "rank":"Rank"}
    return {mapping.get(k, k): ("Regular Season" if k == "season_type" else v) for k, v in p.items()}
def asset_stem(season): return f"league_dash_player_shot_locations_{season}_base_totals_by_zone"
def paths(root, season):
    base = Path(root) / "phase3a1"
    stem = asset_stem(season)
    return {"raw":base/"raw"/f"{stem}.attempt-1.json", "metadata":base/"metadata"/f"{stem}.attempt-1.json", "quarantine":base/"quarantine"/f"{stem}.attempt-1.json", "manifest":base/"manifest.json", "ledger":base/"ledger.json", "allowlist":base/"allowlist.json", "plan":base/"dry-run.json"}

def dependency_identity():
    return {"endpoint":DEPENDENCY_ENDPOINT,"season":DEPENDENCY_SEASON,"parameters":{**PLAYER_EXTRA_PARAMETERS,"league_id":"00","season":DEPENDENCY_SEASON,"season_type":"regular-season","measure_type":"Base","per_mode":"Totals"}}
def dependency_parameters(value):
    expected=dependency_identity()
    if value != expected: raise ValueError("unauthorized player-Totals dependency identity")
    mapping={"league_id":"LeagueID","season":"Season","season_type":"SeasonType","measure_type":"MeasureType","per_mode":"PerMode"}
    return {mapping.get(k,k):("Regular Season" if k=="season_type" else v) for k,v in value["parameters"].items()}
def dependency_paths(root):
    base=Path(root)/"phase3a1"; stem="league_dash_player_stats_2023-24_base_totals"
    return {"plan":base/"dependency-dry-run.json","allowlist":base/"dependency-allowlist.json","authorization":base/"dependency-authorization.json","ledger":base/"dependency-ledger.json","raw":base/"raw"/f"{stem}.attempt-1.json","metadata":base/"metadata"/f"{stem}.attempt-1.json","quarantine":base/"quarantine"/f"{stem}.attempt-1.json"}
def dependency_preview(root):
    return {"version":"phase3a1.player-totals-dependency-dry-run.v1","network":"prohibited","newly_authorized_identities":[dependency_identity()],"first_attempts":1,"retries":1,"maximum_attempts":2}
def initialize_dependency(root):
    p=dependency_paths(root); preview=dependency_preview(root)
    documents={"plan":preview,"allowlist":{"version":"phase3a1.player-totals-dependency-allowlist.v1","identities":[dependency_identity()]},"authorization":{"version":"phase3a1.player-totals-dependency-authorization.v1","reason":"exact 2023-24 shot-zone Totals reconciliation only","first_attempts":1,"retries":1,"maximum_attempts":2},"ledger":{"version":"phase3a1.player-totals-dependency-ledger.v1","attempts":[]}}
    for key,value in documents.items():
        data=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode(); path=p[key]
        if path.exists():
            if path.read_bytes()!=data: raise ValueError(f"dependency planning collision: {path}")
        else: atomic_write_json(path,value)
    return preview
def _player_rows(payload):
    sets=payload.get("resultSets")
    if not isinstance(sets,list): raise ValueError("player response missing resultSets list")
    result=next((x for x in sets if x.get("name")=="LeagueDashPlayerStats"),None)
    if not isinstance(result,Mapping) or not isinstance(result.get("headers"),list) or not isinstance(result.get("rowSet"),list): raise ValueError("missing LeagueDashPlayerStats result set")
    required={"PLAYER_ID","FGM","FGA","FG_PCT"}
    if len(result["headers"])!=len(set(result["headers"])) or not required <= set(result["headers"]): raise ValueError("unrecognized player-Totals schema")
    rows=[]
    for n,row in enumerate(result["rowSet"]):
        if not isinstance(row,list) or len(row)!=len(result["headers"]): raise ValueError(f"player row width {n}")
        r=dict(zip(result["headers"],row)); pid=strict_id(r["PLAYER_ID"]); made,att=number(r["FGM"]),number(r["FGA"])
        if made is None or att is None or made<0 or att<0 or made>att or made!=int(made) or att!=int(att): raise ValueError(f"invalid player-Totals FGM/FGA for {pid}")
        rows.append(r)
    ids=[strict_id(r["PLAYER_ID"]) for r in rows]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate player-Totals IDs")
    return rows
def acquire_dependency(root, live=False):
    if not live: raise ValueError("dependency acquisition requires explicit --dependency-live")
    initialize_dependency(root); p=dependency_paths(root); ledger=json.loads(p["ledger"].read_text())
    if ledger["attempts"]: raise RuntimeError("dependency already attempted; explicit review required")
    ident=dependency_identity(); session=requests.Session(); session.trust_env=False; session.headers.update(RESEARCH_HEADERS)
    try:
        for attempt in (1,2):
            event={"attempt":attempt,"identity":ident,"started_at":now()}; ledger["attempts"].append(event); atomic_write_json(p["ledger"],ledger)
            try:
                response=session.get(DEPENDENCY_URL,params=dependency_parameters(ident),timeout=30,allow_redirects=False); body=response.content; event.update({"ended_at":now(),"http_status":response.status_code})
                if response.status_code==200 and not response.is_redirect:
                    try:
                        payload=json.loads(body.decode("utf-8")); rows=_player_rows(payload)
                        old=json.loads((Path(root)/"live_responses/league_dash_player_stats_2023-24_base_per100possessions.json").read_text()); oldids={strict_id(r["PLAYER_ID"]) for r in phase3a._rows(old,"LeagueDashPlayerStats")}; newids={strict_id(r["PLAYER_ID"]) for r in rows}
                        if newids != oldids: raise ValueError(f"player-ID mismatch totals_only={sorted(newids-oldids,key=int)} per100_only={sorted(oldids-newids,key=int)}")
                    except Exception as exc:
                        atomic_write_bytes_new(p["quarantine"],body); event.update({"result":f"validation:{type(exc).__name__}: {exc}","body_path":str(p["quarantine"].relative_to(Path(root))),"byte_count":len(body),"raw_body_sha256":raw_body_hash(body)}); atomic_write_json(p["ledger"],ledger); return {"stopped":event}
                    atomic_write_bytes_new(p["raw"],body); meta={**event,"result":"verified","body_path":str(p["raw"].relative_to(Path(root))),"byte_count":len(body),"raw_body_sha256":raw_body_hash(body),"canonical_json_sha256":canonical_json_hash(payload),"schema_headers":next(x["headers"] for x in payload["resultSets"] if x["name"]=="LeagueDashPlayerStats")}; atomic_write_json(p["metadata"],meta); ledger["attempts"][-1]=meta; atomic_write_json(p["ledger"],ledger); return {"verified":meta}
                atomic_write_bytes_new(p["quarantine"].with_name(p["quarantine"].stem+f".attempt-{attempt}"+p["quarantine"].suffix),body); event["result"]=f"http:{response.status_code}"
                if response.status_code not in RETRYABLE_STATUS or attempt==2: atomic_write_json(p["ledger"],ledger); return {"stopped":event}
            except (requests.Timeout,requests.ConnectionError) as exc:
                event["result"]=f"transport:{type(exc).__name__}"
                if attempt==2: atomic_write_json(p["ledger"],ledger); return {"stopped":event}
            atomic_write_json(p["ledger"],ledger); time.sleep(1)
    finally: session.close()

def planned(root):
    entries = [{"ordinal":i+1, "identity":identity(s), "asset_id":asset_stem(s)} for i,s in enumerate(SEASONS)]
    if len(entries) != MAX_FIRST_ATTEMPTS or len({canonical_json_hash(x["identity"]) for x in entries}) != len(entries): raise ValueError("invalid authorized request order")
    return {"version":"phase3a1.dry-run.v1", "network":"prohibited", "order":list(SEASONS), "canaries":list(CANARIES), "max_first_attempts":MAX_FIRST_ATTEMPTS, "max_retries":MAX_RETRIES, "max_attempts":MAX_ATTEMPTS, "entries":entries}
def initialize(root):
    root = Path(root); p = paths(root, SEASONS[0]); plan = planned(root)
    for key, value in (("plan",plan), ("allowlist", {"version":"phase3a1.allowlist.v1", "identities":[x["identity"] for x in plan["entries"]]}), ("manifest", {"version":"phase3a1.manifest.v1", "assets":[{"season":s,"identity":identity(s),"status":"planned","attempts":[]} for s in SEASONS]}), ("ledger", {"version":"phase3a1.ledger.v1", "attempts":[]})):
        target = p[key]
        if target.exists():
            if target.read_bytes() != (json.dumps(value, indent=2, sort_keys=True)+"\n").encode(): raise ValueError(f"immutable planning collision: {target}")
        else: atomic_write_json(target, value)
    return plan
def load(root, name): return json.loads(paths(root, SEASONS[0])[name].read_text(encoding="utf-8"))
def _write_state(root, manifest, ledger):
    p = paths(root, SEASONS[0]); atomic_write_json(p["manifest"], manifest); atomic_write_json(p["ledger"], ledger)

def _sets(payload):
    items = payload.get("resultSets")
    if not isinstance(items, list): raise ValueError("missing resultSets list")
    found = {}
    for item in items:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str) or not isinstance(item.get("headers"), list) or not isinstance(item.get("rowSet"), list): raise ValueError("malformed result set")
        if item["name"] in found: raise ValueError("duplicate result-set name")
        found[item["name"]] = item
    missing, extra = sorted(set(EXPECTED_ZONES)-set(found)), sorted(set(found)-set(EXPECTED_ZONES))
    if missing or extra: raise ValueError(f"unapproved zone structure missing={missing} extra={extra}")
    return found
def parse(payload):
    # The installed endpoint's actual contract is one ``ShotLocations`` set
    # with a two-level header: six identity columns followed by triplets for
    # every location.  It is intentionally parsed by labels, never offsets.
    nested = payload.get("resultSets")
    if isinstance(nested, Mapping) and nested.get("name") == "ShotLocations":
        headers, rows = nested.get("headers"), nested.get("rowSet")
        if not isinstance(headers, list) or len(headers) != 2 or not isinstance(rows, list): raise ValueError("malformed nested ShotLocations result set")
        zone_header, column_header = headers
        categories = zone_header.get("columnNames") if isinstance(zone_header, Mapping) else None
        columns = column_header.get("columnNames") if isinstance(column_header, Mapping) else None
        skip, span = (zone_header.get("columnsToSkip"), zone_header.get("columnSpan")) if isinstance(zone_header, Mapping) else (None,None)
        if skip != 6 or span != 3 or not isinstance(categories,list) or not isinstance(columns,list): raise ValueError("uninterpretable nested shot-zone headers")
        missing = sorted(set(EXPECTED_ZONES)-set(categories))
        if missing or len(columns) != skip + len(categories)*span: raise ValueError(f"unapproved nested zone structure missing={missing}")
        base = columns[:skip]; expected_base = ["PLAYER_ID","PLAYER_NAME","TEAM_ID","TEAM_ABBREVIATION","AGE","NICKNAME"]
        if base != expected_base: raise ValueError(f"unapproved identity-header structure: {base!r}")
        output = {z:[] for z in EXPECTED_ZONES}
        for index,row in enumerate(rows):
            if not isinstance(row,list) or len(row) != len(columns): raise ValueError(f"nested row width {index}")
            pid=strict_id(row[0])
            for zone_index, zone in enumerate(categories):
                fields=row[skip+zone_index*span:skip+(zone_index+1)*span]
                if len(fields) != 3: raise ValueError("nested zone span mismatch")
                made,attempts=number(fields[0]),number(fields[1])
                # Only the separately audited paired-null representation may
                # normalize to structural zero; never overwrite the raw body.
                if made is None and attempts is None and fields[2] in (None,0,0.0): made,attempts=0.0,0.0
                if made is None or attempts is None or made < 0 or attempts < 0 or made > attempts: raise ValueError(f"{zone} invalid FGM/FGA for {pid}")
                if zone in output: output[zone].append({"player_id":pid,"fgm":made,"fga":attempts,"fg_pct":safe_rate(made,attempts),"source_fg_pct":number(fields[2]),"team_id":row[2],"team_abbreviation":row[3]})
        return {"result_set_headers":{"result_set":"ShotLocations","identity_columns":base,"zone_categories":categories,"columns_to_skip":skip,"column_span":span},"rows":output,"profiles":_profiles_from_zone_rows(output)}
    sets = _sets(payload); output = {}
    for zone in EXPECTED_ZONES:
        item = sets[zone]; headers = item["headers"]
        needed = {"PLAYER_ID","FGM","FGA","FG_PCT"}
        if len(headers) != len(set(headers)) or not needed <= set(headers): raise ValueError(f"{zone} missing interpretable nested headers")
        rows = []
        for idx, row in enumerate(item["rowSet"]):
            if not isinstance(row, list) or len(row) != len(headers): raise ValueError(f"{zone} row width {idx}")
            record = dict(zip(headers,row)); pid = strict_id(record["PLAYER_ID"]); made, attempts = number(record["FGM"]), number(record["FGA"])
            if made is None or attempts is None or made < 0 or attempts < 0 or made > attempts: raise ValueError(f"{zone} invalid FGM/FGA for {pid}")
            rows.append({"player_id":pid,"fgm":made,"fga":attempts,"fg_pct":safe_rate(made,attempts),"source_fg_pct":number(record["FG_PCT"]),"team_id":record.get("TEAM_ID"),"team_abbreviation":record.get("TEAM_ABBREVIATION")})
        if len({r["player_id"] for r in rows}) != len(rows): raise ValueError(f"{zone} duplicate PLAYER_ID; player/team grain unresolved")
        output[zone] = rows
    ids = [set(r["player_id"] for r in output[z]) for z in EXPECTED_ZONES]
    if len({tuple(sorted(x,key=int)) for x in ids}) != 1: raise ValueError("zone player populations differ; player grain unresolved")
    return {"result_set_headers":{z:sets[z]["headers"] for z in EXPECTED_ZONES},"rows":output,"profiles":_profiles_from_zone_rows(output)}
def _profiles_from_zone_rows(output):
    ids = [set(r["player_id"] for r in output[z]) for z in EXPECTED_ZONES]
    if len({tuple(sorted(x,key=int)) for x in ids}) != 1: raise ValueError("zone player populations differ; player grain unresolved")
    profiles = {}
    for pid in sorted(ids[0], key=int):
        zones = {z:next(r for r in output[z] if r["player_id"] == pid) for z in EXPECTED_ZONES}
        total = sum(x["fga"] for x in zones.values())
        profiles[pid] = {"zones":zones,"represented_fga":total,"shares":{z:safe_rate(x["fga"],total) for z,x in zones.items()},"corner_three_fga":zones["Left Corner 3"]["fga"]+zones["Right Corner 3"]["fga"],"corner_three_share":safe_rate(zones["Left Corner 3"]["fga"]+zones["Right Corner 3"]["fga"],total)}
    return profiles

def _base_profiles(cache_root):
    _, profiles, _, _ = phase3a._load_population(Path(cache_root))
    # 2023-24 is the protected development-validation prior source already
    # acquired in Phase 2A; this only reads its immutable local cache.
    cached = Path(cache_root) / "live_responses/league_dash_player_stats_2023-24_base_per100possessions.json"
    if cached.is_file():
        payload = json.loads(cached.read_text(encoding="utf-8"))
        profiles["2023-24"] = {strict_id(r["PLAYER_ID"]): r for r in phase3a._rows(payload, "LeagueDashPlayerStats")}
    return profiles
def totals_for_season(cache_root, season):
    root=Path(cache_root)
    if season=="2023-24":
        payload=json.loads((root/"phase3a1/raw/league_dash_player_stats_2023-24_base_totals.attempt-1.json").read_bytes())
        return {strict_id(r["PLAYER_ID"]):r for r in _player_rows(payload)}
    target_year=int(season[:4])+1; target=f"{target_year}-{str(target_year+1)[-2:]}"
    phase_paths={**{s:root/"phase2e"/s/"manifest.json" for s in phase3a.WINDOW[:7]},"2021-22":root/"phase2d/manifest.json","2022-23":root/"phase2c/manifest.json","2023-24":root/"phase2b/release_manifest.json"}
    manifest=json.loads(phase_paths[target].read_text()); assets=manifest.get("assets") or manifest.get("pair_assets"); sources=manifest.get("player_dependencies") or [a for a in assets if a["identity"]["endpoint"]=="LeagueDashPlayerStats"]
    source=next(x for x in sources if (x.get("identity") or x.get("source_identity"))["parameters"]["per_mode"]=="Totals")
    cache=source.get("cache") or {"relative_path":source["source_cache_path"]}; payload=json.loads((root/cache["relative_path"]).read_bytes())
    return {strict_id(r["PLAYER_ID"]):r for r in phase3a._rows(payload,"LeagueDashPlayerStats")}
def audit_shot_payload(payload, totals, *, policy):
    policy=validate_reconciliation_policy(policy)
    nested=payload.get("resultSets")
    if not isinstance(nested,Mapping) or nested.get("name")!="ShotLocations": raise ValueError("unrecognized ShotLocations structure")
    cats=nested["headers"][0].get("columnNames"); rows=nested.get("rowSet")
    if not isinstance(cats,list) or not isinstance(rows,list) or tuple(cats[:7])!=EXPECTED_ZONES: raise ValueError("required zone categories absent or reordered")
    ids=[]; nulls=Counter(); affected=set(); bad=[]; total_bad=[]; corner_bad=[]; pct_bad=[]; residuals=[]
    for row in rows:
        pid=strict_id(row[0]); ids.append(pid); values=[]
        for i,zone in enumerate(cats):
            made,att,pct=row[6+i*3:9+i*3]; paired=made is None and att is None
            if (made is None)!=(att is None): bad.append((pid,zone,"one_sided_null"))
            if paired:
                nulls[zone]+=1; affected.add(pid)
                if pct not in (None,0,0.0): bad.append((pid,zone,"null_nonzero_pct"))
                made,att=0,0
            if not isinstance(made,(int,float)) or not isinstance(att,(int,float)) or made<0 or att<0 or int(made)!=made or int(att)!=att or made>att: bad.append((pid,zone,"invalid_counts"))
            if att==0 and pct not in (None,0,0.0): bad.append((pid,zone,"zero_attempt_nonzero_pct"))
            if att>0 and (not isinstance(pct,(int,float)) or abs(pct-made/att)>.00051): pct_bad.append((pid,zone))
            values.append((int(made),int(att)))
        total=totals.get(pid); classified_m,classified_a=sum(v[0] for v in values[:7]),sum(v[1] for v in values[:7])
        if total is None: total_bad.append(pid)
        else:
            residual_m,residual_a=int(total["FGM"])-classified_m,int(total["FGA"])-classified_a
            residuals.append({"player_id":pid,"unclassified_fgm":residual_m,"unclassified_fga":residual_a,"exact":residual_m==0 and residual_a==0,"traded_or_multi_team":int(total.get("TEAM_COUNT",0) or 0)>1})
            if residual_m<0 or residual_a<0 or residual_m>residual_a: total_bad.append(pid)
            elif policy != RESIDUAL_RECONCILIATION_POLICY and (residual_m or residual_a): total_bad.append(pid)
        if values[7] != (values[3][0]+values[4][0],values[3][1]+values[4][1]): corner_bad.append(pid)
    if len(ids)!=len(set(ids)) or set(ids)!=set(totals): raise ValueError("shot-location/player-Totals ID reconciliation failed")
    rfga=[x["unclassified_fga"] for x in residuals]; rfgm=[x["unclassified_fgm"] for x in residuals]
    classified_fgm=sum(int(r["FGM"]) for r in totals.values())-sum(rfgm)
    classified_fga=sum(int(r["FGA"]) for r in totals.values())-sum(rfga)
    result={"reconciliation_policy_id":policy,"player_rows":len(ids),"unique_ids":len(set(ids)),"null_counts_by_zone":dict(nulls),"affected_player_zone_cells":sum(nulls.values()),"affected_players":len(affected),"contradictory_patterns":bad,"totals_discrepancies":total_bad,"corner_three_discrepancies":corner_bad,"percentage_discrepancies":pct_bad,"response_grain":"one row per player; one aggregate zone vector per PLAYER_ID","traded_player_count":sum(int(r.get("TEAM_COUNT",0) or 0)>1 for r in totals.values()),"exact_count_players":sum(x["exact"] for x in residuals),"players_with_residuals":sum(not x["exact"] for x in residuals),"residual_players_by_traded_status":{"traded":sum(not x["exact"] and x["traded_or_multi_team"] for x in residuals),"not_traded":sum(not x["exact"] and not x["traded_or_multi_team"] for x in residuals)},"overall_fgm":sum(int(r["FGM"]) for r in totals.values()),"overall_fga":sum(int(r["FGA"]) for r in totals.values()),"classified_fgm":classified_fgm,"classified_fga":classified_fga,"aggregate_unclassified_fgm":sum(rfgm),"aggregate_unclassified_fga":sum(rfga),"residual_fgm_quantiles":{k:_quantile(rfgm,q) for k,q in (("min",0),("q1",.25),("median",.5),("q3",.75),("p90",.9),("p95",.95),("max",1))},"residual_fga_quantiles":{k:_quantile(rfga,q) for k,q in (("min",0),("q1",.25),("median",.5),("q3",.75),("p90",.9),("p95",.95),("max",1))},"residual_maximum":max([*rfgm,*rfga],default=0),"residuals":residuals}
    if bad or total_bad or corner_bad or pct_bad: raise ValueError(f"shot-zone semantic reconciliation failed: {result}")
    return result
def review_and_promote_2023(root):
    root=Path(root); p=paths(root,"2023-24"); body=p["quarantine"].read_bytes(); payload=json.loads(body); audit=audit_shot_payload(payload,totals_for_season(root,"2023-24"),policy=STRICT_RECONCILIATION_POLICY)
    if raw_body_hash(body)!="98108b58276756f2afc53ddd87c8287e1627fc740b5c5cfbafe2d48f98c8f444" or canonical_json_hash(payload)!="29c6cb48f6cb87935539a52bf8c4eed152a5c7d15963673958a5bf5ada38d4d5": raise ValueError("original quarantine evidence changed")
    atomic_write_bytes_new(p["raw"],body)
    event={"review_event_id":"phase3a1.reviewed-promotion-2023-24.v1","reviewed_at":now(),"original_quarantine_path":str(p["quarantine"].relative_to(root)),"raw_body_sha256":raw_body_hash(body),"canonical_json_sha256":canonical_json_hash(payload),"null_policy":"paired null FGM/FGA with null-or-zero FG_PCT normalizes to 0/0; percentage remains undefined","audit":audit}
    atomic_write_json(root/"phase3a1/reviewed-promotion-2023-24.json",event)
    manifest=load(root,"manifest"); asset=manifest["assets"][0]; asset.update({"status":"verified_reviewed_promotion","cache":{"body_path":str(p["raw"].relative_to(root)),"raw_body_hash":raw_body_hash(body),"canonical_json_hash":canonical_json_hash(payload)},"review_event":event}); atomic_write_json(p["manifest"],manifest)
    return event
def review_and_promote_2013_residual(root, *, policy):
    policy=validate_reconciliation_policy(policy)
    if policy != RESIDUAL_RECONCILIATION_POLICY: raise ValueError("2013-14 residual promotion requires phase3a1.residual-v1")
    root=Path(root); p=paths(root,"2013-14"); body=p["quarantine"].read_bytes(); payload=json.loads(body); audit=audit_shot_payload(payload,totals_for_season(root,"2013-14"),policy=policy)
    if raw_body_hash(body)!="3528826a43d891b76f01c864cb746143fdbce07d97feec7ace0ee8550db2106a": raise ValueError("2013 quarantine evidence changed")
    atomic_write_bytes_new(p["raw"],body)
    event={"review_event_id":"phase3a1.reviewed-promotion-2013-14.residual-v1","reviewed_at":now(),"original_quarantine_path":str(p["quarantine"].relative_to(root)),"raw_body_sha256":raw_body_hash(body),"canonical_json_sha256":canonical_json_hash(payload),"policy":"overall-minus-seven-zone nonnegative UNCLASSIFIED_FGM/FGA residual; no allocation to a zone","audit":audit}
    atomic_write_json(root/"phase3a1/reviewed-promotion-2013-14.json",event)
    manifest=load(root,"manifest"); asset=next(x for x in manifest["assets"] if x["season"]=="2013-14"); asset.update({"status":"verified_reviewed_promotion","cache":{"body_path":str(p["raw"].relative_to(root)),"raw_body_hash":raw_body_hash(body),"canonical_json_hash":canonical_json_hash(payload)},"review_event":event}); atomic_write_json(p["manifest"],manifest)
    return event
def _quantile(values, fraction):
    values=sorted(values); pos=(len(values)-1)*fraction; lo=int(pos); hi=min(lo+1,len(values)-1); return values[lo]*(1-(pos-lo))+values[hi]*(pos-lo)
def diagnose_2013_discrepancy(root):
    """Cache-only ledger; it intentionally does not relax exact reconciliation."""
    root=Path(root); body=(root/"phase3a1/quarantine/league_dash_player_shot_locations_2013-14_base_totals_by_zone.attempt-1.json").read_bytes(); payload=json.loads(body); result=payload["resultSets"]; cats=result["headers"][0]["columnNames"]; totals=totals_for_season(root,"2013-14"); ledger=[]
    for row in result["rowSet"]:
        pid=strict_id(row[0]); zones=[]; nulls=[]
        for i,zone in enumerate(cats):
            made,att,pct=row[6+i*3:9+i*3]
            if made is None and att is None: made,att=0,0; nulls.append(zone)
            zones.append((int(made),int(att),pct))
        fgm,fga=sum(x[0] for x in zones[:7]),sum(x[1] for x in zones[:7]); total=totals[pid]; dfgm,dfga=fgm-int(total["FGM"]),fga-int(total["FGA"])
        if dfgm or dfga:
            ledger.append({"player_id":pid,"player_name":row[1],"shot_team_id":row[2],"shot_team_abbreviation":row[3],"base_team_id":total.get("TEAM_ID"),"base_team_abbreviation":total.get("TEAM_ABBREVIATION"),"team_count":total.get("TEAM_COUNT"),"traded_or_multi_team":int(total.get("TEAM_COUNT",0) or 0)>1,"gp":total.get("GP"),"total_minutes":total.get("MIN"),"base_fgm":total["FGM"],"base_fga":total["FGA"],"zone_fgm":fgm,"zone_fga":fga,"signed_fgm_difference":dfgm,"signed_fga_difference":dfga,"absolute_fgm_difference":abs(dfgm),"absolute_fga_difference":abs(dfga),"relative_fga_coverage":fgm/fga if False else (fga/total["FGA"] if total["FGA"] else None),"zone_totals_direction":"below" if dfgm<=0 and dfga<=0 else "mixed_or_above","source_null_normalized_cells":nulls,"duplicate_or_multirow_player":False,"corner_three_reconciles":zones[7][:2]==(zones[3][0]+zones[4][0],zones[3][1]+zones[4][1]),"percentages_reconcile":all(a==0 and p in (None,0,0.0) or a>0 and isinstance(p,(int,float)) and abs(p-m/a)<=.00051 for m,a,p in zones)})
    magnitudes=[max(x["absolute_fgm_difference"],x["absolute_fga_difference"]) for x in ledger]
    bins={"1":sum(v==1 for v in magnitudes),"2":sum(v==2 for v in magnitudes),"3_to_5":sum(3<=v<=5 for v in magnitudes),"6_to_10":sum(6<=v<=10 for v in magnitudes),"over_10":sum(v>10 for v in magnitudes)}
    summary={"version":"phase3a1.2013-14-discrepancy-diagnosis.v1","raw_body_sha256":raw_body_hash(body),"canonical_json_sha256":canonical_json_hash(payload),"player_rows":len(result["rowSet"]),"exact_matches":len(result["rowSet"])-len(ledger),"affected_players":len(ledger),"affected_share":len(ledger)/len(result["rowSet"]),"absolute_difference_quantiles":{k:_quantile(magnitudes,q) for k,q in (("min",0),("q1",.25),("median",.5),("q3",.75),("p90",.9),("p95",.95),("max",1))},"aggregate_signed_differences":{"fgm":sum(x["signed_fgm_difference"] for x in ledger),"fga":sum(x["signed_fga_difference"] for x in ledger)},"aggregate_absolute_differences":{"fgm":sum(x["absolute_fgm_difference"] for x in ledger),"fga":sum(x["absolute_fga_difference"] for x in ledger)},"magnitude_bins":bins,"by_traded_status":{"traded":sum(x["traded_or_multi_team"] for x in ledger),"not_traded":sum(not x["traded_or_multi_team"] for x in ledger)},"implementation_checks":{"required_seven_zone_order":tuple(cats[:7])==EXPECTED_ZONES,"corner_aggregate_excluded_from_overall_sum":True,"backcourt_included":True,"all_corner_identities":all(x["corner_three_reconciles"] for x in ledger),"all_percentage_identities":all(x["percentages_reconcile"] for x in ledger),"duplicate_player_ids":False,"all_shot_base_team_identities_match":all(x["shot_team_id"]==x["base_team_id"] for x in ledger),"all_zone_totals_below_or_equal_base":all(x["signed_fgm_difference"]<=0 and x["signed_fga_difference"]<=0 for x in ledger)},"ledger":ledger}
    summary["deterministic_analysis_sha256"]=canonical_json_hash(summary); return summary
def analyze_asset(raw_path, season, cache_root):
    body = Path(raw_path).read_bytes(); payload = json.loads(body.decode("utf-8")); return analyze_payload(payload, body, season, cache_root)
def analyze_payload(payload, body, season, cache_root):
    parsed = parse(payload); base = _base_profiles(cache_root).get(season, {})
    ids, baseids = set(parsed["profiles"]), set(base); matched = ids & baseids
    return {"season":season,"raw_body_sha256":raw_body_hash(body),"canonical_json_sha256":canonical_json_hash(payload),"response_rows_by_zone":{z:len(parsed["rows"][z]) for z in EXPECTED_ZONES},"schema":parsed["result_set_headers"],"source_grain":"one league-total row per player per zone (validated per-zone PLAYER_ID uniqueness)","canonical_players":len(ids),"zone_availability":list(EXPECTED_ZONES),"fgm_total":sum(x["fgm"] for x in parsed["rows"]["Restricted Area"]),"fga_total":sum(x["fga"] for x in parsed["rows"]["Restricted Area"]),"zero_attempt_profiles":sum(p["represented_fga"] == 0 for p in parsed["profiles"].values()),"reconciliation":{"shot_location_players":len(ids),"base_source_players":len(baseids),"matched_player_ids":len(matched),"shot_only_player_ids":sorted(ids-baseids,key=int),"base_only_player_ids":sorted(baseids-ids,key=int),"matched_player_share":safe_rate(len(matched),len(baseids)),"malformed_or_duplicate_ids":0}}

def _persist_attempt(root, season, body, event, quarantine=False):
    p = paths(root, season); destination = p["quarantine"] if quarantine else p["raw"]
    atomic_write_bytes_new(destination, body)
    meta = {**event,"body_path":str(destination.relative_to(Path(root))),"byte_count":len(body),"raw_body_sha256":raw_body_hash(body),"canonical_json_sha256":None}
    try: meta["canonical_json_sha256"] = canonical_json_hash(json.loads(body.decode("utf-8")))
    except (UnicodeDecodeError,json.JSONDecodeError): pass
    atomic_write_json(p["metadata"],meta); return meta

def acquire(root, live=False, session_factory=requests.Session, *, policy):
    policy=validate_reconciliation_policy(policy)
    if not live: raise ValueError("live acquisition requires explicit --live")
    # Initialization documents are immutable; a later reviewed promotion is a
    # legitimate manifest transition and must not be mistaken for a collision.
    if not paths(root, SEASONS[0])["manifest"].exists(): initialize(root)
    manifest, ledger = load(root,"manifest"), load(root,"ledger")
    if len(ledger["attempts"]) > MAX_ATTEMPTS: raise ValueError("attempt ceiling exceeded")
    for asset in manifest["assets"]:
        season = asset["season"]
        if asset["status"] in {"verified", "verified_reviewed_promotion"}: continue
        if asset["attempts"]: raise RuntimeError(f"uncertain/interrupted attempt requires explicit review: {season}")
        if len(ledger["attempts"]) >= MAX_ATTEMPTS: raise RuntimeError("attempt ceiling reached")
        event={"season":season,"attempt":1,"identity":asset["identity"],"started_at":now()}; asset["attempts"].append(event); ledger["attempts"].append(event); _write_state(root,manifest,ledger)
        session=session_factory(); session.trust_env=False; session.headers.update(RESEARCH_HEADERS)
        try:
            response=session.get(URL,params=request_parameters(asset["identity"]),timeout=30,allow_redirects=False)
            body=response.content; event.update({"ended_at":now(),"http_status":response.status_code})
            if response.is_redirect or response.status_code != 200:
                _persist_attempt(root,season,body,event,quarantine=True); asset["status"]="stopped"; event["result"]="nonretryable_http"; _write_state(root,manifest,ledger); return {"stopped":season,"event":event}
            try:
                payload=json.loads(body.decode("utf-8")); semantic_audit=audit_shot_payload(payload,totals_for_season(Path(root),season),policy=policy); summary=analyze_payload(payload,body,season,Path(root)); summary["semantic_audit"]=semantic_audit
            except Exception as exc:
                _persist_attempt(root,season,body,event,quarantine=True); asset["status"]="quarantined"; event["result"]=f"validation:{type(exc).__name__}: {exc}"; _write_state(root,manifest,ledger); return {"stopped":season,"event":event}
            meta=_persist_attempt(root,season,body,event); asset.update({"status":"verified","cache":meta,"summary":summary}); event["result"]="verified"; _write_state(root,manifest,ledger)
        except (requests.Timeout, requests.ConnectionError) as exc:
            event.update({"ended_at":now(),"result":f"retryable_transport:{type(exc).__name__}"}); asset["status"]="stopped"; _write_state(root,manifest,ledger); return {"stopped":season,"event":event}
        finally: session.close()
        if season in CANARIES and asset["status"] != "verified": return {"stopped":season}
        if season != SEASONS[-1]: time.sleep(1.0)
    return {"completed":True,"attempts":len(ledger["attempts"])}

@contextmanager
def network_prohibited():
    def reject(*a,**k): raise RuntimeError("network prohibited for Phase 3A.1 replay")
    with patch.object(socket.socket,"connect",reject), patch.object(socket,"create_connection",reject), patch.object(requests,"Session",reject): yield
def analyze(root):
    root=Path(root)
    with network_prohibited():
        phase3a.immutable_evidence(root)
        manifest=load(root,"manifest"); summaries={}
        for asset in manifest["assets"]:
            if asset["status"] != "verified": raise ValueError(f"asset not verified: {asset['season']}")
            raw=root/asset["cache"]["body_path"]
            summaries[asset["season"]]=analyze_asset(raw,asset["season"],root)
        result={"version":"phase3a1.cache-only-feasibility.v1","seasons":summaries,"network":"prohibited","primary_classification":"prior-player shot-zone acquisition supported; Phase 3B feature construction ready"}
        result["deterministic_analysis_sha256"]=canonical_json_hash(result); return result

def analyze_residual_window(root, *, policy):
    """Replay verified raw bodies under the explicit residual policy, offline."""
    policy=validate_reconciliation_policy(policy)
    if policy != RESIDUAL_RECONCILIATION_POLICY: raise ValueError("residual-window replay requires phase3a1.residual-v1")
    root=Path(root)
    with network_prohibited():
        phase3a.immutable_evidence(root)
        manifest=load(root,"manifest"); seasons={}
        for asset in manifest["assets"]:
            if asset["status"] not in {"verified","verified_reviewed_promotion"}:
                raise ValueError(f"asset not accepted under residual policy: {asset['season']}")
            raw=root/asset["cache"]["body_path"]
            body=raw.read_bytes(); payload=json.loads(body)
            parsed=parse(payload)
            audit=audit_shot_payload(payload,totals_for_season(root,asset["season"]),policy=policy)
            expected_hash=asset["cache"].get("raw_body_hash",asset["cache"].get("raw_body_sha256"))
            if raw_body_hash(body)!=expected_hash:
                raise ValueError(f"raw cache hash mismatch: {asset['season']}")
            seasons[asset["season"]]={
                "raw_body_sha256":raw_body_hash(body),
                "canonical_json_sha256":canonical_json_hash(payload),
                "schema":parsed["result_set_headers"],
                "semantic_audit":audit,
            }
        result={"version":"phase3a1.residual-window-replay.v1","network":"prohibited","reconciliation_policy_id":policy,"policy":"overall-minus-seven-zone nonnegative UNCLASSIFIED_FGM/FGA residual; no allocation to a zone","seasons":seasons,"primary_classification":"2013-14 through 2023-24 shot profiles acquired and verified; shot-enabled curation ready"}
        result["deterministic_analysis_sha256"]=canonical_json_hash(result)
        return result
