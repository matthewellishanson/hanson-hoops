# Pair-fit v2 provisional model contract

## Scope

This document is a provisional research contract for the Hanson Hoops Phase 0 pair-fit v2 experiment. It is not a claim that the final model has been selected, nor that interaction effects are validated.

The purpose of this work is to test whether a reproducible shared-court pair-season dataset can be built at a scale and with enough reliability to support a future supervised projection exercise.

## Observation unit

The observation unit is one unordered player-pair/team/season observation, stored using canonical player IDs so A+B and B+A cannot become separate records.

Canonical pair identity should satisfy:

- player IDs are stored as stable integers or canonical strings
- the pair key is sorted or otherwise normalized before record creation
- duplicate pair rows are rejected or flagged explicitly during validation
- the pair identity is independent of player ordering in the source data

## Target definition

The observed 2024-25 TeamDashLineups Advanced response directly provides team offensive rating (`OFF_RATING`) and defensive rating (`DEF_RATING`) while both players share the court.

The provisional primary rate target is `NET_RATING`, with the expected relationship:

- `NET_RATING` = `OFF_RATING` - `DEF_RATING`, subject to displayed rounding

This is a one-team target-availability finding, not evidence of predictive validity. The Base-measure `PLUS_MINUS` field is a cumulative on-court team point differential; it is neither net rating nor an on/off statistic and is not substituted for the rate target.

The central research question is whether a supervised projection can estimate expected shared-court team performance for a selected pair, given prior-period player capability and standardized context.

## Additive vs interaction component

The model contract distinguishes between:

- additive component: expected shared-court performance implied by prior independent player capability and standardized context
- interaction component: projected departure from that additive expectation once both players are present together

The interaction term is not presumed valid in Phase 0. It is a future modeling concept that will only be treated as validated if it improves held-out prediction over a documented baseline.

## Intended interpretation

The intended final interpretation is expected team production and efficiency with the selected pair sharing the floor, assuming approximately league-average remaining teammates and opponents.

This is a team-efficiency projection, not a claim that a particular lineup is the entire game-state model.

## Prediction timing

Prediction timing is strictly pre-target-season or pre-cutoff information only.

The target-season pair performance is predicted using information available before the target season or the prediction cutoff. This excludes same-season player statistics from being treated as prior features.

## Reliability and sample-size fields

Minutes and possessions are treated as reliability and sample-size information, not as player-quality features.

Usage is treated as an offensive-role and possession-ending-burden feature, not as inherent player quality or a reliability metric.

These variables are used for:

- eligibility filtering
- reliability weighting
- sample-size analysis
- uncertainty checks

They are not treated as intrinsic quality scores.

## Initial exclusions and deferred questions

Phase 0 should initially exclude or explicitly flag:

- rookies, unless justified by a special exception
- same-season target features used as prior features
- unverified possession estimates
- pair rows with zero or unusable shared minutes
- malformed or duplicate pair identifiers
- rows without stable ID resolution

Open questions that remain provisional include:

- whether usage should be included as a feature in the eventual model
- how prior-season player histories should be aggregated across trades and team changes
- how to handle incomplete or sparse shared-court samples
- how to treat pair rows with limited minutes or possessions
- whether pair-level team context should be standardized at team or league level

## Historical split for future work

The intended future historical split is:

- training targets: 2021–22 through 2023–24
- validation target: 2024–25
- untouched test target: 2025–26
- prior player data beginning in 2020–21

This document does not claim that the final model is valid or that interaction effects are predictable. The purpose of Phase 0 is feasibility and data-contract validation only.

The current research status is: live one-team Base and Advanced pair acquisition, plus the canonical Base-to-Advanced join, are verified. Phase 0F acquired one live 2023-24 LeagueDashPlayerStats response and quantified prior-player join feasibility for the 183 Warriors 2024-25 pairs: player-level coverage 19/23 (82.6%), pair-level complete-prior coverage 143/183 (78.1%). A provisional missing-history baseline policy has been adopted (see below). Multi-team historical consistency and predictive feasibility remain unverified.

## Prior-player join audit (Phase 0F)

One live 2023-24 `LeagueDashPlayerStats` response (Base measure, Per100Possessions) was acquired and joined to the 183 Warriors 2024-25 canonical pairs by stable `PLAYER_ID`, independently for each player in the pair.

- Stable-ID audit: 572 raw rows, 572 unique `PLAYER_ID` values, 0 duplicate IDs, 0 missing/malformed IDs. The endpoint appears to return one aggregate row per player, including 78 players with `TEAM_COUNT > 1` (traded during the season). One traded player (Buddy Hield) shows `GP=84`; this is a valid combined-team total (a mid-season trade can push combined games above 82 because the two teams may have played a different number of games at the trade date), not an anomaly, and it is not capped or corrected.
- Player-level coverage: 19 of 23 unique Warriors pair-population player IDs (82.6%) have a 2023-24 record. 4 do not: they are described only as having "no 2023-24 LeagueDashPlayerStats record," not labeled rookies or errors without further evidence.
- Pair-level coverage: 143 of 183 pairs (78.1%) have both players matched; 29 have only player 1, 8 have only player 2, 3 have neither.
- Exposure-weighted diagnostic coverage: complete-prior pairs sum to 36,469.0 of 39,458.0 shared minutes (92.4%) and 77,640 of 84,005 possessions (92.4%); incomplete-prior pairs hold the remaining 2,989.0 minutes and 6,365 possessions (7.6% each). These are overlapping diagnostic sums recalculated from the cached pair table, not unique team totals, and are not used as model features.
- Observed `MIN` semantics under `Per100Possessions`: it is not season-total minutes; it is minutes reported on the same per-100-possession normalization as other rate fields, and happened to resemble typical per-game averages for this season's pace. It must not be used as the prior player's season-total eligibility or reliability measure. A later ingestion phase will need a validated `Totals`-per-mode response, or another trustworthy season-total-minutes field. Phase 0F establishes join coverage, not the final prior-player reliability contract.

Missing-history policy: a provisional Phase 1 baseline policy has been adopted (see below), subject to reevaluation after the multi-team pilot.

This audit does not establish multi-team coverage, does not select a final feature set, and does not train or validate a model.

## Provisional missing-history policy (Phase 1 baseline, subject to reevaluation)

This is a provisional baseline policy for the upcoming Phase 1A multi-team pilot, not a final modeling decision:

1. Preserve all pair observations in raw and curated datasets; no pair rows are dropped from storage.
2. Add a categorical prior-history status per pair: `complete`, `one_missing`, or `both_missing`.
3. Use `complete`-status pairs for the primary baseline model.
4. Do not zero-impute missing prior NBA statistics.
5. Retain `one_missing`/`both_missing` pairs for coverage analysis and a possible later no-history fallback.
6. The no-history fallback model is not yet defined or implemented.

This policy is subject to reevaluation after the Phase 1A multi-team pilot confirms whether coverage patterns generalize beyond the Warriors.

## Phase 0 requirement

Phase 0 does not validate the model or the predictability of interaction effects.

It only determines whether the research pipeline is feasible enough to scale into a multi-season sample with acceptable data quality, reasonable coverage, and a clean target/feature contract.
