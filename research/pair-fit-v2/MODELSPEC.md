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

The primary target is team offensive rating (ORtg) and defensive rating (DRtg) while both players share the court.

Derived target:

- net rating = ORtg - DRtg

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

The current research status is: currently blocked. The synthetic scaffold is valid, but the live pair-season feasibility check is blocked by upstream NBA stats access timeouts during the bounded live request attempt.

## Phase 0 requirement

Phase 0 does not validate the model or the predictability of interaction effects.

It only determines whether the research pipeline is feasible enough to scale into a multi-season sample with acceptable data quality, reasonable coverage, and a clean target/feature contract.
