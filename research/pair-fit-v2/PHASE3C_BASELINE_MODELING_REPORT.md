# Phase 3C: leakage-safe rolling historical baselines

## Conclusion

The baseline pipeline is technically supported: it is deterministic, chronologically leakage-safe, symmetric under player-slot swapping, finite, and better than the training-mean baseline on the six authorized out-of-season validations. The fixed nonlinear baseline is only modestly better than Ridge, and the shot-family gains are small. These are prediction results, not evidence that player chemistry or shot-profile similarity causes pair outcomes. No production model is selected.

## Scope and immutable preflight

The run used only the Phase 3B `POSS >= 150` primary population: 27,001 rows, equal row weights, and unmodified `NET_RATING` targets. It rejected any target season outside 2014-15 through 2023-24 before fitting. It did not load 2024-25 or 2025-26 outcomes, make a network request, modify raw evidence, or serialize a model.

The input hashes reproduced as follows:

| Artifact | Result |
| --- | --- |
| Phase 3A content | `dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f` |
| Phase 3A.1 content | `54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47` |
| Primary CSV byte hash | `da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8` |
| Sensitivity CSV byte hash | `cf01683e4923e34763f9ad7e62b16a7f07c7e1afd993ea26c3501cf67fcb594a` |
| Feature manifest byte hash | `ca137b375fa6613478ed826fa61eadd808d813e81e03311b2f70223e7ee25103` |
| Curation summary deterministic-content hash | `70650038719f7a4f70505305cb00643f4b96e5753419a45691f594534b2e07b1` |

The stale canonical manifest (`f32ecf…`, 9,024 bytes) and summary (`9f5878…`) were reproducible derived copies, not corrupted raw evidence. An isolated replay from committed Phase 3B source produced the required manifest byte hash and the required summary **content** hash. The serialized summary byte hash is `7fe573b…`; `706500…` is the summary's own documented deterministic-content hash, not its file byte hash. The stale manifest omitted the later authoritative category, category-partition note, estimator specifications, and reliability-metadata sections. The stale and replayed summaries had the same top-level schema, but the corrected manifest lineage/artifact values and content hash differed. The authorized canonical derived directory was refreshed only after this replay passed.

## Validation and preprocessing

| Validation season | Training seasons |
| --- | --- |
| 2018-19 | 2014-15–2017-18 |
| 2019-20 | 2014-15–2018-19 |
| 2020-21 | 2014-15–2019-20 |
| 2021-22 | 2014-15–2020-21 |
| 2022-23 | 2014-15–2021-22 |
| 2023-24 | 2014-15–2022-23 |

The shot-enabled matrix has 52 exact Phase 3B-approved symmetric features; no-shot removes only its seven shot-family features, leaving 45. Slot-level medians use unique observed `(player_id, selected_profile_season)` profiles in the current training fold, never pair-row frequency or validation rows, and apply the same value to either player slot. Symmetric means/differences and the approved L1 shot-distance are constructed only after this imputation. An observed zero overall-FGA denominator correctly leaves the L1 formula undefined; a second training-only median at the already-symmetric feature level fills only that resulting null for finite Ridge/HGB matrices. Ridge scaling is training-only.

The fixed HGB configuration was `learning_rate=0.05`, `max_iter=200`, `max_leaf_nodes=15`, `min_samples_leaf=50`, `l2_regularization=5`, `early_stopping=false`, and `random_state=314159`. Ridge alpha grid was `[0.1, 1, 10, 100, 1000]`, selected by mean inner expanding-fold MAE with a lower-alpha exact-tie break. Every outer fold selected `1000.0` (inner MAEs: 6.826, 6.777, 6.802, 6.929, 6.966, 6.975).

## Results

All models have 16,751 out-of-season validation predictions. Aggregate MAE/RMSE/R² are row aggregates; no independence or significance inference is made from overlapping pair rows.

| Variant | MAE | RMSE | R² | Bias | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training mean | 7.579 | 9.739 | -0.000 | 0.015 | -0.005 |
| Ridge, no shot | 7.114 | 9.451 | 0.058 | 0.569 | 0.325 |
| Ridge, shot enabled | 7.108 | 9.452 | 0.058 | 0.598 | 0.328 |
| HGB, no shot | 7.087 | 9.290 | 0.090 | 0.529 | 0.318 |
| HGB, shot enabled | 7.072 | 9.279 | 0.092 | 0.597 | 0.324 |

The HGB MAE improvement over shot-enabled Ridge is 0.036 (about 0.5% of Ridge MAE), so this baseline does not establish a material nonlinear advantage. Both learned families consistently beat the mean baseline across all six seasons.

| Season | Mean | Ridge shot | Ridge no shot | HGB shot | HGB no shot |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2018-19 | 7.152 | 6.728 | 6.740 | 6.728 | 6.744 |
| 2019-20 | 7.199 | 6.851 | 6.847 | 6.830 | 6.836 |
| 2020-21 | 7.793 | 7.309 | 7.318 | 7.288 | 7.312 |
| 2021-22 | 7.635 | 7.114 | 7.142 | 7.125 | 7.137 |
| 2022-23 | 7.603 | 7.021 | 7.028 | 6.973 | 6.990 |
| 2023-24 | 8.064 | 7.614 | 7.590 | 7.475 | 7.488 |

Shot-enabled minus no-shot aggregate deltas are -0.005 MAE / +0.001 RMSE for Ridge and -0.015 MAE / -0.012 RMSE for HGB. HGB MAE improves in every season, but its RMSE worsens in 2019-20 and 2023-24; Ridge improves MAE in four of six seasons and worsens in two. The small, mixed scale does not warrant rewriting the shot contract or making a theory claim.

For shot-enabled HGB, complete-history rows have MAE 6.883 (13,044 rows), one-missing rows 7.643 (3,408), and both-missing rows 8.860 (299; R² -0.038). Pandemic validations have MAE 7.070 (5,346) versus 7.074 non-pandemic (11,405), while R² is lower in pandemic seasons (0.071 vs 0.102). The four exact-250 team-season flags yield 548 validation rows with MAE 9.023 and R² -0.387, versus 16,203 non-flag rows with MAE 7.006 and R² 0.095. These are descriptive sensitivity slices, not causal or inferential comparisons.

Each fold's calibration table uses ten deterministic prediction-rank bins. Overall HGB-shot prediction dispersion is substantially narrower than target dispersion (prediction standard deviation about 3.271 versus target standard deviation about 9.738). Upper-bin predictions exceed observed means in every fold, while lower-bin direction is mixed; tail-calibration direction is therefore mixed. This is a diagnostic finding, not proof of one universal calibration error or a basis for post-hoc recalibration in this phase.

## Determinism and verification

`summary.json` uses two distinct hashes: its canonical-content SHA-256 is `c9cddb3710389183134e039830a6486f9d5981a1c7e867dd1a6a70def3b50ac3`, computed by canonical JSON serialization after omitting its self-hash field; its serialized-byte SHA-256 is `e10e233a435a38d13d66c65bb77a9a325b0f03bee26d77edf87741f173990d55`, computed over the persisted bytes. `artifact_hashes.json` byte-hashes the eight payload artifacts. It explicitly excludes itself (self-reference) and `summary.json` (which records the manifest digest); both exclusions and their non-circular canonical-content policies are validated by regression tests. The obsolete `64da8a…` result belongs to the earlier output shape and is not evidence for this checkpoint.

The authoritative determinism evidence is the later manual isolated pair, `phase3c-a` and `phase3c-b`. Both exited 0, each produced the complete ten-file inventory, and every artifact was byte-identical between them. Each also matched every byte of the persisted `modeling/phase3c/` checkpoint, so no persisted derived artifact required replacement. Metrics and calibration recomputed independently from the prediction rows matched their stored tables exactly. The temporary pair was removed after this comparison; it was outside the project directory due to a missing output-path separator and was not source evidence.

Focused Phase 3C tests: 8 passed in 1.53 seconds (exit 0). They cover anchors, season/fold bounds, unique-profile and shared-slot imputation, a validation-only extreme-value leakage sentinel, transform ordering, swap symmetry, allowlist/ablation partition, metrics, calibration, fixed HGB configuration, and non-circular artifact-manifest coverage. The complete offline research suite previously passed **354 tests in 332.54 seconds** (exit 0) with its base temporary directory and JUnit output under root `.t/`.

## Limitations and next decisions

The returned pair population is not a census of all possible pairs; pair rows overlap and may reflect coaching, health, roster continuity and team context. Missing-history and exact-250 slices are notably harder. This phase neither tests weights/threshold sensitivities nor shot-efficiency smoothing, and it does not use either protected holdout.

Classification: **technically supported baseline pipeline; do not select a production model yet.** Before threshold, weighting, smoothing or holdout evaluation, decide a frozen model-design rule (including whether the small HGB/shot differences are practically meaningful), then authorize the separate `POSS >= 100`/weighting refinements and only afterward the 2024-25 development holdout. Keep 2025-26 untouched until that design is frozen.
