# Phase 3F-R4 final evaluation execution contract

## Scope

This checkpoint executes the separately authorized, one-time frozen 2025-26 final Ridge evaluation. The authoritative scientific contract is the unchanged Phase 3F-R0/R0.1 policy. The authoritative readiness input is the eleven original non-summary R3 artifacts plus `curated/phase3f-r3.1/corrected_summary.json`; the historical R3 summary remains preserved but is superseded for deterministic composite use.

This contract authorizes exactly one fit of `sklearn.linear_model.Ridge(alpha=3000.0)` on the 29,701-row expanded-training population, exactly one prediction call against the already-scaled 2,811 by 45 final-test matrix, one frozen historical-training-mean baseline, and the predeclared metrics, diagnostics, warnings, and mechanical classification. It authorizes no alternate model, tuning, calibration fit, second operation, network access, target reconstruction, model serialization, packaging, integration, deployment, commit, or push.

## Preconditions and write-once boundary

The official CLI requires branch `research/pair-fit-v2`, HEAD `da6e7c1d1e7c94a8dbf7a4b4c658b2a55695862d`, upstream divergence `0/0`, a clean index, and only the five predeclared Git-visible R4 paths changed. It authenticates the complete R0/R0.1 and R3/R3.1 composites, the spent-development reference, the exact row and feature identities, the six passed readiness gates, finiteness, exclusions, and source restrictions before estimator construction.

The official program creates `curated/phase3f-r4/` once and refuses an existing namespace. It first persists the command, environment, hashes, configuration, event ledger, and passing pre-execution integrity record. A failure is retained in that namespace and prohibits relaunch without new user authorization.

## Sole model operation

The frozen R0 scaler is applied exactly once to the unscaled 29,701 by 45 training matrix. The R3 final-test matrix is consumed directly with no transformation. The sole Ridge uses equal implicit row weights. The baseline is derived only after prediction as the full-precision unweighted mean of all 29,701 aligned training targets. No fitted object is serialized.

The prediction vector remains memory-only until prediction integrity, input immutability, all frozen metrics, diagnostics, warnings, schemas, and the classification have passed in memory. Sensitive artifacts are then published write-once, with `predictions.csv` first so valid prediction bytes survive any later publication defect.

## Metrics and verdict

Metric formulas, signs, `ddof=0`, average-tie Spearman behavior, missing-history groups, team and no-refit leave-one-team-out diagnostics, deterministic ten-bin ordering, residual relationships, historical warnings, null rules, and classification precedence are inherited unchanged from the committed policies. Calibration bins use `1 + floor(j * 10 / n)` after sorting by prediction, numeric team ID, and numeric canonical player IDs.

The program loads the machine-readable R0 classification definitions. Integrity failure or nonfinite mandatory improvement is `INVALID`; MAE improvement at most zero is `FINAL SCIENTIFIC FAILURE`; MAE improvement at least `0.10` and RMSE improvement at least zero is `FINAL SCIENTIFIC PASS`; every other finite result is `FINAL MIXED RESULT`. Diagnostics cannot override the result.

## Outputs and stop boundary

The ignored namespace contains configuration, append-only events, pre-execution integrity, the sole row-aligned prediction vector, all frozen aggregate and subgroup artifacts, decision, nonrecursive hash manifest, and summary. `PHASE3F_R4_FINAL_EVALUATION_REPORT.md` is the sole Git-visible human result report.

After the official invocation, verification is read-only with respect to the namespace and cannot call the estimator. Work stops after deterministic publication and verification. The next step is one final read-only scientific audit; packaging and deployment remain unauthorized.
