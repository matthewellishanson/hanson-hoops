# Pair-fit v2 research README

## Scope

This folder contains the Phase 0 feasibility scaffold for the Hanson Hoops pair-fit v2 experiment. This work is research-only and does not modify production frontend or backend behavior.

## Phase 0F status

one-team prior-player join feasibility quantified; provisional missing-history baseline policy adopted; multi-team scale remains pending

Phase 0F acquired one live 2023-24 `LeagueDashPlayerStats` response (572 unique player rows, 0 duplicate IDs) and joined it by stable `PLAYER_ID` to the 183 Warriors 2024-25 canonical pairs. Player-level coverage: 19/23 unique players (82.6%). Pair-level coverage: 143/183 pairs with both players matched (78.1%); the missing pairs are concentrated in a small number of players and hold 2,989.0 of 39,458.0 summed shared minutes (7.6%) and 6,365 of 84,005 summed possessions (7.6%). One traded player (Buddy Hield) shows a valid `GP=84`, which is a normal combined-team total, not an anomaly. A provisional missing-history baseline policy has been adopted (see `MODELSPEC.md`); it is subject to reevaluation after the Phase 1A multi-team pilot. Multi-team feasibility and predictive feasibility remain pending.

**Phase 1A recommendation**: go for a bounded multi-team ingestion and validation pilot (testing whether schemas, pair joins, prior coverage and missing-history patterns generalize beyond the Warriors); no-go for model training or full historical expansion.

## Status

- Phase 0 model contract: in `MODELSPEC.md`
- Data dictionary: `DATA_DICTIONARY.md`
- Feasibility report: `FEASIBILITY_REPORT.md`
- Tests: `tests/test_phase0_pipeline.py`

## Commands

From the repository root:

```powershell
cd research\pair-fit-v2
python -m pytest tests -q
```

To inspect the package in a Python shell:

```powershell
cd research\pair-fit-v2
python -c "import sys; sys.path.insert(0, r'.\src'); from pair_fit_v2.schema import canonical_pair_key; print(canonical_pair_key('204','101'))"
```

## Research guardrails

- Do not use 2025–26 as experimental data.
- Do not train a model in Phase 0.
- Keep all raw API responses and caches immutable where possible.
- Use prior-season player data only, not same-season target stats.
- Preserve the canonical pair identity rule: A+B and B+A are not distinct records.
- Prior-player join audit (Phase 0F): one-team feasibility is quantified and a provisional missing-history baseline policy is adopted (see `MODELSPEC.md`). Multi-team historical feasibility and predictive feasibility remain pending, to be tested in the bounded Phase 1A pilot.
