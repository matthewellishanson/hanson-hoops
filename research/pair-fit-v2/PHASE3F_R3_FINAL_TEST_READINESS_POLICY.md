# Phase 3F-R3 final-test construction and readiness policy

## Scope and stop boundary

This checkpoint authenticates the audit-cleared Phase 3F evidence, constructs the frozen 2025–26 final-test population, applies the frozen expanded-training preprocessing state, and evaluates the six frozen readiness gates. It is offline, estimator-free, and stops before fitting, prediction, performance calculation, or model serialization.

The target is direct full-season Advanced `NET_RATING`. Eligibility is direct full-season `POSS >= 150`; the TeamDashLineups Base schema has no `POSS`, so possession comes from the matching direct full-season Advanced row while Base supplies the exact reconciled pair key and Base audit fields. No window or recovered response supplies a retained row, possession, or target.

Indiana (`1610612754`) and Memphis (`1610612763`) are excluded in full as proven non-exhaustive. The other 28 teams are retained subject only to the frozen eligibility rule. Zero-possession raw rows remain diagnostic and are ineligible.

Player history is the nearest available strict-prior profile in 2024–25, 2023–24, then 2022–23. Missing history remains explicit. Totals `MIN` becomes `TOTAL_MIN` reliability metadata only. The exact ordered 45-feature symmetric no-shot manifest excludes target, exposure, reliability, provenance, history, and slot-specific fields.

The sole preprocessing state is `curated/phase3f-r0/expanded_preprocessing_state.json`, learned from all and only the 29,701 expanded-training rows. Player-slot medians are applied identically, frozen symmetric fills are applied, and the frozen scaler is applied exactly once. The persisted matrix is marked `scaled_once_ready_for_direct_ridge_prediction`.

## Frozen readiness gates

The gate order and identities remain exactly:

1. `predictor_evidence_completeness`
2. `target_evidence_completeness`
3. `team_population_exhaustiveness`
4. `row_eligibility`
5. `row_alignment`
6. `protected_result_reveal`

Every gate must pass. A failed or unresolved gate blocks final execution. Passing all six authorizes only a focused read-only audit of this checkpoint. Final execution additionally requires that audit to clear and the user to separately authorize the one-time final model execution.

## Generated evidence

The ignored, write-once namespace is `curated/phase3f-r3/`. It contains staging, row-index, target-vector, scaled estimator-matrix, feature-manifest, preprocessing-identity, population, history-selection, input-fingerprint, readiness-gate, artifact-manifest, and summary artifacts. The artifact manifest nonrecursively hashes exactly the first ten payloads and excludes itself and `summary.json`. JSON is strict and finite; CSV row and column order is deterministic.

The implementation imports no transport or estimator package and exposes no acquisition, fitting, prediction, metric, or serialization path. It does not modify earlier evidence. No commit or push is part of this checkpoint.
