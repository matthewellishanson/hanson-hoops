# Phase 3E-R3: pre-result 2024-25 development-holdout evaluation policy

## Policy status and scope

This policy is frozen before any 2024-25 prediction, baseline value, model-performance result, target distribution, calibration result, residual result, or prediction-distribution result is generated or inspected. Phase 3E-R3 defines evaluation only. It does not authorize running or loading the model, fitting any estimator or calibrator, calculating any holdout metric, accessing the network, or accessing 2025-26 evidence.

The machine-readable source of truth is the deterministic, Git-ignored `modeling/phase3e-r3/evaluation_policy.json`, built by `pair_fit_v2.phase3e_r3_evaluation_policy`. Its builder validates the frozen Phase 3D and Phase 3E-R2 contracts without parsing the target-bearing R2 CSV rows.

## Reconciled prior evidence

This policy reconciles `AGENTS.md`, `MODELSPEC.md`, `DATA_DICTIONARY.md`, the Phase 3B feature specification and manifests, the Phase 3C report and artifacts, the complete Phase 3D report and required artifacts, the Phase 3E-R0/R1 reports and policies, and the Phase 3E-R2 construction report, manifests, preprocessing state, and audit conclusion.

The controlling evidence is:

- Phase 3B training population: `curated/phase3b/phase3b_poss_ge_150.csv`, 27,001 rows, serialized-byte SHA-256 `da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8`.
- Phase 3D selection: `modeling/phase3d/selection_decision.json`, SHA-256 `5ef9663dff906fc04b3a31aec56c0dce1ce9fe4e7cdcc87dbaab95762ff02ca0`.
- Phase 3E-R2 artifact manifest: `curated/phase3e-r2/artifact_hashes.json`, SHA-256 `50247fad8a51d314a6cf3933a5341ee8327fca292a06ea95b1c5816bcc3992f2`.
- Phase 3E-R2 summary: `curated/phase3e-r2/summary.json`, SHA-256 `ddb877f2be0f5d6cbe8f14098c7ee3ee7201e04cbc785e93e97ce701d48ba5ba`.

The exact R2 evaluation inputs and byte hashes are:

| Artifact | Serialized-byte SHA-256 |
| --- | --- |
| `holdout_staging.csv` | `2a281f379258f0f14a59395d656484fe265443217da028e7e2733ae698ffac58` |
| `holdout_row_index.csv` | `2ba178639cd2f1c4dcba5407a1b040bd993d7cdee31b045a33c6de0583d0304b` |
| `holdout_estimator_matrix.csv` | `eea1e78f427877c3c173e2607bbe2a42d87d39c7ea3a8e41e2277d95cf44ca25` |
| `estimator_feature_manifest.json` | `4cb3e75bc1c37a56063147b75fdc5def582ad65a704ce282afa96a7897ad4b1c` |
| `preprocessing_state.json` | `05730ce4ecd8944e236e791faecf242174272692794477e39d1523f9475d7da3` |
| `population_diagnostics.json` | `6c0b136f93b3ec2c24d9ee70cb930160d45af5b10a27c32df6b65baafd2558ed` |
| `input_fingerprints.json` | `11e00e15ac188a5d7d243b484192fe4604d37d21e06b482fb724c81683f45918` |
| `artifact_hashes.json` | `50247fad8a51d314a6cf3933a5341ee8327fca292a06ea95b1c5816bcc3992f2` |
| `summary.json` | `ddb877f2be0f5d6cbe8f14098c7ee3ee7201e04cbc785e93e97ce701d48ba5ba` |

Any mismatch is an integrity failure, not permission to rebuild the holdout or relax the policy.

## Frozen evaluation population

The evaluation population is 2024-25 Regular Season, with exactly 28 retained teams and 2,700 eligible canonical pair rows. Charlotte (`1610612766`) and Philadelphia (`1610612755`) are excluded in full under the predeclared incomplete-team-season policy. Eligibility is the directly returned full-season `POSS >= 150`. The target is the directly returned full-season pair `NET_RATING`. No window-aggregated, reconstructed, or substituted target is allowed.

The observation key is `(target_season, team_id, player_1_id, player_2_id)`. Player IDs must be numerically canonical with `player_1_id < player_2_id`, and the full key must be unique.

Pair keys have two deliberately separate namespaces. Phase 1B retains its lexicographic normalized-decimal-string ordering solely as a legacy Phase 1B raw-acquisition, cache-identity, and deterministic-replay convention; its behavior and historical raw evidence must not change. Phase 3B and every later curated/model phase use numeric positive-ID ordering. Phase 3E-R2, this R3 policy, and future R4 therefore require `int(player_1_id) < int(player_2_id)`. Future R4 source must not import or apply either `pair_fit_v2.phase1b_contract.stable_pair_key` or its lexicographic delegate `pair_fit_v2.schema.canonical_pair_key` to model observation keys. No raw historical artifact is renamed, rewritten, migrated, or rehashed.

No row or team may be added or removed after errors are seen.

## Frozen estimator and preprocessing

The only authorized estimator is `sklearn.linear_model.Ridge(alpha=3000.0)`, matching the Phase 3D constructor under the pinned scikit-learn 1.3.2 environment. It is trained once on all 27,001 eligible rows from 2014-15 through 2023-24 with equal row weights. Exact-250 historical observations are included normally.

Player history is the nearest strictly prior profile within three seasons. The model uses the Phase 3E-R2 training-only player-slot medians, symmetric-feature fills, feature order, and scaling. The already transformed and scaled R2 holdout estimator matrix must be consumed directly. Nothing may be learned, refit, selected, or normalized from 2024-25: not medians, scaling, features, alpha, weights, or any other preprocessing operation.

The exact ordered no-shot inputs are:

1. `pair_mean.AGE`
2. `pair_mean.FGM`
3. `pair_mean.FGA`
4. `pair_mean.FG3M`
5. `pair_mean.FG3A`
6. `pair_mean.FTM`
7. `pair_mean.FTA`
8. `pair_mean.OREB`
9. `pair_mean.DREB`
10. `pair_mean.AST`
11. `pair_mean.TOV`
12. `pair_mean.STL`
13. `pair_mean.BLK`
14. `pair_mean.BLKA`
15. `pair_mean.PF`
16. `pair_mean.PFD`
17. `pair_mean.PTS`
18. `pair_mean.PLUS_MINUS`
19. `pair_mean.effective_field_goal_pct`
20. `pair_mean.true_shooting_pct`
21. `pair_mean.three_point_attempt_rate`
22. `pair_mean.free_throw_rate`
23. `pair_absolute_difference.AGE`
24. `pair_absolute_difference.FGM`
25. `pair_absolute_difference.FGA`
26. `pair_absolute_difference.FG3M`
27. `pair_absolute_difference.FG3A`
28. `pair_absolute_difference.FTM`
29. `pair_absolute_difference.FTA`
30. `pair_absolute_difference.OREB`
31. `pair_absolute_difference.DREB`
32. `pair_absolute_difference.AST`
33. `pair_absolute_difference.TOV`
34. `pair_absolute_difference.STL`
35. `pair_absolute_difference.BLK`
36. `pair_absolute_difference.BLKA`
37. `pair_absolute_difference.PF`
38. `pair_absolute_difference.PFD`
39. `pair_absolute_difference.PTS`
40. `pair_absolute_difference.PLUS_MINUS`
41. `pair_absolute_difference.effective_field_goal_pct`
42. `pair_absolute_difference.true_shooting_pct`
43. `pair_absolute_difference.three_point_attempt_rate`
44. `pair_absolute_difference.free_throw_rate`
45. `pair_traded_history_count`

Shot features, a calibrator, alternate Ridge alpha, HGB, a fallback estimator, an ensemble, model redesign, and post-result tuning are prohibited.

## Historical-training-mean baseline

The baseline is one mean target computed from all and only the 27,001 rows in the hash-pinned Phase 3B `POSS >= 150` training artifact. Every row receives weight one:

`baseline prediction = sum(training target_net_rating) / 27,001`

That single value is assigned to all 2,700 holdout rows. The 2024-25 target mean must not be used as the prediction.

The evaluation record must retain the training artifact path and hash, row count, ordered seasons, observation-key fields, target field, eligibility rule, equal-weight rule, and computed training mean at full precision. The hash-pinned artifact defines the exact training rows; no historical row may be silently omitted or duplicated.

## Metric definitions and precision

Let `e_i = prediction_i - target_i`, and let `n = 2,700` for pooled unweighted metrics.

- `MAE = sum(abs(e_i)) / n`.
- `RMSE = sqrt(sum(e_i^2) / n)`.
- `R² = 1 - sum(e_i^2) / sum((target_i - mean(target))^2)`. Report null with a reason if target variance is zero.
- Signed bias is `sum(e_i) / n`: mean prediction minus mean target.
- Spearman is the Pearson correlation of prediction ranks and target ranks, with average ranks for ties. Report null with a reason if either rank vector is constant.
- Prediction and target standard deviations use the population definition, `ddof=0`.
- Prediction-to-target standard-deviation ratio is `prediction SD / target SD`. Report null with a reason if target SD is zero.
- `MAE improvement = baseline MAE - Ridge MAE`.
- `RMSE improvement = baseline RMSE - Ridge RMSE`.

All primary metrics are unweighted pair-row metrics. Computation uses float64, machine-readable outputs retain full serialized precision, human tables display six decimal places, and every decision comparison uses the unrounded value.

Possession-weighted MAE and RMSE are mandatory secondary diagnostics for Ridge and baseline:

- weighted MAE is `sum(POSS_i * abs(e_i)) / sum(POSS_i)`;
- weighted RMSE is `sqrt(sum(POSS_i * e_i^2) / sum(POSS_i))`.

They cannot replace or override the unweighted evaluation.

## Primary and large-error gates

The primary scientific statistic is unweighted pair-row MAE over all 2,700 rows. Ridge must achieve `baseline MAE - Ridge MAE >= 0.10` NET_RATING points.

The 0.10 threshold reuses the Phase 3D simplicity/materiality band. It is a project policy threshold, not a universal statistical law.

Interpretation is fixed:

- improvement at least 0.10 passes the primary model-value gate;
- positive improvement below 0.10 is numerically better but fails materiality;
- zero or negative improvement fails to outperform the baseline.

The corroboration gate is unweighted pooled RMSE on the identical 2,700 rows. Ridge RMSE must be no worse than baseline RMSE, so `baseline RMSE - Ridge RMSE >= 0`. No separate 0.10 RMSE margin applies.

## Historical-stability warnings

Historical absolute performance is diagnostic, not an automatic pass/fail boundary. The selected Phase 3D Ridge has macro validation-season MAE `7.113451159210443`, pooled MAE `7.116374337661991`, worst-season MAE `7.596126328447196`, pooled RMSE `9.422213701344353`, and worst-season RMSE `10.330015941206614`.

Flag holdout Ridge MAE above `8.096126328447196`, which is more than 0.50 above the historical worst-season MAE. Also flag Ridge RMSE above `10.330015941206614`.

For R², signed bias, Spearman, prediction SD, target SD, and prediction-to-target SD ratio, report the holdout value against each of the six historical fold values and the pooled value. Report the delta from pooled and flag a value outside the six-fold minimum/maximum range. Separately flag absolute bias above the largest historical fold absolute bias. The exact reference values are embedded in the machine-readable policy and verified against `candidate_metrics.csv`.

A stability flag is evidence of possible temporal deterioration or distribution shift requiring interpretation. It cannot authorize redesign and is not automatically scientific failure when the baseline-relative gates pass.

## Missing-history diagnostics

Use exactly `complete`, `one_missing`, and `both_missing`. For each, report row count, MAE, RMSE, signed bias, and MAE minus complete-history MAE.

The frozen R2 counts are 2,139 complete, 523 one-missing, and 38 both-missing. At least 100 rows is adequate for formal comparison. Complete and one-missing therefore qualify; both-missing is descriptive and uncertain. A subgroup MAE difference with absolute magnitude at least 0.50 relative to complete history is material. For confidence-label interpretation, the established adverse rule is specifically `group MAE - complete MAE >= 0.50`.

These results do not decide the overall pass and are not causal. They assess whether the `standard` label for complete history and `lower` label for missing history remain empirically sensible. The 38-row both-missing group cannot validate or invalidate its confidence tier.

## Team and leave-one-team-out diagnostics

For every retained team report eligible rows, summed possessions, MAE, RMSE, bias, mean target, and mean prediction. Report the best and worst team MAE as descriptive concentration checks, with numeric team ID as the tie-break.

For each team, remove only that team's rows and recompute pooled unweighted MAE without refitting the model. Report remaining rows, leave-one-team-out MAE, and full-sample MAE minus leave-one-team-out MAE. This diagnoses whether one team disproportionately controls the pooled result.

The sign is fixed: `full-sample MAE - leave-one-team-out MAE > 0` means removing that team lowers pooled MAE, so the team raises overall error. A negative value means removing that team raises pooled MAE. Zero means no change at retained machine precision. This diagnostic cannot authorize removing a team.

No team may be removed after errors are seen. Team results are not independent model-selection tests, small samples require caution, and no coaching, roster, or causal chemistry explanation may be inferred.

## Exact-250 diagnostic

Report an exact-250 subgroup only for retained rows where `endpoint_exact_250_flag` is true. Charlotte and Philadelphia remain excluded and cannot be reintroduced. If no retained row has the flag, report `not applicable`. Never manufacture a subgroup or substitute historical exact-250 rows. This diagnostic is not a decision gate.

## Calibration, tails, residuals, and dispersion

No calibrator may be fitted. Reuse Phase 3D's deterministic ten-bin prediction-rank procedure on the full holdout:

1. Sort by prediction ascending, numeric team ID, numeric Player 1 ID, and numeric Player 2 ID.
2. For zero-based sorted index `j`, assign `bin = 1 + floor(j * 10 / 2700)`.
3. The 2,700-row population therefore yields ten bins of exactly 270 rows.
4. Report bin number, row count, mean prediction, mean target, and `calibration difference = mean target - mean prediction`.
5. Bin 1 is the lower tail and bin 10 is the upper tail. Positive difference means underprediction; negative means overprediction; zero means aligned.

Define residual as `target - prediction`. Against both prediction and pair possessions, report Pearson correlation and the ordinary least-squares slope with an intercept, computed as population covariance divided by population variance. Also report prediction SD, target SD, and their ratio using `ddof=0`.

For residual-versus-prediction, report both slope and Pearson correlation as null with explicit reasons when prediction variance is zero. For residual-versus-possessions, report both as null with explicit reasons when possessions variance is zero. If residual variance is zero, both Pearson correlations are null with reasons; OLS slopes remain defined when their independent-variable variances are nonzero. Do not emit NaN or infinity; emit a machine null and reason.

Calibration and tail results are diagnostic. They may motivate a separately authorized research phase after the holdout is formally spent, but cannot change current predictions or justify fitting a calibrator during this evaluation.

## Exact future R4 output contract

The future runtime output directory is exactly `modeling/phase3e-r4/`. It is Git-ignored and distinct from commit-eligible implementation source, tests, and the human report. R3 creates no R4 artifact.

The complete ordered runtime inventory is:

1. `execution_configuration.json`
2. `pre_metric_integrity.json`
3. `predictions.csv`
4. `overall_metrics.json`
5. `missing_history_metrics.csv`
6. `team_metrics.csv`
7. `leave_one_team_out_metrics.csv`
8. `calibration_bins.csv`
9. `residual_diagnostics.json`
10. `historical_stability.json`
11. `evaluation_decision.json`
12. `artifact_hashes.json`
13. `summary.json`

The commit-eligible human report is exactly `PHASE3E_R4_DEVELOPMENT_HOLDOUT_EVALUATION_REPORT.md`.

### Artifact sensitivity and reveal contract

Every runtime schema uses exactly these sensitivity meanings: `contains_row_level_target` and `contains_row_level_prediction` identify direct per-holdout-row values; `contains_target_derived_results` and `contains_prediction_derived_results` identify aggregates, diagnostics, comparisons, warnings, or classifications computed from holdout targets or predictions. Direct row values alone do not set the derived-result flags. `sensitivity_class` is one of `configuration_only`, `pre_metric_integrity_only`, `row_level_evaluation`, `aggregate_evaluation`, or `artifact_bookkeeping`.

| Artifact | Row target | Row prediction | Target-derived result | Prediction-derived result | Sensitivity class | Pre-Stage-A write/open | Reveal only after Stage B computation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `execution_configuration.json` | false | false | false | false | `configuration_only` | true | false |
| `pre_metric_integrity.json` | false | false | false | false | `pre_metric_integrity_only` | true | false |
| `predictions.csv` | true | true | false | false | `row_level_evaluation` | false | true |
| `overall_metrics.json` | false | false | true | true | `aggregate_evaluation` | false | true |
| `missing_history_metrics.csv` | false | false | true | true | `aggregate_evaluation` | false | true |
| `team_metrics.csv` | false | false | true | true | `aggregate_evaluation` | false | true |
| `leave_one_team_out_metrics.csv` | false | false | true | true | `aggregate_evaluation` | false | true |
| `calibration_bins.csv` | false | false | true | true | `aggregate_evaluation` | false | true |
| `residual_diagnostics.json` | false | false | true | true | `aggregate_evaluation` | false | true |
| `historical_stability.json` | false | false | true | true | `aggregate_evaluation` | false | true |
| `evaluation_decision.json` | false | false | true | true | `aggregate_evaluation` | false | true |
| `artifact_hashes.json` | false | false | false | false | `artifact_bookkeeping` | false | true |
| `summary.json` | false | false | true | true | `aggregate_evaluation` | false | true |

`artifact_hashes.json` contains no row-level or aggregate target/prediction values itself, but its hashes indirectly identify sensitive generated evidence. Before Stage A closes, only `execution_configuration.json` and `pre_metric_integrity.json` may be written, opened, or revealed as final artifacts. The pre-metric artifact is revealed only after it is atomically finalized; on failure it is the integrity-failure record.

The deterministic prediction failure-safe mechanism is memory-only buffering. The sole 2,700-value Ridge prediction vector remains in memory while its Stage A finiteness, alignment, symmetry, estimator-identity, and immutability checks run. No temporary or final prediction file is created. Only after `pre_metric_integrity.json` is written and closed with Stage A passing may `predictions.csv` be serialized and aggregate computation begin. The sensitive prediction file and all aggregate-evaluation artifacts remain unrevealed until Stage B computation is complete. If Stage A fails, publish no prediction or performance artifact and persist only `execution_configuration.json` plus the finalized `pre_metric_integrity.json` failure evidence.

### JSON artifact schemas

- `execution_configuration.json` freezes `version`, `policy_identity` with `relative_path,deterministic_content_sha256,serialized_byte_sha256`, `input_artifacts` entries with `relative_path,serialized_byte_sha256`, `estimator` with `family,constructor_parameters`, `training_seasons`, `training_rows`, `training_weight_policy`, `preprocessing_state_identity` with its path and both hashes, ordered `feature_order`, `baseline` with its definition, target column, training-population path/hash/count/seasons/weight policy, `environment_versions`, and `prohibited_operation_confirmations` for network, final-test-season, alternate-estimator/prediction, and calibrator/transform activity. It contains no target or prediction values.
- `pre_metric_integrity.json` contains `version`, `policy_identity`, one ordered `stage_a_gate_results` entry per Stage A gate, `stage_a_pass`, `training_rows`, `holdout_rows`, `feature_count`, `prediction_count`, `finite_target_count`, `finite_prediction_count`, `estimator_identity`, `input_cache_fingerprints_before`, `input_cache_fingerprints_after_prediction`, and `sequence_evidence`. Fingerprints sort by path. Sequence evidence records ordered event numbers and a UTC finalization timestamp; metric calculation may begin only at the next event, and downstream metric artifacts must identify the SHA-256 of this written-and-closed artifact. It contains no performance metric, target summary, prediction value, or prediction-performance comparison.
- `overall_metrics.json` contains `version`, `row_count`, `ridge_unweighted`, `baseline_unweighted`, `improvements`, `possession_weighted`, `dispersion`, `exact_250_diagnostic`, `null_reasons`, and `pre_metric_integrity_sha256`. Both unweighted objects contain MAE, RMSE, R², bias, Spearman, prediction SD, target SD, and prediction-to-target SD ratio. `improvements` contains baseline-minus-Ridge MAE and RMSE. `possession_weighted` contains Ridge and baseline MAE/RMSE. `dispersion` contains both prediction SDs, target SD, and both SD ratios. `exact_250_diagnostic` contains `applicable,row_count,mae,rmse,bias,not_applicable_reason`; when no retained row carries the flag, the three metrics are null and the reason is populated.
- `residual_diagnostics.json` contains `version`, `row_count`, `residual_sign_convention`, `residual_mean`, `residual_variance`, `prediction_variance`, `possessions_variance`, both residual Pearson correlations, both OLS slopes, and `null_reasons`.
- `historical_stability.json` contains `version`, `holdout_values`, `historical_pooled_reference`, chronological `historical_fold_references`, `deltas_from_pooled`, `fold_range_comparisons`, and every `warning_flags` result.
- `evaluation_decision.json` contains only `version`, `stage_a_pass`, `stage_b_pass`, unrounded `mae_improvement`, unrounded `rmse_improvement`, ordered `gate_outcomes` entries with `stage,gate_id,passed`, and exactly one `classification`. `override`, `discretionary_override`, and `alternate_classification` fields are prohibited.
- `artifact_hashes.json` contains `version`, `payload_artifacts`, `excluded_from_own_byte_manifest`, and `deterministic_content_sha256`. Each payload entry contains exactly `relative_path,serialized_byte_sha256`. It byte-hashes exactly the first 11 artifacts in the inventory. It excludes itself and `summary.json` to avoid recursive hashing and defines that complete payload inventory.
- `summary.json` contains `version`, `policy_identity` with `relative_path,deterministic_content_sha256,serialized_byte_sha256`, `artifact_manifest_canonical_sha256`, `final_classification`, `required_row_counts`, `generated_artifact_count`, `final_test_season_accessed`, `network_accessed`, and `alternate_model_generated`.

All JSON objects serialize with sorted keys; arrays retain the orders declared here.

### CSV artifact schemas

- `predictions.csv` has exactly 2,700 rows ordered by `row_position` 0 through 2699, identical to R2 order. Columns are exactly `row_position,target_season,team_id,player_1_id,player_2_id,target_net_rating,ridge_prediction,baseline_prediction,pair_possessions,history_status,endpoint_exact_250_flag`. It is the only runtime artifact containing row-level targets or predictions. No alternate-model, HGB, alternate-alpha, or calibrated prediction column is allowed.
- `missing_history_metrics.csv` has exactly three rows ordered `complete`, `one_missing`, `both_missing`. Columns are exactly `history_group,row_count,mae,rmse,bias,mae_difference_from_complete,adequate_for_formal_comparison,material_absolute_difference,adverse_lower_confidence_difference`.
- `team_metrics.csv` has exactly 28 rows ordered by numeric team ID. Columns are exactly `team_id,eligible_rows,summed_possessions,mae,rmse,bias,mean_target,mean_prediction`.
- `leave_one_team_out_metrics.csv` has exactly 28 rows in the same team order. Columns are exactly `removed_team_id,remaining_rows,leave_one_team_out_mae,full_sample_mae,full_sample_minus_leave_one_team_out_mae`.
- `calibration_bins.csv` has exactly ten rows ordered by bins 1 through 10, with exactly 270 observations per bin. Columns are exactly `bin,tail,row_count,mean_prediction,mean_target,calibration_difference`.

The CSV contract is UTF-8 without BOM, comma delimiter, double quote with minimal quoting, exact declared columns and row orders, LF line endings including a final LF, base-10 integers, shortest round-trip full-precision finite floats, empty fields for null, and lowercase `true`/`false`. JSON is UTF-8 without BOM, sorted-key, two-space-indented, `allow_nan=false`, uses JSON `null`, retains shortest round-trip full-precision finite numbers, and ends with one LF. Six-decimal rounding is human display only; gates use unrounded machine values.

The R4 mutation allowlist permits only the exact 13 ignored runtime artifacts above, the named commit-eligible report, and the separately predeclared commit-eligible implementation files `src/pair_fit_v2/phase3e_r4_evaluation.py`, `src/pair_fit_v2/phase3e_r4_cli.py`, and `tests/test_phase3e_r4_evaluation.py`. No other runtime path may be created or modified.

## Stage A: pre-metric integrity gates

Every Stage A gate must be completed and persisted before any aggregate, subgroup, team, calibration, residual, or classification result is calculated or revealed. Target comparison before `pre_metric_integrity.json` is finalized is prohibited except for alignment, row-count, identity, and finiteness checks.

1. `pinned_input_hashes`: all policy, Phase 3B, Phase 3D, and Phase 3E-R2 pinned hashes match before use.
2. `training_holdout_row_counts`: training has exactly 27,001 rows and holdout index, matrix, and target vector each have exactly 2,700 aligned rows.
3. `feature_count_order`: training and holdout matrices have the same 45 unique ordered features.
4. `finite_estimator_matrix`: every training and holdout estimator value is present and finite.
5. `finite_target_vector`: all 2,700 directly returned targets are finite. Finite aggregate improvements are not a substitute.
6. `estimator_identity`: the sole estimator is the frozen Ridge at alpha 3000 under the frozen environment contract.
7. `training_population_weights`: training is the exact hash-pinned 2014-15 through 2023-24 population with equal weights and normal exact-250 inclusion.
8. `training_only_preprocessing`: frozen full-training medians, fills, feature order, and scaling are used; 2024-25 refits nothing.
9. `transformation_compatibility`: reconstructed training and already transformed R2 holdout matrices use identical frozen preprocessing, feature meanings, order, and scaling.
10. `row_key_alignment`: zero-based R2 row position and canonical key align index, staging target, matrix, and prediction without a silent sort or join change.
11. `excluded_teams_absent`: Charlotte and Philadelphia are absent.
12. `canonical_unique_pairs`: numeric `player_1_id < player_2_id`, and each observation key is unique.
13. `prediction_symmetry`: R2's 121,500-value swap proof is intact, prediction uses only the 45 symmetric columns, and no player-slot input enters prediction.
14. `single_authorized_prediction_vector`: exactly one 2,700-value vector is generated by the authorized Ridge and no other prediction vector exists.
15. `finite_prediction_vector`: all 2,700 Ridge predictions are finite. Finite aggregate improvements are not a substitute.
16. `no_calibrator_prediction_transform`: no calibrator or prediction transform is fitted or applied.
17. `no_alternate_estimator_prediction`: no fallback, ensemble, HGB, alternate alpha, or alternate-model prediction is generated.
18. `offline_protected_scope`: no network and no 2025-26 path or evidence access.
19. `input_cache_immutability`: all pinned inputs and all 129 cache fingerprints match both pre-run and post-prediction snapshots.

The feasible execution sequence is fixed:

1. Verify immutable inputs and policy.
2. Load and validate the target and estimator inputs.
3. Construct the training matrix using the frozen full-training preprocessing state.
4. Fit exactly one authorized Ridge.
5. Generate exactly one prediction vector.
6. Verify prediction finiteness, alignment, symmetry contract, estimator identity, and input/cache immutability.
7. Write and close `pre_metric_integrity.json`.
8. Only then calculate performance metrics.

Prediction generation is allowed before metric reveal. The finalized pre-metric artifact must contain no performance metric, target summary, or prediction-performance comparison.

## Stage B: post-computation completeness checks

After Stage A is finalized and metrics are computed, all Stage B checks must pass before final handoff:

1. `required_metrics_diagnostics_complete`: every predeclared metric and diagnostic was calculated.
2. `required_outputs_retained`: every required machine artifact and the human report was retained.
3. `unfavorable_results_retained`: no unfavorable result was omitted or selectively reported.
4. `output_schema_row_counts`: every output matches its frozen schema, key/column inventory, row count, and ordering.
5. `mutation_allowlist`: only the predeclared R4 output, source, test, and report paths changed.
6. `output_hashes_reconcile`: payload byte hashes, artifact-manifest canonical hash, and summary references reconcile.
7. `single_frozen_classification`: exactly one frozen classification was assigned with no discretionary override.
8. `human_machine_agreement`: the report agrees with all machine artifacts, gate outcomes, metrics, warnings, and classification.

Failure of either Stage A or Stage B yields `INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE`. It is not scientific evidence against Ridge. Correct only the defect under a separately authorized, narrowly audited pass before rerunning.

## Exhaustive classification logic

Use unrounded improvements and apply exactly one classification only after both stages are known:

1. `VALID DEVELOPMENT-HOLDOUT PASS`: Stage A and Stage B pass, both improvements are finite, MAE improvement is at least 0.10, and RMSE improvement is nonnegative.
2. `VALID DEVELOPMENT-HOLDOUT MIXED RESULT`: Stage A and Stage B pass, both improvements are finite, and either MAE improvement is positive but below 0.10, or MAE improvement is at least 0.10 while RMSE improvement is negative.
3. `VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE`: Stage A and Stage B pass, both improvements are finite, and MAE improvement is zero or negative.
4. `INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE`: any mandatory Stage A pre-metric gate fails; any mandatory Stage B completeness check fails; or MAE improvement or RMSE improvement is NaN, positive infinity, or negative infinity.

A mixed result requires interpretation and a new user decision; it does not authorize silent progression or redesign. A scientific failure requires reporting the frozen result and deciding whether to end production work or start a separately authorized research phase. It does not authorize automatic redesign. Once inspected, 2024-25 is spent as development evidence.

## Reporting and interpretation rules

Diagnostic metrics cannot override a failed primary gate. Subgroup and team differences are noncausal. Calibration findings cannot authorize a calibrator. No row, team, feature, or metric may be removed after results are seen. No alternate alpha or HGB result may be generated. Selective reporting is prohibited, and every predeclared output must be retained even when unfavorable.

## Determinism and artifact policy

The policy builder uses sorted-key JSON, two-space indentation, ASCII escapes, no NaN values, UTF-8 encoding, and one trailing line feed. The embedded content hash is SHA-256 over compact sorted-key JSON after removing the `deterministic_content_sha256` field. Two independent builds must be byte-identical.

The generated JSON remains under the established Git-ignored `modeling/` artifact policy. This Markdown policy, narrowly reusable policy builder, and focused tests are commit-eligible. Phase 3E-R3 does not authorize committing or pushing them.
