# Pair-fit v2 research README

## Scope

This folder contains the Phase 0 feasibility scaffold for the Hanson Hoops pair-fit v2 experiment. This work is research-only and does not modify production frontend or backend behavior.

## Final Phase 0 status

currently blocked

The synthetic scaffold is valid, and the Phase 0B bounded live diagnostic isolated the blocker source: general `stats.nba.com` access timeout from the current local environment (not endpoint-specific, not pair-lineup-specific, not request-size-specific). All three tested endpoints—TeamDashLineups, LeagueDashLineups, and LeagueStandingsV3—timed out at the network layer with HTTPSConnectionPool read timeout after 30 seconds. The live 2024–25 pair-season audit remains blocked by this data-access issue, which is environment-specific and separate from model or schema feasibility.

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
