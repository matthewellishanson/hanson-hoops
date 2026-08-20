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

The cache-audit schema fingerprint is separate from row volume. It consists of the result-set name, ordered column list, and column count. Row count is data volume, not schema identity.

Phase 1B makes the previously fixed request context explicit. The full observation key is (`league_id`, `target_season`, `season_type`, `team_id`, canonical `player_1_id`, canonical `player_2_id`). Raw `GROUP_ID`, player names and row order are audit data, not join identity.

## Phase 1B ingestion architecture contract

The approved design direction is immutable raw JSON → row-preserving curated Parquet → reproducible DuckDB views. This is an architecture contract only; Phase 1B does not materialize Parquet or DuckDB.

- Raw assets are identified by endpoint plus every normalized request parameter and tracked in a versioned resumable manifest. The release gate recomputes the normalized manifest ID, verifies each asset ID against its embedded identity, and independently verifies every embedded identity against the manifest's approved team/measure request.
- Every acquisition event, cache serialization, schema fingerprint and downstream output has separate provenance.
- Required `Overall` and `Lineups` fingerprints must be nonempty, unique, internally valid and recomputed as identical to the approved measure-specific schema contract. A stored `accepted` label is not sufficient; every non-identical schema fingerprint is quarantined for explicit review and no drift is silently coerced.
- Base and Advanced use a full outer reconciliation on the full observation key so unmatched rows remain auditable.
- The all-rows curated table retains target-ineligible and incomplete-history observations with explicit reasons/statuses.
- DuckDB is a rebuildable catalog over Parquet, not the sole durable copy.
- Prior-player features enter through a versioned, strict-pre-target-season source registry that can later add heliocentrism sources without changing pair identity.

The complete design and 30-team release gates are in `PHASE1B_ARCHITECTURE.md`.

`group_quantity` is part of raw request identity and is fixed at `2` for the strictly two-player `pair_observations` grain, preventing collisions with trio, quartet or five-player assets. Future higher-order work requires a new versioned group-observation contract with `group_size` and an ordered canonical player-ID collection. Aggregating pair-model predictions across a larger selection is a possible future interface behavior, but it is not equivalent to directly training a lineup model; neither path is implemented in this pass.

## Target definition

The observed 2024-25 TeamDashLineups Advanced response directly provides team offensive rating (`OFF_RATING`) and defensive rating (`DEF_RATING`) while both players share the court.

The provisional primary rate target is `NET_RATING`, with the expected relationship:

- `NET_RATING` = `OFF_RATING` - `DEF_RATING`, subject to displayed rounding

This target-availability relationship was observed across all four Phase 1A pilot teams; it is not evidence of predictive validity. The Base-measure `PLUS_MINUS` field is a cumulative on-court team point differential; it is neither net rating nor an on/off statistic and is not substituted for the rate target.

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

Minutes and possessions are treated as reliability and sample-size information, not as player-quality features. Base `MIN` is the shared-minute exposure field because it preserves fractional precision; Advanced `POSS` is possession exposure. Advanced `MIN` is retained as returned but is not assumed interchangeable with Base `MIN` at sparse exposure.

Rows with missing `POSS` or `POSS <= 0` are retained unchanged for audit but are ineligible for a possession-based rate target, even if the endpoint returns numeric offensive, defensive, or net ratings. Phase 1A does not select a positive minimum-minute or minimum-possession threshold.

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
- pair rows without eligible possession exposure (`POSS` missing or `POSS <= 0`) from possession-based rate-target training, while retaining the rows and endpoint values for audit
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

Validation must be time-ordered or rolling-origin, with 2025-26 preserved as the untouched final test season. A random pair-row split is explicitly rejected because overlapping players and pairs violate row independence and could cross split boundaries.

This document does not claim that the final model is valid or that interaction effects are predictable. The purpose of Phase 0 is feasibility and data-contract validation only.

The current research status is: Phase 1A bounded multi-team pilot complete; Phase 1B architecture and ingestion-contract design complete; Phase 1C raw-season acquisition complete at 60/60 verified assets; Phase 1D endpoint omission proven for Charlotte; and Phase 1E bounded Charlotte recovery feasibility complete. Across all 30 teams, 5,297 Base/Advanced returned pairs match one-to-one with no unmatched or duplicate full observation keys; the complete-season manifest and clean raw-release gates pass. Phase 1E's two-window Charlotte union contains all 250 full-season keys plus seven recovered-only keys, and supported additive Base totals plus Advanced `POSS` reproduce the immutable full-season values for all 250 comparable pairs. This demonstrates a larger observed window-union population, not global exhaustiveness. Possession-weighted `OFF_RATING` met the `0.2` audit bound, but `DEF_RATING` and `NET_RATING` did not do so for every row; target recomposition is therefore unresolved, no recovered-only target values are approved, and Philadelphia was not requested after the Charlotte gate failed. No positive exposure threshold was selected. Multi-season and predictive feasibility remain unverified, and historical expansion/model training remain prohibited pending a defensible target-reconstruction decision plus the approved exposure, missing-history, and validation gates.

## Prior-player join audit (Phase 0F)

One live 2023-24 `LeagueDashPlayerStats` response (Base measure, Per100Possessions) was acquired and joined to the 183 Warriors 2024-25 canonical pairs by stable `PLAYER_ID`, independently for each player in the pair.

- Stable-ID audit: 572 raw rows, 572 unique `PLAYER_ID` values, 0 duplicate IDs, 0 missing/malformed IDs. The endpoint appears to return one aggregate row per player, including 78 players with `TEAM_COUNT > 1` (traded during the season). One traded player (Buddy Hield) shows `GP=84`; this is a valid combined-team total (a mid-season trade can push combined games above 82 because the two teams may have played a different number of games at the trade date), not an anomaly, and it is not capped or corrected.
- Player-level coverage: 19 of 23 unique Warriors pair-population player IDs (82.6%) have a 2023-24 record. 4 do not: they are described only as having "no 2023-24 LeagueDashPlayerStats record," not labeled rookies or errors without further evidence.
- Pair-level coverage: 143 of 183 pairs (78.1%) have both players matched; 29 have only player 1, 8 have only player 2, 3 have neither.
- Exposure-weighted diagnostic coverage under the Phase 1A convention: complete-prior pairs sum to 36,469.44 of 39,460.00 Base shared minutes (92.4%) and 77,640 of 84,005 Advanced possessions (92.4%); incomplete-prior pairs hold the remaining 2,990.56 Base minutes and 6,365 Advanced possessions. These are overlapping diagnostic sums recalculated from the cached pair tables, not unique team totals, and are not used as model features.
- Observed `MIN` semantics under `Per100Possessions`: it is not season-total minutes; it is minutes reported on the same per-100-possession normalization as other rate fields, and happened to resemble typical per-game averages for this season's pace. It must not be used as the prior player's season-total eligibility or reliability measure. A later ingestion phase will need a validated `Totals`-per-mode response, or another trustworthy season-total-minutes field. Phase 0F establishes join coverage, not the final prior-player reliability contract.

Missing-history policy: the uniform Phase 1 baseline policy below was exercised across the four-team pilot and remains subject to approval before modeling.

This audit does not establish multi-team coverage, does not select a final feature set, and does not train or validate a model.

## Uniform missing-history policy (Phase 1 baseline)

This baseline policy was applied unchanged in the Phase 1A multi-team pilot (see `PHASE1A_PILOT_REPORT.md`); it is still not a final modeling decision:

1. Preserve all pair observations in raw and curated datasets; no pair rows are dropped from storage.
2. Add a categorical prior-history status per pair: `complete`, `one_missing`, or `both_missing`.
3. Use `complete`-status pairs for the primary baseline model.
4. Do not zero-impute missing prior NBA statistics.
5. Retain `one_missing`/`both_missing` pairs for coverage analysis and later evaluation of one universal no-history fallback.
6. The no-history fallback model is not yet defined or implemented.

Phase 1A confirmed this policy's mechanics work across four teams. The same statuses and complete-history primary baseline apply to every team; no roster-specific policy is introduced. The `complete` share varies from 57.2% to 81.6% across the pilot teams, but the bounded sample does not establish roster type as the cause or a league-wide relationship. All rows remain available for later evaluation of a universal fallback (see `PHASE1A_PILOT_REPORT.md`).

## Phase 0 requirement

Phase 0 does not validate the model or the predictability of interaction effects.

It only determines whether the research pipeline is feasible enough to scale into a multi-season sample with acceptable data quality, reasonable coverage, and a clean target/feature contract.
