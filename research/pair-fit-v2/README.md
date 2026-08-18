# Pair-fit v2 research README

## Scope

This folder contains the Phase 0 feasibility scaffold for the Hanson Hoops pair-fit v2 experiment. This work is research-only and does not modify production frontend or backend behavior.

## Final Phase 0 status

live Base pair-lineup acquisition verified; rate-target and prior-player feasibility pending

Phase 0D acquired one authentic 2024-25 Warriors Base pair-lineup response (183 two-player pairs) via direct requests.Session. PLUS_MINUS field is cumulative on-court differential, not a per-possession rate; Advanced measure required for rate-target validation. Prior-player join audit (Phase 0E) remains pending. Direct requests.Session pattern proven; nba_api wrapper times out but is not required.

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
- Advanced rate-target validation (Phase 0E) and the subsequent prior-player join audit (Phase 0F) remain pending.
