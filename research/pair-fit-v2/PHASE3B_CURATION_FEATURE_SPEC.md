# Phase 3B: deterministic curation and feature specification

## Classification

`Phase 3B deterministic curation and feature specification complete; modeling not started.`

This is an offline, cache-only production step. It reads the verified 2014-15 through 2023-24 raw pair outcomes, selects only prior player profiles from 2013-14 through 2022-23, and writes reproducible CSV artifacts under the Git-ignored `curated/phase3b/` path. It makes no network request, does not alter raw evidence, and does not fit an imputer, scaler, estimator, or any other model component.

## What one row means

One row is `team × target season × canonical unordered player pair`. The two player IDs are numerically sorted and duplicates/noncanonical keys fail before output. The target is the original target-season `NET_RATING`; it is retained unmodified and checked against `OFF_RATING - DEF_RATING` within 0.1. The target-period ratings are audit values, not features.

The primary population has `POSS >= 150`; a separate `POSS >= 100` sensitivity CSV is also written. Possessions and target-season shared minutes are eligibility/reliability data only, never predictors. The floor removes the noisiest tiny shared-court samples, but it also creates selection bias: retained pairs were used enough to accumulate possessions, which can reflect coaching, health, transactions, and team context rather than a census of all possible pair fit.

The Phase 3A returned source population reconciles exactly to 46,938 rows. `POSS >= 100` retains 30,580 (16,358 excluded) and `POSS >= 150` retains 27,001 (19,937 excluded). Per-season retention and missing-history coverage are:

| Target season | >=100 rows (complete / one / both missing) | >=150 rows (complete / one / both missing) |
| --- | ---: | ---: |
| 2014-15 | 3,010 (2,241 / 677 / 92) | 2,666 (2,025 / 571 / 70) |
| 2015-16 | 2,755 (2,142 / 578 / 35) | 2,491 (1,955 / 507 / 29) |
| 2016-17 | 2,778 (2,027 / 669 / 82) | 2,507 (1,867 / 574 / 66) |
| 2017-18 | 2,925 (2,045 / 770 / 110) | 2,586 (1,856 / 646 / 84) |
| 2018-19 | 3,172 (2,389 / 731 / 52) | 2,797 (2,152 / 605 / 40) |
| 2019-20 | 2,886 (2,150 / 663 / 73) | 2,548 (1,944 / 551 / 53) |
| 2020-21 | 3,215 (2,437 / 704 / 74) | 2,798 (2,158 / 581 / 59) |
| 2021-22 | 3,406 (2,554 / 767 / 85) | 3,002 (2,285 / 648 / 69) |
| 2022-23 | 3,256 (2,595 / 609 / 52) | 2,858 (2,317 / 499 / 42) |
| 2023-24 | 3,177 (2,477 / 646 / 54) | 2,748 (2,188 / 524 / 36) |

The generated summary reports the exact retention count for every one of the 300 returned team-seasons at each floor; no raw row is rewritten to produce these exclusions.

## Historical availability and missing history

For each player slot, the builder searches only profile seasons before the target and chooses the closest available one within three seasons. It writes the selected profile season and gap independently for both players. It never uses later information or previous shared-pair experience.

All exposure-eligible rows remain, including `one_missing` and `both_missing` profile histories. The table records slot-level missing flags, a missing-player count, history status, and a strict-complete-history flag for later sensitivity work. Missing player fields remain blank; they are not zero- or globally-imputed.

Any future modeling pipeline must fit an imputer from training-fold player slots only, apply it independently and identically to the two slots, then construct symmetric pair features. It may not impute during curation or create a one-player pseudo-pair mean.

## Feature contract

The materialized CSV preserves raw prior-player slot inputs: per-100 production/count fields, age, games, validated season-total minutes, prior plus-minus (explicitly context-sensitive), team count and a traded-player indicator. It retains count inputs instead of duplicate source percentages. Defined candidates are effective FG%, true shooting, three-point attempt rate, and free-throw rate; a missing/nonpositive denominator returns null.

The later estimator may receive only symmetric transforms: selected per-field pair means and absolute differences, pair trade indicators, pair mean shot distributions, shot-distribution L1 distance, and explicitly defined combined overall shot volume. It may not directly receive Player 1 or Player 2 columns.

Excluded predictors include all IDs/provenance, possessions/minutes/weights, every target-period pair statistic, rank/fantasy/high-score/administrative fields, raw player names, prior-pair experience, and the overlapping source Corner 3 aggregate.

## Shot profiles

Shot profiles use verified `phase3a1.residual-v1` semantics. For every selected profile the table preserves FGM/FGA for restricted area, non-restricted paint, mid-range, left/right corner three, above-the-break three, backcourt, overall, and unclassified residual; source-null and attempted-zone indicators; and classified FGM/FGA coverage.

The source Corner 3 aggregate is used only to validate left plus right and is never double-counted. Primary distribution candidates use overall FGA denominators and preserve unclassified share: restricted area, non-restricted paint, mid-range, combined corner three, above-the-break three, overall three-point location, unclassified, and classified-attempt coverage. The seven mutually exclusive zone shares normalized by classified FGA are a later sensitivity representation. A zero-attempt zone has zero share only when overall FGA is positive, `attempted_zone=false`, and undefined—not 0%—shooting efficiency. Counts remain so later fold-safe smoothing can be specified without choosing a parameter now.

## Weights and sensitivity metadata

Primary modeling weight is equal row weight after the 150-possession floor. Candidate sensitivities are square-root possession weight and possession weight capped at 300. All weight columns remain outside the predictor allowlist; uncapped linear possession weighting is not a candidate.

The outputs retain target season, team and canonical player IDs, pair possessions/minutes, endpoint exact-250 flags, 2019-20/2020-21 pandemic flags, source seasons/gaps, policy flags, candidate weights, and raw-source path/hash provenance. The four exact-250 team-seasons remain flags, not automatic exclusions.

## Reproduction

From `research/pair-fit-v2`, with the repository virtual environment active:

```powershell
$env:PYTHONPATH = 'src'
python -m pair_fit_v2.phase3b_cli --cache-root cache --output-dir curated/phase3b
```

The output directory contains `phase3b_poss_ge_100.csv`, `phase3b_poss_ge_150.csv`, `phase3b_feature_manifest.json`, and `phase3b_curation_summary.json`. The summary contains exact per-season and all team-season retention, history coverage, prerequisite anchors, field counts, and every deterministic artifact hash. The CSVs are deliberately Git-ignored because they are reproducible and materially large.

## Still undecided

No imputation method, efficiency smoothing parameter, scaling scheme, estimator, hyperparameters, target-driven feature screening, predictive evaluation, or shot/no-shot ablation has been selected or executed. Chronological fold design and protected-season evaluation remain future work.

## Correction pass: estimator and manifest contract

The corrected primary estimator allowlist has 52 features, down from 60. Removed exact redundancies or reliability-only candidates are: `pair_mean.GP`, `pair_absolute_difference.GP`, `pair_mean.TOTAL_MIN`, `pair_absolute_difference.TOTAL_MIN`, `pair_combined_overall_fga`, `pair_any_traded_history`, mean overall three-point-location share, and mean classified-attempt coverage. Player-slot GP, season-total minutes, and overall FGA remain preserved reliability/audit data. The remaining basketball statistics can be correlated or linearly related in places; no additional candidate was removed solely for correlation in this pass.

`traded_player_indicator` is 0 only when `TEAM_COUNT == 1`, 1 only when `TEAM_COUNT > 1`, and null for missing, nonnumeric, nonintegral, zero, or negative TEAM_COUNT. `pair_traded_history_count` is the sum of the two indicators only when both are known, with range 0--2; otherwise it is null.

`pair_shot_distribution_l1_distance_overall_fga` is the sum of absolute differences between the two players' overall-FGA-denominator shares for restricted area, non-restricted paint, mid-range, combined left-plus-right corner three, above-the-break three, backcourt, and unclassified residual. Its range is 0--2: zero means identical distributions and larger values mean more different distributions. It is null if either profile is missing, either overall FGA is missing/nonpositive, or any required component is missing. It excludes aggregate three-point-location share, classified coverage, source Corner 3, and classified-FGA-normalized sensitivity shares.

The manifest now has a disjoint authoritative category partition: identifiers, target, eligibility/exposure, reliability metadata, weights, player attributes/production, shot semantics, missingness, sensitivity metadata, provenance, and estimator predictors. The threshold flags occur only in eligibility/exposure; source-null indicators occur only in shot semantics. Validation rejects unknown fields, duplicate category assignment, and predictor overlap with identifiers, targets, reliability, eligibility/exposure, weights, or prohibited fields.
