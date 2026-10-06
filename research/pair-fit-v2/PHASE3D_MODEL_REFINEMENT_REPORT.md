# Phase 3D: bounded model refinement and pre-holdout design selection

## Conclusion

**Phase 3D design frozen; 2024-25 development holdout ready for separate authorization.**

The provisional design is Ridge, `POSS >= 150`, equal training weights, no shot features, and normal inclusion of the four exact-250 team-seasons. This is a pre-holdout research choice, not a final evaluation, production model, or causal claim.

The selected Ridge result has macro validation-season MAE 7.1135, pooled MAE 7.1164, macro RMSE 9.4109, pooled RMSE 9.4222, pooled R² 0.0639, pooled bias +0.5243, and pooled Spearman 0.3246. Its prediction standard deviation is 3.1418 versus target standard deviation 9.7383.

## Scope and immutable preflight

The run used only Phase 3B training-era rows whose target seasons are 2014-15 through 2023-24. The six outer validation seasons are 2018-19 through 2023-24. Every inner and outer training season precedes its validation season. Protected-season path names are rejected before hashing or opening an input.

The prerequisite values reproduced without replay:

| Artifact | SHA-256 type | Verified value |
| --- | --- | --- |
| Phase 3A | documented content | `dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f` |
| Phase 3A.1 | documented content | `54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47` |
| Phase 3B `POSS >= 150` CSV | serialized bytes | `da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8` |
| Phase 3B `POSS >= 100` CSV | serialized bytes | `cf01683e4923e34763f9ad7e62b16a7f07c7e1afd993ea26c3501cf67fcb594a` |
| Phase 3B feature manifest | serialized bytes | `ca137b375fa6613478ed826fa61eadd808d813e81e03311b2f70223e7ee25103` |
| Phase 3B summary | canonical content, historical spaced JSON | `70650038719f7a4f70505305cb00643f4b96e5753419a45691f594534b2e07b1` |
| Phase 3C summary | canonical content, compact JSON | `c9cddb3710389183134e039830a6486f9d5981a1c7e867dd1a6a70def3b50ac3` |
| Phase 3C summary | serialized bytes | `e10e233a435a38d13d66c65bb77a9a325b0f03bee26d77edf87741f173990d55` |

No network request, raw-evidence mutation, holdout access, database, Parquet/Feather/pickle/joblib/model serialization, production integration, commit, or push occurred.

## Frozen staged design

Stage A contained exactly 12 candidates: two thresholds by three training-weight policies by Ridge/fixed HGB, using distribution features. Stage B advanced one threshold/weight design per estimator and compared no-shot, distribution-only, and distribution-plus-smoothed-efficiency. Stage C applied include, 0.5 downweight, and exclude training policies to each leading family configuration. Stage D produced diagnostics for the two family finalists and applied the predeclared Ridge-versus-HGB rule.

The primary statistic was unweighted macro validation-season MAE. A simpler candidate was preferred only when its MAE was strictly less than 0.10 above the best candidate. The frozen simplicity orders were `150` before `100`, equal before square-root before capped-linear, no-shot before distribution before efficiency, and include before downweight before exclude. An adequate missing-history subgroup was predeclared as at least 100 validation rows.

Ridge used only `[0.1, 1, 10, 100, 1000, 3000, 10000]`, with the Phase 3C smaller-alpha exact-tie rule. HGB retained the Phase 3C configuration unchanged: learning rate 0.05, 200 iterations, 15 leaf nodes, minimum leaf size 50, L2 regularization 5, `early_stopping=False`, and `random_state=314159`. No other estimator was allowed.

## Population coverage and threshold result

`POSS >= 150` has 27,001 total training-era rows and 16,751 outer-validation predictions. `POSS >= 100` has 30,580 rows and 19,112 outer-validation predictions. Both cover all 300 team-seasons; every validation fold covers 30 team-seasons.

| Validation | Train rows ≥150 | Validation rows ≥150 | Train rows ≥100 | Validation rows ≥100 |
| --- | ---: | ---: | ---: | ---: |
| 2018-19 | 10,250 | 2,797 | 11,468 | 3,172 |
| 2019-20 | 13,047 | 2,548 | 14,640 | 2,886 |
| 2020-21 | 15,595 | 2,798 | 17,526 | 3,215 |
| 2021-22 | 18,393 | 3,002 | 20,741 | 3,406 |
| 2022-23 | 21,395 | 2,858 | 24,147 | 3,256 |
| 2023-24 | 24,253 | 2,748 | 27,403 | 3,177 |

The `100-149` rows were substantially noisier: under equal weights their out-of-season MAE/RMSE were 13.0609/16.6024 for Ridge and 12.9451/16.2586 for HGB. Training on the ≥100 population did not improve the common ≥150 validation slice: Ridge MAE was 7.1329 versus 7.1132 when trained/evaluated at ≥150; HGB was 7.1011 versus 7.0724. The extra rows therefore added noisier targets without useful evidence for the common higher-exposure population. `POSS >= 150` advances.

## Stage A: weighting

All metrics below are unweighted validation metrics. R², bias, Spearman, and dispersion are pooled; the primary MAE is macro by validation season.

| Estimator | POSS | Weight | Macro MAE | Pooled MAE | Pooled RMSE | R² | Bias | Spearman | Pred SD / Target SD |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ridge | 150 | equal | 7.1107 | 7.1132 | 9.4268 | 0.0630 | +0.5596 | 0.3266 | 3.1780 / 9.7383 |
| Ridge | 150 | sqrt(POSS) | 7.1097 | 7.1124 | 9.4640 | 0.0555 | +1.0908 | 0.3318 | 3.4401 / 9.7383 |
| Ridge | 150 | min(POSS,300) | 7.1011 | 7.1036 | 9.4169 | 0.0649 | +0.6812 | 0.3290 | 3.2434 / 9.7383 |
| Ridge | 100 | equal | 7.8604 | 7.8652 | 10.5620 | 0.0403 | +0.4269 | 0.2896 | 3.1951 / 10.7816 |
| Ridge | 100 | sqrt(POSS) | 7.8668 | 7.8725 | 10.6462 | 0.0250 | +1.1719 | 0.2958 | 3.3917 / 10.7816 |
| Ridge | 100 | min(POSS,300) | 7.8531 | 7.8582 | 10.5909 | 0.0351 | +0.7675 | 0.2944 | 3.2662 / 10.7816 |
| HGB | 150 | equal | 7.0697 | 7.0724 | 9.2786 | 0.0922 | +0.5969 | 0.3239 | 3.2710 / 9.7383 |
| HGB | 150 | sqrt(POSS) | 7.0846 | 7.0884 | 9.3088 | 0.0863 | +1.0469 | 0.3262 | 3.3535 / 9.7383 |
| HGB | 150 | min(POSS,300) | 7.0706 | 7.0737 | 9.2832 | 0.0913 | +0.6941 | 0.3245 | 3.2851 / 9.7383 |
| HGB | 100 | equal | 7.8173 | 7.8231 | 10.4048 | 0.0687 | +0.4983 | 0.2840 | 3.2711 / 10.7816 |
| HGB | 100 | sqrt(POSS) | 7.8171 | 7.8236 | 10.4335 | 0.0635 | +1.0698 | 0.2910 | 3.3821 / 10.7816 |
| HGB | 100 | min(POSS,300) | 7.8016 | 7.8078 | 10.4051 | 0.0686 | +0.7668 | 0.2902 | 3.2739 / 10.7816 |

Equal weights advance for both estimators. Equal is HGB's numerical winner. Capped-linear is Ridge's numerical winner by only 0.0096 macro MAE, far inside the 0.10 simplicity band. Square-root weighting gives no primary advantage and roughly doubles positive bias. In the latest outer training fold, equal weights have ESS 24,253; square-root has ESS 20,348 and top-decile share 19.36%; capped-linear has ESS 23,723 and top-decile share 10.74%. All were normalized to mean one using training rows only.

## Stage B: shot ablation and smoothing

The existing six shot-distribution means plus L1 distance were retained unchanged when distribution features were enabled. Efficiency adds 14 symmetric features: a pair mean and absolute difference for each of restricted area, non-restricted paint, mid-range, combined corners, above-the-break three, backcourt, and unclassified residual.

Each zone prior is `sum(FGM)/sum(FGA)` across unique valid player-season profiles in the applicable training partition. Each slot value is `(FGM + k * prior)/(FGA + k)`. Validation rows never enter priors. Missing or invalid counts and zero/nonpositive attempts remain undefined until training-only player-slot imputation. Zero attempts are distinct from a defined 0% result. Unclassified residuals remain their own zone and are never allocated elsewhere. Slot imputation precedes symmetric construction; any remaining L1 null is median-imputed at the symmetric-feature stage using training rows only.

| Estimator | Feature family | Macro MAE | Pooled MAE | Pooled RMSE | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Ridge | no shot | 7.1135 | 7.1164 | 9.4222 | advanced by simplicity |
| Ridge | distribution | 7.1107 | 7.1132 | 9.4268 | +0.0028 macro MAE vs best simple |
| Ridge | distribution + efficiency | 7.0955 | 7.0979 | 9.4037 | numerical best; only 0.0180 better than no-shot |
| HGB | no shot | 7.0844 | 7.0872 | 9.2904 | advanced by simplicity |
| HGB | distribution | 7.0697 | 7.0724 | 9.2786 | numerical best; only 0.0147 better than no-shot |
| HGB | distribution + efficiency | 7.0813 | 7.0846 | 9.2862 | efficiency worsened distribution by 0.0116 |

Smoothed efficiency did not materially help. Ridge selected `alpha=3000` and `k=100` in every outer fold for its efficiency variant. HGB selected `k=100` in five folds and `k=50` for 2020-21. The no-shot Ridge comparator reused the corresponding distribution alpha (`3000` in all six folds) rather than retuning against its ablated matrix.

## Stage C: exact-250 sensitivity

The flagged team-seasons were asserted to be exactly 2020-21 Houston and 2023-24 Toronto, Memphis, and Detroit. All 548 flagged validation rows remain in every comparison.

| Estimator | Training policy | Macro MAE | Pooled MAE | Pooled RMSE | Flagged MAE | Flagged RMSE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Ridge | include | 7.1135 | 7.1164 | 9.4222 | 9.6702 | 13.5429 |
| Ridge | downweight 0.5 | 7.1138 | 7.1168 | 9.4237 | 9.6803 | 13.5549 |
| Ridge | exclude | 7.1144 | 7.1174 | 9.4258 | 9.6931 | 13.5740 |
| HGB | include | 7.0844 | 7.0872 | 9.2904 | 8.9969 | 11.3170 |
| HGB | downweight 0.5 | 7.0875 | 7.0905 | 9.2933 | 8.9845 | 11.3068 |
| HGB | exclude | 7.0894 | 7.0926 | 9.2961 | 8.9959 | 11.3285 |

Normal inclusion is the overall numerical winner for both estimators. HGB's 0.5 policy improves the flagged slice by only 0.0123 MAE while worsening the primary macro MAE by 0.0031. This sensitivity does not support altering the population, and it is not interpreted as evidence that endpoint responses are incomplete.

## Stage D: finalists, stability, and estimator rule

| Validation season | Ridge MAE | Ridge RMSE | HGB MAE | HGB RMSE |
| --- | ---: | ---: | ---: | ---: |
| 2018-19 | 6.7297 | 9.0133 | 6.7440 | 8.8546 |
| 2019-20 | 6.8373 | 9.0445 | 6.8357 | 9.0739 |
| 2020-21 | 7.3233 | 9.5821 | 7.3122 | 9.5529 |
| 2021-22 | 7.1526 | 9.2997 | 7.1373 | 9.3024 |
| 2022-23 | 7.0417 | 9.1960 | 6.9897 | 9.1506 |
| 2023-24 | 7.5961 | 10.3300 | 7.4876 | 9.7698 |

HGB wins MAE in five of six seasons, improves pooled RMSE (9.2904 versus 9.4222), does not worsen an adequate missing-history subgroup by more than 0.25, and retains a small advantage outside both exact-250 and pandemic observations. Its macro MAE advantage is only 0.0290, however, so it fails the mandatory 0.10 improvement condition. The predeclared rule therefore retains Ridge.

The selected Ridge per-season R² ranges from -0.0061 in 2023-24 to 0.1056 in 2022-23. Bias is positive in five seasons and -0.1604 in 2019-20. Spearman ranges from 0.2701 to 0.3790. The worst-season MAE is 7.5961 in 2023-24.

## Missing-history confidence diagnostics

| History group | Rows | Ridge MAE | Ridge RMSE | HGB MAE | HGB RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete player history | 13,044 | 6.9048 | 9.1722 | 6.9005 | 9.0447 |
| One player missing | 3,408 | 7.7542 | 10.1105 | 7.6464 | 9.9734 |
| Both players missing | 299 | 9.0768 | 11.7634 | 8.8604 | 11.5285 |

For selected Ridge, one-missing MAE is 0.8495 above complete history and both-missing MAE is 2.1721 above it. Both groups exceed the predeclared 100-row adequacy floor and 0.50 materiality threshold. Provisional confidence labels are therefore `standard` for complete history and `lower` for one- or both-missing history. These labels are diagnostic only; no fallback model was created.

Every finalist prediction retains target season, team, canonical player IDs, target, prediction, possession exposure, missing-history group, second-stage symmetric-imputation flag, shot-L1 undefined reason, whether L1 was undefined because of missing/nonpositive overall FGA, per-slot/per-zone efficiency undefined reasons, exact-250 membership, and pandemic context. These fields remain outside estimator matrices.

## Calibration

No calibrator was fit. Both finalists strongly compress dispersion: selected Ridge predicts SD 3.1418 against target SD 9.7383; HGB predicts 3.2591 against 9.7383. Prediction-to-target SD is below 0.75 in every season for both. Upper-tail direction is not consistent for Ridge, and lower-tail direction is mixed for both. Under the frozen rule—which requires compression in at least five seasons and consistent direction in both tails—the evidence does not yet justify recommending a later calibrator. Dispersion compression remains a diagnostic concern to monitor in an independently authorized holdout; it is not established here as a stable correctable calibration mapping.

Calibration-bin observed/predicted means, season bias, tail direction, and residual relationships against predictions and possessions are in the deterministic diagnostics. No post-hoc selection or calibration was performed.

## Deterministic artifacts and hashes

The authoritative outputs are Git-ignored under `modeling/phase3d/`. All payloads use deterministic JSON or CSV serialization.

| Payload artifact | Serialized-byte SHA-256 |
| --- | --- |
| `calibration_diagnostics.csv` | `9847684de72c4703fd2912b4c05aca0e3a5324b953009c49bdc5ee5e27f2fde1` |
| `candidate_metrics.csv` | `670392a4f23b5bf9a802601577080bfdb34e0f9105e35f12e2995a5b2a62dd49` |
| `experiment_configuration.json` | `8af3a806b7a03a0524c89f64ca17d583be64b8b4976d4497da010ce692f0e4b9` |
| `feature_manifest.json` | `d3e607066a351c6ca7e5070dd3b72c0803f7423ce8e5d5826efe5ebba3a8f54d` |
| `finalist_predictions.csv` | `017154f10a0ab927dc2c07965a43606bac732125379e7808cc48bd6b2f0bedd8` |
| `fold_definitions.json` | `e5a1a3208b59983fa5e128309889579f77581ab1bf1bdc43a640e89175d6a1f4` |
| `imputation_diagnostics.csv` | `25a08d6450db3c4fc300f056aef33114d3a8462703c72603586f0c8b8d84c241` |
| `population_diagnostics.csv` | `76b72036e25e167cf3f81e4c5ffec90e8385a45fb9b51866827fe4f85e741fcf` |
| `residual_diagnostics.csv` | `2b37dca8d54f2d2477a40236f0a214a9cd860e14607a8910480effce9d9138c5` |
| `selection_decision.json` | `5ef9663dff906fc04b3a31aec56c0dce1ce9fe4e7cdcc87dbaab95762ff02ca0` |
| `smoothing_prior_diagnostics.csv` | `19ecb1ac1dab419be69175073c34a30d459317881cbf4137395b24b3846813d6` |
| `staged_candidate_registry.csv` | `d95aaabdd74e44f4373fd50a61f1e7fd8df607ededa599cf7616f7464681114b` |
| `subgroup_metrics.csv` | `8a7669a2adbf465f565bde4075e1a778f419922d28a62556707312d3dad10b75` |
| `tuning_diagnostics.csv` | `f545667cc399123e308660531d1c32ef4b5bacc73736d7ae023deee674df7db0` |
| `weight_diagnostics.csv` | `fa44ca5373aa7a0e28aa3aa7b98750800ce7445e6ae252e195583b0e44f77a74` |

`artifact_hashes.json` covers exactly those 15 payloads by byte hash and excludes itself and `summary.json` explicitly. Its canonical-content hash is `e7fd02b5f56014b2b89bab646c421946cf01b9744cbac72e0787cd80cd959aee`; its serialized-byte hash is `3acaf4be39965358eab17069b94fc88a09d377e0edc6ab7227bb2953a3711c67`. `summary.json` records the artifact-manifest content hash and is excluded from that byte manifest. Its canonical-content hash is `1db8765e938a061a2afa75901fe408e42e592f47fa3e7e30f867bc4b9d05a088`; its serialized-byte hash is `431fc8e34ba26e1e06dd034e1014aa519c8bef028d0cebd5289375aa60efcb5c`.

## Verification

Focused Phase 3D tests pass: 16 tests in 1.34 seconds. The complete offline research suite passes: 371 tests in 392.72 seconds, using the short root `.t/phase3d-full` base and no pytest cache writes. Two independent complete executions wrote 17 artifacts each, and all 17 were byte-identical. An independent recomputation directly from 33,502 finalist prediction rows matched 12 pooled/macro metrics for each finalist to absolute tolerance `1e-12`.

`git diff --check`, ignore checks, prohibited-artifact checks, and explicit protected-season checks passed at final handoff.

## Interpretation limits

The pair population overlaps in players and pairs and is conditioned on observed shared possessions; it is not a census of all theoretical pairings. Threshold, weight, shot, exact-250, and missing-history results are predictive diagnostics, not causal evidence about chemistry, coaching decisions, injuries, roster construction, or endpoint completeness. The 2024-25 development holdout and 2025-26 final test remain unopened and require separate authorization.
