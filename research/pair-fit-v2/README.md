# Pair-fit v2 research README

## Scope

This folder contains the Phase 0 feasibility scaffold, Phase 1A evidence audit and Phase 1B architecture contracts for the Hanson Hoops pair-fit v2 experiment. This work is research-only and does not modify production frontend or backend behavior.

## Phase 1B status

Architecture and ingestion design is now specified in `PHASE1B_ARCHITECTURE.md`. Standard-library contracts define stable season/team/pair keys, deterministic raw-asset and season manifests, resumability decisions, provenance requirements, schema-drift quarantine, row-preserving curated validation, complete 30-team raw gates and an extensible prior-player feature-source registry. The complete-season gate independently verifies the normalized manifest identity and ID, each asset ID against its embedded identity, each embedded identity against the manifest's expected request, and each required schema fingerprint against the approved measure-specific schema contract.

Phase 1B has not acquired any remaining team, made a live request, created Parquet or DuckDB artifacts, trained a model or used 2025-26 data. The contracts were verified against the existing four-team caches only: 8/8 unique assets matched their recorded canonical JSON hashes, Base/Advanced schemas were identical, and all 736 pair observations had unique full Phase 1B keys.

## Phase 1A status

Phase 1A bounded multi-team pilot complete; schema and join behavior are consistent across the four pilot teams; prior-history coverage varies materially within this bounded sample

Three new teams (Boston Celtics, Washington Wizards, Brooklyn Nets) were acquired via six bounded live requests and combined with the cached Warriors data (736 combined 2024-25 pairs). Base and Advanced schemas are identical across all four teams; all Base-to-Advanced joins are 100% matched and one-to-one; the combined canonical observation key has zero duplicates. Prior-player pair-level coverage ranges from 57.2% (Washington Wizards) to 81.6% (Boston Celtics), combined 68.9% (507/736). The pattern is consistent with the deliberately selected roster profiles, but four teams do not establish roster type as the cause or prove a league-wide relationship.

The cache-only possession audit found one zero/missing-possession row: Washington's `K. Middleton - J. McDaniels` pair (`1629667`, `203114`) has Base `MIN=0.143333`, Advanced `MIN=0.0`, `POSS=0.0`, and returned `OFF_RATING=0.0`, `DEF_RATING=0.0`, `NET_RATING=0.0`. It is retained unchanged but is ineligible for a possession-based rate target. No other pilot row has zero or missing `POSS`. Full findings and the bounded Phase 1B recommendation are in `PHASE1A_PILOT_REPORT.md`.

## Phase 0F status

one-team prior-player join feasibility quantified; uniform missing-history status policy established and later exercised by Phase 1A

Phase 0F acquired one live 2023-24 `LeagueDashPlayerStats` response (572 unique player rows, 0 duplicate IDs) and joined it by stable `PLAYER_ID` to the 183 Warriors 2024-25 canonical pairs. Player-level coverage: 19/23 unique players (82.6%). Pair-level coverage: 143/183 pairs with both players matched (78.1%). One traded player (Buddy Hield) shows a valid `GP=84`, which is a normal combined-team total, not an anomaly. The uniform missing-history policy uses `complete`, `one_missing`, and `both_missing`, makes complete-history pairs the primary baseline population, never zero-imputes absent history, and retains every row for later evaluation of one universal no-history fallback (see `MODELSPEC.md`). Predictive feasibility remains unverified.

**Phase 1B recommendation:** bounded go for architecture and ingestion design only; no-go for model training or historical expansion until the exposure policy, uniform missing-history treatment, and chronological validation design are approved. See `PHASE1A_PILOT_REPORT.md`.

## Status

- Phase 0 model contract: in `MODELSPEC.md`
- Data dictionary: `DATA_DICTIONARY.md`
- Feasibility report: `FEASIBILITY_REPORT.md`
- Phase 1A pilot report: `PHASE1A_PILOT_REPORT.md`
- Phase 1B architecture: `PHASE1B_ARCHITECTURE.md`
- Tests: `tests/`, including `tests/test_phase1a_pilot_audit.py` and `tests/test_phase1b_architecture.py`

## Commands

From the repository root:

```powershell
python.exe -m pytest research\pair-fit-v2\tests -q --basetemp=research\pair-fit-v2\.pytest_tmp
```

To inspect the package in a Python shell:

```powershell
cd research\pair-fit-v2
python -c "import sys; sys.path.insert(0, r'.\src'); from pair_fit_v2.schema import canonical_pair_key; print(canonical_pair_key('204','101'))"
```

## Research guardrails

- Do not use 2025–26 as experimental data.
- Do not train a model during the current architecture/ingestion-design phase.
- Keep all raw API responses and caches immutable where possible.
- Use prior-season player data only, not same-season target stats.
- Preserve the canonical pair identity rule: A+B and B+A are not distinct records.
- Define a schema fingerprint by result-set name, ordered columns, and column count; treat row count as data volume, not schema identity.
- Use Base `MIN` for shared-minute exposure and Advanced `POSS` for possession exposure. Do not assume Advanced `MIN` is interchangeable with Base `MIN` at sparse exposure.
- Retain rows with missing `POSS` or `POSS <= 0` for audit, but mark them ineligible for possession-based rate targets even when ratings are numeric. No positive exposure threshold has been selected.
- Apply the same `complete`/`one_missing`/`both_missing` policy across teams, use complete-history pairs as the primary baseline population, never zero-impute missing history, and retain all rows for later evaluation of a universal fallback.
- Use time-ordered or rolling-origin validation, preserve 2025-26 as the untouched final test season, and reject random pair-row splits because overlapping players and pairs violate row independence.
- Phase 1A multi-team pilot (see `PHASE1A_PILOT_REPORT.md`): schema/join behavior is consistent across four pilot teams; coverage varies materially but the sample does not establish roster type as the cause or a league-wide relationship. Phase 1B is a bounded go for architecture/ingestion design only; model training and historical expansion remain prohibited pending approval of the exposure, missing-history, and validation policies.
- Phase 1B contracts (see `PHASE1B_ARCHITECTURE.md`) are design-only. Do not execute a 30-team manifest, materialize Parquet/DuckDB, or fetch remaining teams without a later explicit approval.
- Keep `group_quantity=2` for `pair_observations`. It is part of raw request identity, so pair/trio/quartet/five-player requests cannot collide. Higher-order research requires a separate versioned group-observation contract; aggregating pair predictions across a larger selection would not be a directly trained lineup model.
