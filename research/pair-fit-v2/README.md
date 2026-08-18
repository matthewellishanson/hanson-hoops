# Pair-fit v2 research README

## Scope

This folder contains the Phase 0 feasibility scaffold for the Hanson Hoops pair-fit v2 experiment. This work is research-only and does not modify production frontend or backend behavior.

## Phase 0E status

live one-team rate-target availability and Base-to-Advanced join verified; prior-player and multi-team feasibility remain pending

Phase 0D acquired one authentic 2024-25 Warriors Base pair-lineup response (183 two-player pairs). Phase 0E acquired one Warriors Advanced response through the same direct `requests.Session` path and joined all 183 canonical pairs one-to-one to Base. `OFF_RATING`, `DEF_RATING`, `NET_RATING`, estimated counterparts, `POSS`, `PACE` and `MIN` were directly observed. `PLUS_MINUS` remains cumulative on-court differential, not a per-possession rate. Prior-player join audit (Phase 0F) and multi-team feasibility remain pending.

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
- Prior-player join audit (Phase 0F), multi-team historical feasibility and predictive feasibility remain pending.
