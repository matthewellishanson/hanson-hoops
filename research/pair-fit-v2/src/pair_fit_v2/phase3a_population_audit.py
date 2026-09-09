"""Phase 3A cache-only population and curation-policy audit.

This module has no transport client and performs no network I/O.  It reuses
the established cache-only Phase 1F replay for provenance verification,
replays the immutable Phase 2 cache, validates the recorded raw-file hashes,
and returns a deterministic summary; it never writes a curated table.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pair_fit_v2.phase1c_manifest import canonical_json_hash


WINDOW = tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(2014, 2024))
THRESHOLDS = (1, 5, 10, 25, 50, 75, 100, 150, 200, 300, 500, 1000)
PHASE2E_HASH = "d57840f80172df49ea7350520fbf1961499c6f558c70c40ced2bab38c7b5379f"
PHASE1_ANCHORS = {
    "phase1c_manifest": "5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c",
    "phase1d_ledger": "f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9",
    "phase1e_ledger": "5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde",
    "phase1f_analysis": "bbe5b0f3805e06ce553774779ad5210b5af8678f3cd84da4d0820ecf3a700d19",
}
PHASE2_ANALYSES = {
    "2023-24": "00f4324311368184d1c184be89d23b866551678b3715c262e76b36f459e24b82",
    "2022-23": "a644c47dd6940ac3ab0ccc438ed9a93c852d325fb11484679d1e341d66708ad0",
    "2021-22": "6b231f4d413d87d8e31bc92fa442ebf9e05587ea8dec9e876dba7cb21fed566f",
}
PHASE2_STATE_HASHES = {
    "phase2b_manifest": "af8acbc10adf110f43c7c53a0ab2d6b402e3121fbe57e2d8b5dc3de7072e689e",
    "phase2b_ledger": "d298f15316dec37cfb3efe6fb9f1451cb3052ed7a1f0b603ce0a4d6057f62dcb",
    "phase2c_manifest": "cce7150e0aa0a4c0278c34d8f20bed0b534bc02ef65c61031c65b03fd786ed0d",
    "phase2c_ledger": "eb4d3fcbf9f0e00104c903ec6f2f8f80c9fb716724d7a469a66d81a0e45eb58e",
    "phase2d_manifest": "0280fcccd8ddb57cfa1f0c2feeccefb815136a576dc672a28c2141bdb27f5015",
    "phase2d_ledger": "19549243c95bfb00e7ac30a111cc8486909a078d7941ad4267609bbdc1a89266",
    "phase2e_2020-21_manifest": "60cbffa3af6b6115e8fd0462644f9ac6004f63ed19b22f72e369bc43461e4b60",
    "phase2e_2020-21_ledger": "334e1e8106d935fb9571f41ceaed1ea734ec930466ad18407a5a1c2a6f880c69",
    "phase2e_2019-20_manifest": "eca79fcc130d81c1f5a52fb57d2e6a724058b849ba1e51b62c4215e13cc9f3ac",
    "phase2e_2019-20_ledger": "c23a8129b63a5245a24bc7dce51c2d069e78a860bf0a9875bd3d7a351fe25c54",
    "phase2e_2018-19_manifest": "ab015676f489f041273da4bd16a61bdf3cff6c2b973fd41dacfa7fc746229b48",
    "phase2e_2018-19_ledger": "49c9977b12d451d8105310c68edaa2cb5298f68721b8fb3ccc7b8b4c54b430b8",
    "phase2e_2017-18_manifest": "018fd2c3a87fddf5b55a48797026da60c36b71e86fd75353877015f134660bb4",
    "phase2e_2017-18_ledger": "8a90537fecff338d76b51c9ce4b5012c295f92365d1aaac2138f57832bc1ee01",
    "phase2e_2016-17_manifest": "adfae71d4f297f0a5d6d23f8efece5cd35787b51cdae96d44cca95dd61b4a1cb",
    "phase2e_2016-17_ledger": "63e0e965138f4a36a2922b9d6da4e7fac23f2238a9147a1ad852dcfdbb4051f4",
    "phase2e_2015-16_manifest": "468dfb37fd87e4f67f78f467fd1e04a27ee8f03fdc7faedca01d93592a25042d",
    "phase2e_2015-16_ledger": "9f52a748f37f428f78516e28af8f01ed05ada7a5b3ec71433ec66bc08892c50b",
    "phase2e_2014-15_manifest": "94228afc1c346122c6bf289f7dc542e16287b3a3406c36b3c8b60198ec5c4c97",
    "phase2e_2014-15_ledger": "28e634b846832c266ead110474b41cadee636be4d73e4bea7e037335f2e5da02",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _id(value) -> str:
    text = str(value)
    if not text.isdecimal() or int(text) <= 0 or str(int(text)) != text:
        raise ValueError(f"noncanonical positive player ID: {value!r}")
    return text


def canonical_pair(player_a, player_b) -> tuple[str, str]:
    left, right = sorted((_id(player_a), _id(player_b)), key=int)
    if left == right:
        raise ValueError("pair cannot contain the same player twice")
    return left, right


def safe_rate(numerator, denominator):
    """Return an undefined rate as None instead of inventing a zero denominator."""
    numerator, denominator = _number(numerator), _number(denominator)
    return None if numerator is None or denominator is None or denominator <= 0 else numerator / denominator


def derived_shooting_features(profile):
    fgm, fga = _number(profile.get("FGM")), _number(profile.get("FGA"))
    fg3m, fg3a = _number(profile.get("FG3M")), _number(profile.get("FG3A"))
    two_m = None if fgm is None or fg3m is None else fgm - fg3m
    two_a = None if fga is None or fg3a is None else fga - fg3a
    return {"three_point_attempt_share": safe_rate(fg3a, fga), "two_point_attempt_share": safe_rate(two_a, fga),
            "free_throw_attempt_rate": safe_rate(profile.get("FTA"), fga), "three_point_accuracy": safe_rate(fg3m, fg3a),
            "two_point_accuracy": safe_rate(two_m, two_a), "overall_fg_accuracy": safe_rate(fgm, fga)}


def symmetric_pair_transform(left, right, field):
    """Order-invariant primitive summary; interpretation remains for later evaluation."""
    a, b = _number(left.get(field)), _number(right.get(field))
    if a is None or b is None:
        return {name: None for name in ("sum", "mean", "minimum", "maximum", "absolute_difference")}
    return {"sum": a + b, "mean": (a + b) / 2, "minimum": min(a, b), "maximum": max(a, b), "absolute_difference": abs(a - b)}


def _rows(payload, result_name):
    result = next((x for x in payload["resultSets"] if x["name"] == result_name), None)
    if result is None:
        raise ValueError(f"missing {result_name} result set")
    return [dict(zip(result["headers"], value)) for value in result["rowSet"]]


def _pair_rows(payload, season, team_id):
    rows = []
    for index, raw in enumerate(_rows(payload, "Lineups")):
        tokens = [x for x in str(raw.get("GROUP_ID", "")).strip("-").split("-") if x]
        if len(tokens) != 2:
            raise ValueError(f"malformed GROUP_ID at {season}/{team_id}/{index}")
        raw["pair"] = canonical_pair(*tokens)
        raw["season"] = season
        raw["team_id"] = str(team_id)
        rows.append(raw)
    return rows


def _unique_pair_index(payload, season, team_id, measure):
    """Validate every canonical observation key before building its index."""
    rows = _pair_rows(payload, season, team_id)
    keys = [(season, str(team_id), *row["pair"]) for row in rows]
    counts = Counter(keys)
    duplicates = sorted((key for key, count in counts.items() if count > 1), key=lambda key: (key[0], int(key[1]), int(key[2]), int(key[3])))
    if duplicates:
        raise ValueError(f"duplicate {measure} observation keys: {duplicates!r}")
    if len(keys) != len(counts):
        raise ValueError(f"duplicate {measure} observation-key count mismatch")
    return {row["pair"]: row for row in rows}


def _reconciled_pair_indexes(base_payload, advanced_payload, season, team_id):
    base = _unique_pair_index(base_payload, season, team_id, "Base")
    advanced = _unique_pair_index(advanced_payload, season, team_id, "Advanced")
    base_only = sorted(set(base) - set(advanced), key=lambda pair: tuple(map(int, pair)))
    advanced_only = sorted(set(advanced) - set(base), key=lambda pair: tuple(map(int, pair)))
    if base_only or advanced_only:
        raise ValueError(
            f"Base/Advanced pair reconciliation failure: {season}/{team_id}; "
            f"base_only={base_only!r}; advanced_only={advanced_only!r}"
        )
    return base, advanced


def _quantiles(values):
    values = sorted(float(v) for v in values)
    if not values:
        return {"count": 0}
    def q(p):
        pos = p * (len(values) - 1); lo = int(pos); hi = min(lo + 1, len(values) - 1)
        return values[lo] * (1 - (pos - lo)) + values[hi] * (pos - lo)
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {"count": len(values), "minimum": values[0], "p01": q(.01), "p05": q(.05),
            "p10": q(.10), "p25": q(.25), "median": q(.5), "mean": mean,
            "p75": q(.75), "p90": q(.9), "p95": q(.95), "p99": q(.99), "maximum": values[-1],
            "variance": variance, "standard_deviation": math.sqrt(variance)}


def _history_status(row, profiles, lookback=1):
    target_year = int(row["season"][:4])
    gaps = []
    for player in row["pair"]:
        available = [target_year - int(season[:4]) for season in profiles if int(season[:4]) < target_year and player in profiles[season]]
        gap = min(available) if available else None
        gaps.append(gap if gap is not None and gap <= lookback else None)
    present = sum(gap is not None for gap in gaps)
    return ("complete" if present == 2 else "one_missing" if present == 1 else "both_missing"), gaps


def _target_summary(rows):
    targets = [_number(r["NET_RATING"]) for r in rows]
    if any(v is None for v in targets):
        raise ValueError("numeric NET_RATING availability failed")
    identities = sum(abs(_number(r["NET_RATING"]) - (_number(r["OFF_RATING"]) - _number(r["DEF_RATING"]))) <= .1000001
                     for r in rows if _number(r["POSS"]) and _number(r["OFF_RATING"]) is not None and _number(r["DEF_RATING"]) is not None)
    eligible = [r for r in rows if _number(r["POSS"]) and _number(r["POSS"]) > 0]
    return {"net_rating": _quantiles(targets), "numeric_missing": 0,
            "zero_possession_rows": sum((_number(r["POSS"]) or 0) == 0 for r in rows),
            "positive_possession_rows": len(eligible), "standard_identity_rows": identities,
            "standard_identity_failures": len(eligible) - identities,
            "extremes": {str(level): sum(abs(_number(r["NET_RATING"])) >= level for r in eligible)
                         for level in (25, 50, 100)},
            "by_season": {s: _quantiles([_number(r["NET_RATING"]) for r in rows if r["season"] == s]) for s in WINDOW},
            "by_team_season": {f"{s}|{t}": _quantiles([_number(r["NET_RATING"]) for r in rows if r["season"] == s and r["team_id"] == t])
                               for s, t in sorted({(r["season"], r["team_id"]) for r in rows})}}


def _thresholds(rows, profiles):
    total_poss = sum(_number(r["POSS"]) or 0 for r in rows)
    answer = {}
    for threshold in THRESHOLDS:
        kept = [r for r in rows if (_number(r["POSS"]) or 0) >= threshold]
        statuses = Counter(_history_status(r, profiles, 1)[0] for r in kept)
        values = [_number(r["NET_RATING"]) for r in kept]
        answer[str(threshold)] = {
            "retained_rows": len(kept), "excluded_rows": len(rows) - len(kept),
            "retained_row_share": len(kept) / len(rows),
            "retained_summed_possession_share": sum(_number(r["POSS"]) or 0 for r in kept) / total_poss,
            "seasons": len({r["season"] for r in kept}), "team_seasons": len({(r["season"], r["team_id"]) for r in kept}),
            "unique_players": len({p for r in kept for p in r["pair"]}), "unique_pairs": len({r["pair"] for r in kept}),
            "target": _quantiles(values), "extreme_counts": {str(level): sum(abs(v) >= level for v in values) for level in (25, 50, 100)},
            "extreme_percentages": {str(level): sum(abs(v) >= level for v in values) / len(values) if values else 0 for level in (25, 50, 100)},
            "history": dict(sorted(statuses.items())),
            "representation_by_season": dict(sorted(Counter(r["season"] for r in kept).items())),
            "representation_by_team": dict(sorted(Counter(r["team_id"] for r in kept).items(), key=lambda x: int(x[0]))),
            "exact_250_team_seasons": sorted({f"{r['season']}|{r['team_id']}" for r in kept if r.get("endpoint_boundary_250")}),
        }
    return answer


def _weighting(rows):
    usable = [r for r in rows if (_number(r["POSS"]) or 0) > 0]
    formulas = {
        "equal": lambda x: 1.0, "linear_possessions": lambda x: x,
        "sqrt_possessions": lambda x: math.sqrt(x), "log1p_possessions": lambda x: math.log1p(x),
        "capped_linear_100": lambda x: min(x, 100), "capped_linear_300": lambda x: min(x, 300),
        "capped_linear_500": lambda x: min(x, 500), "capped_linear_1000": lambda x: min(x, 1000),
        "hybrid_floor25_capped300": lambda x: min(x, 300),
    }
    result = {}
    for name, fn in formulas.items():
        population = [r for r in usable if name != "hybrid_floor25_capped300" or _number(r["POSS"]) >= 25]
        weights = [fn(_number(r["POSS"])) for r in population]
        total = sum(weights)
        allocations = defaultdict(float)
        for row, weight in zip(population, weights):
            allocations[("season", row["season"])] += weight
            allocations[("team_season", row["season"], row["team_id"])] += weight
            for player in row["pair"]: allocations[("player", player)] += weight / 2
        ordered = sorted(weights, reverse=True)
        def concentration(items, share):
            n = max(1, math.ceil(len(items) * share)); return sum(items[:n]) / total if total else 0
        def group_share(label):
            values = sorted((v for key, v in allocations.items() if key[0] == label), reverse=True)
            return {"top_1": values[0] / total if values else 0, "top_10": sum(values[:10]) / total if total else 0}
        result[name] = {"eligible_rows": len(population), "total_weight": total,
                        "normalized_mean_weight": 1.0 if population else 0,
                        "effective_sample_size": total * total / sum(w * w for w in weights) if weights else 0,
                        "top_row_weight_share": concentration(ordered, 1 / len(ordered)) if ordered else 0,
                        "top_1pct_weight_share": concentration(ordered, .01), "top_5pct_weight_share": concentration(ordered, .05),
                        "top_10pct_weight_share": concentration(ordered, .1), "player_concentration": group_share("player"),
                        "team_season_concentration": group_share("team_season"), "season_concentration": group_share("season"),
                        "low_exposure_weight_share_under_100": sum(w for r, w in zip(population, weights) if _number(r["POSS"]) < 100) / total if total else 0}
    return result


def _missing_history(rows, profiles):
    strict = {}
    lookbacks = {}
    for lookback in (1, 2, 3, 5):
        annotated = [(r, *_history_status(r, profiles, lookback)) for r in rows]
        status = Counter(x[1] for x in annotated)
        details = {"statuses": dict(sorted(status.items())), "retained_pair_minutes": sum(_number(r.get("base_min")) or 0 for r, s, _ in annotated if s != "both_missing"),
                   "retained_pair_possessions": sum(_number(r["POSS"]) or 0 for r, s, _ in annotated if s != "both_missing"),
                   "history_gap_distribution": dict(sorted(Counter(g for _, _, gaps in annotated for g in gaps if g is not None).items())),
                   "by_target_season": {season: dict(sorted(Counter(s for r, s, _ in annotated if r["season"] == season).items())) for season in WINDOW}}
        if lookback == 1:
            player_ids = {p for r in rows for p in r["pair"]}
            present = {p for r, s, gaps in annotated for p, g in zip(r["pair"], gaps) if g is not None}
            details["unique_players_with_history"] = len(present); details["unique_players_missing"] = len(player_ids - present)
            details["pair_minutes_by_status"] = {status: sum(_number(r.get("base_min")) or 0 for r, s, _ in annotated if s == status)
                                                 for status in ("complete", "one_missing", "both_missing")}
            details["pair_possessions_by_status"] = {status: sum(_number(r["POSS"]) or 0 for r, s, _ in annotated if s == status)
                                                     for status in ("complete", "one_missing", "both_missing")}
            strict = details
        else:
            prior = [(r, _history_status(r, profiles, 1)[0]) for r in rows]
            details["pair_rows_upgraded_from_missing"] = sum(a != "complete" and b == "complete" for (r, a), (_, b, _) in zip(prior, annotated))
            details["remaining_missing_rows"] = status["one_missing"] + status["both_missing"]
            recovered = {p for (r, old), (_, new, gaps) in zip(prior, annotated) for p, gap in zip(r["pair"], gaps)
                         if old != "complete" and gap is not None and gap > 1}
            details["players_recovered_with_nonadjacent_history"] = len(recovered)
        lookbacks[str(lookback)] = details
    # Reasons determined only from available history, avoiding rookie speculation.
    reasons = Counter()
    for row in rows:
        _, gaps = _history_status(row, profiles, 5)
        for player, gap in zip(row["pair"], gaps):
            if gap is None: reasons["no_prior_record_in_acquired_window"] += 1
            elif gap > 1: reasons["absent_immediately_prior_but_earlier_record_available"] += 1
    return {"strict_previous_season": strict, "lookbacks": lookbacks, "observable_missingness_reasons": dict(sorted(reasons.items()))}


def _repeat_stability(rows):
    by_pair_season = defaultdict(list)
    for row in rows:
        by_pair_season[(row["pair"], row["season"])].append(row)
    out = {}
    for kind in ("all_repeated_pairs", "same_team_repeated_pairs"):
        matches = []
        for (pair, season), current in by_pair_season.items():
            previous = f"{int(season[:4])-1}-{season[2:4]}"
            prior = by_pair_season.get((pair, previous), [])
            for old in prior:
                for new in current:
                    if kind == "same_team_repeated_pairs" and old["team_id"] != new["team_id"]: continue
                    if (_number(old["POSS"]) or 0) > 0 and (_number(new["POSS"]) or 0) > 0: matches.append((old, new))
        bands = {}
        for label, floor in (("poss_gt_0", 1), ("poss_ge_100_each", 100), ("poss_ge_200_each", 200), ("poss_ge_300_each", 300)):
            selected = [(a, b) for a, b in matches if _number(a["POSS"]) >= floor and _number(b["POSS"]) >= floor]
            xs = [_number(a["NET_RATING"]) for a, _ in selected]; ys = [_number(b["NET_RATING"]) for _, b in selected]
            mx = sum(xs) / len(xs) if xs else 0; my = sum(ys) / len(ys) if ys else 0
            denom = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
            bands[label] = {"matched_adjacent_observations": len(selected), "pearson": sum((x-mx)*(y-my) for x, y in zip(xs, ys))/denom if denom else None,
                            "mae": sum(abs(x-y) for x,y in zip(xs,ys))/len(xs) if xs else None,
                            "same_sign_share": sum((x >= 0) == (y >= 0) for x,y in zip(xs,ys))/len(xs) if xs else None}
        out[kind] = bands
    return out


def _feature_inventory(profiles):
    fields = ("AGE", "GP", "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS", "TEAM_COUNT")
    all_profiles = [p for season in profiles.values() for p in season.values()]
    missing = {field: sum(_number(p.get(field)) is None for p in all_profiles) for field in fields}
    return {"source": "LeagueDashPlayerStats Base Per100Possessions; one league-aggregate player-season row", "profile_rows": len(all_profiles),
            "candidate_field_missingness": missing,
            "available_primitive_fields": list(fields),
            "derived_candidates": {"three_point_attempt_share": "FG3A / FGA", "two_point_attempt_share": "(FGA-FG3A) / FGA", "free_throw_attempt_rate": "FTA / FGA", "three_point_accuracy": "FG3M / FG3A", "two_point_accuracy": "(FGM-FG3M) / (FGA-FG3A)", "overall_fg_accuracy": "FGM / FGA"},
            "absent": ["player pace", "height", "weight", "experience", "usage percentage", "shot-location zones", "rim/paint/midrange/corner-three/above-break-three splits"],
            "forbidden": ["rank columns", "PLAYER_NAME", "TEAM_ID/team abbreviation as player quality", "target-season player stats", "target-season pair fields", "row order"]}


def _load_population(cache_root: Path):
    """Load and validate every Phase 2 raw asset without imported acquisition machinery."""
    phase_paths = {**{season: cache_root / "phase2e" / season / "manifest.json" for season in WINDOW[:7]},
                   "2021-22": cache_root / "phase2d" / "manifest.json", "2022-23": cache_root / "phase2c" / "manifest.json",
                   "2023-24": cache_root / "phase2b" / "release_manifest.json"}
    all_rows, profiles, boundaries, evidence = [], defaultdict(dict), [], {}
    for season in WINDOW:
        manifest = _read(phase_paths[season])
        assets = manifest.get("assets") or manifest.get("pair_assets")
        if not assets:
            raise ValueError(f"missing assets for {season}")
        per_team = defaultdict(dict)
        for asset in assets:
            cache = asset.get("cache") or asset.get("source_reference")
            if not cache: continue
            path = cache_root / (cache.get("relative_path") or cache["source_cache_path"])
            if _sha(path) != cache["raw_body_hash"]: raise ValueError(f"raw evidence hash mismatch: {path}")
            payload = _read(path)
            params = asset["identity"]["parameters"]
            if asset["identity"]["endpoint"] == "TeamDashLineups":
                per_team[str(params["team_id"])][params["measure_type"]] = payload
        # Phase 2B player dependencies are immutable imported pointers; later releases are ordinary assets.
        player_sources = manifest.get("player_dependencies", [])
        if not player_sources:
            player_sources = [a for a in assets if a["identity"]["endpoint"] == "LeagueDashPlayerStats"]
        prior_season = f"{int(season[:4])-1}-{season[2:4]}"
        player_payloads = {}
        for source in player_sources:
            cache = source.get("cache") or {"relative_path": source["source_cache_path"], "raw_body_hash": source["raw_body_hash"]}
            path = cache_root / cache["relative_path"]
            if _sha(path) != cache["raw_body_hash"]: raise ValueError(f"player evidence hash mismatch: {path}")
            mode = (source.get("identity") or source.get("source_identity"))["parameters"]["per_mode"]
            player_payloads[mode] = _rows(_read(path), "LeagueDashPlayerStats")
        if set(player_payloads) != {"Per100Possessions", "Totals"}: raise ValueError(f"missing player modes for {season}")
        totals = {_id(r["PLAYER_ID"]): r for r in player_payloads["Totals"]}
        for player in player_payloads["Per100Possessions"]:
            ident = _id(player["PLAYER_ID"])
            if ident not in totals: raise ValueError("player-source ID sets do not reconcile")
            profiles[prior_season][ident] = {**player, "TOTAL_MIN": totals[ident].get("MIN")}
        for team, measures in per_team.items():
            if set(measures) != {"Base", "Advanced"}: raise ValueError(f"Base/Advanced missing: {season}/{team}")
            base, advanced = _reconciled_pair_indexes(measures["Base"], measures["Advanced"], season, team)
            boundary = len(advanced) == 250
            for pair, row in advanced.items():
                row["base_min"] = base[pair].get("MIN"); row["endpoint_boundary_250"] = boundary
                all_rows.append(row)
            if boundary or any((_number(r["POSS"]) or 0) == 0 for r in advanced.values()):
                boundaries.append({"season": season, "team_id": team, "team_name": manifest["team_directory"][team]["team_name"],
                                   "returned_rows": len(advanced), "exact_250": boundary,
                                   "zero_possession_rows": sum((_number(r["POSS"]) or 0) == 0 for r in advanced.values())})
        evidence[season] = {"pair_rows": sum(len(_pair_rows(payload, season, team)) for team, ms in per_team.items() for payload in [ms["Advanced"]]),
                            "player_prior_season": prior_season, "player_rows": len(player_payloads["Per100Possessions"])}
    keys = [(r["season"], r["team_id"], *r["pair"]) for r in all_rows]
    if len(keys) != len(set(keys)): raise ValueError("duplicate full observation key")
    return all_rows, dict(profiles), boundaries, evidence


def _phase1f_replay_hash(cache_root: Path) -> str:
    from pair_fit_v2.phase1f_target_audit import analyze_cached_phase1f

    return analyze_cached_phase1f(cache_root)["summary_sha256"]


def _verify_phase1f_anchor(cache_root: Path) -> str:
    derived = _phase1f_replay_hash(cache_root)
    if derived != PHASE1_ANCHORS["phase1f_analysis"]:
        raise ValueError(f"Phase 1F analysis anchor mismatch: {derived}")
    return derived


def _verify_phase2e_summary(path: Path) -> str:
    summary = _read(path)
    stored = summary.pop("deterministic_analysis_sha256", None)
    derived = canonical_json_hash(summary)
    if stored != PHASE2E_HASH or derived != PHASE2E_HASH:
        raise ValueError(f"Phase 2E final analysis anchor mismatch: stored={stored}; derived={derived}")
    return derived


def immutable_evidence(cache_root: Path):
    checks = {name: _sha(cache_root / relative) for name, relative in {
        "phase1c_manifest": "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json",
        "phase1d_ledger": "phase1d/diagnostic_ledger.json", "phase1e_ledger": "phase1e/recovery_ledger.json"}.items()}
    if checks != {k: v for k, v in PHASE1_ANCHORS.items() if k != "phase1f_analysis"}: raise ValueError("Phase 1 immutable anchor mismatch")
    phase2_paths = {
        "phase2b_manifest": "phase2b/release_manifest.json", "phase2b_ledger": "phase2b/attempt_ledger.json",
        "phase2c_manifest": "phase2c/manifest.json", "phase2c_ledger": "phase2c/attempt_ledger.json",
        "phase2d_manifest": "phase2d/manifest.json", "phase2d_ledger": "phase2d/attempt_ledger.json",
    }
    for season in ("2020-21", "2019-20", "2018-19", "2017-18", "2016-17", "2015-16", "2014-15"):
        phase2_paths[f"phase2e_{season}_manifest"] = f"phase2e/{season}/manifest.json"
        phase2_paths[f"phase2e_{season}_ledger"] = f"phase2e/{season}/attempt_ledger.json"
    phase2_checks = {name: _sha(cache_root / relative) for name, relative in phase2_paths.items()}
    if phase2_checks != PHASE2_STATE_HASHES: raise ValueError("Phase 2B–2E immutable state anchor mismatch")
    checks["phase1f_analysis"] = _verify_phase1f_anchor(cache_root)
    checks["phase2e_analysis"] = _verify_phase2e_summary(cache_root / "phase2e/final-combined-audit.json")
    checks["phase2b_to_2e_state_hashes_verified"] = len(phase2_checks)
    return checks


@contextmanager
def network_prohibited():
    import socket
    def reject(*args, **kwargs): raise RuntimeError("Phase 3A network access prohibited")
    with (
        patch.object(socket.socket, "connect", reject),
        patch.object(socket.socket, "connect_ex", reject),
        patch.object(socket, "create_connection", reject),
    ):
        yield


def analyze(cache_root: Path | str):
    cache_root = Path(cache_root)
    with network_prohibited():
        anchors = immutable_evidence(cache_root)
        rows, profiles, boundaries, evidence = _load_population(cache_root)
        if len(rows) != 46938: raise ValueError(f"historical population count mismatch: {len(rows)}")
        summary = {"version": "phase3a.population-policy-audit.v1", "immutable_evidence": anchors,
                   "population": {"rows": len(rows), "positive_possession_rows": sum((_number(r["POSS"]) or 0) > 0 for r in rows),
                                  "zero_possession_rows": sum((_number(r["POSS"]) or 0) == 0 for r in rows),
                                  "unique_players": len({p for r in rows for p in r["pair"]}), "unique_pairs": len({r["pair"] for r in rows}),
                                  "observation_grain": "team × target season × canonical unordered player pair", "seasons": list(WINDOW), "evidence": evidence},
                   "target": _target_summary(rows), "exposure_thresholds": _thresholds(rows, profiles),
                   "weighting": _weighting(rows), "missing_history": _missing_history(rows, profiles),
                   "adjacent_season_stability": _repeat_stability(rows), "feature_inventory": _feature_inventory(profiles),
                   "endpoint_flags": sorted(boundaries, key=lambda x: (x["season"], int(x["team_id"]))),
                   "season_context": {s: {"pandemic_affected": s in {"2019-20", "2020-21"}, "rows": sum(r["season"] == s for r in rows), "positive_possession_rows": sum(r["season"] == s and (_number(r["POSS"]) or 0) > 0 for r in rows)} for s in WINDOW}}
        # Audit-only row ledger: no player features, no imputation, no curated output.
        summary["row_evidence_ledger"] = [
            {"season": r["season"], "team_id": r["team_id"], "pair": list(r["pair"]), "possessions": _number(r["POSS"]),
             "base_minutes": _number(r.get("base_min")), "net_rating": _number(r["NET_RATING"]),
             "strict_history": _history_status(r, profiles, 1)[0], "endpoint_boundary_250": r["endpoint_boundary_250"]}
            for r in sorted(rows, key=lambda r: (r["season"], int(r["team_id"]), tuple(map(int, r["pair"]))))]
        summary["deterministic_analysis_sha256"] = hashlib.sha256(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        return summary
