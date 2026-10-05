# Pair Fit v2 product contract

Version: `pair-fit-v2.0.0`

## Product meaning

Pair Fit v2 outputs **projected shared-court team NET_RATING**: a contextual estimate of the team's points-per-100-possessions margin while the two selected player versions share the court.

It is not a causal chemistry measurement, inherent player-quality grade, 0–100 compatibility score, probability, projected win total, or guarantee that two players would reproduce the estimate together.

## Pair and season contract

- A pair is unordered. Swapping Player A and Player B must leave the feature vector, full-precision prediction, displayed prediction, confidence label, and support status unchanged.
- The same player ID cannot occupy both positions.
- Both cards must use one common target season. Cross-season and cross-era Pair Fit projections are unsupported, even though ordinary comparison cards may still display those players.
- The supported target seasons are `2014-15` through `2026-27`. The permitted profile seasons are `2013-14` through `2025-26`.
- Each player uses the nearest available profile strictly before the target season, with a maximum three-season lookback. A `2026-27` card therefore checks `2025-26`, then `2024-25`, then `2023-24`.
- Seasons before `2014-15` and after `2026-27` return a truthful structured refusal. Do not extrapolate to `2027-28` until authenticated `2026-27` individual profiles exist.

## Missing history and confidence

Missingness is recorded before frozen imputation. If both histories are found, confidence is `standard`; if either or both are missing, it is `lower`. This label describes history completeness, not a calibrated probability of correctness. No numerical confidence percentage is permitted.

## Display and error disclosure

The inference interface may return the full-precision prediction. The initial headline rounds to the nearest whole NET_RATING point, using half-away-from-zero rounding, and retains an explicit plus sign for positive values.

Public copy must say: **Typical final-test error: approximately 7.8 points per 100 possessions.** This is an observed mean absolute error, not a calibrated plus/minus interval.

## Interpretation and limitations

The target is contextual team performance. Teammates, opponents, coaching, roles, injuries, and lineup context are not fully captured. The final model explains only a modest share of observed variation, and Ridge regularization compresses predictions toward average. The estimate should supplement, not replace, basketball judgment.

## Removed legacy concepts

Pair Fit v2 does not expose emphasis sliders, primary-handler selection, ordered pair positions, a 0–100 fit score, numerical confidence, causal “top drivers,” unvalidated risk flags, or legacy style-axis results presented as model explanations.

## Frozen model and population

The deployable estimator is `sklearn.linear_model.Ridge(alpha=3000.0)` with equal row weights, the exact ordered 45-feature no-shot symmetric manifest, no calibrator, no ensemble, no alternate estimator, and no tuning. It was fit once per deterministic package build on 32,512 direct eligible observations: 29,701 rows from `2014-15` through `2024-25` plus 2,811 rows from `2025-26`.

The population retains the frozen exclusions: Charlotte and Philadelphia in `2024-25`, and Indiana and Memphis in `2025-26`. It contains 32,512 unique canonical observation keys, only direct full-season targets, only eligible `POSS >= 150` rows, no recovered-window rows, no reconstructed targets, and no prediction-derived training features.

Production preprocessing is learned only from those 32,512 rows: unique player-season profiles, same medians for both slots, symmetric feature construction and fill, population-variance scaling, then exactly one scaling application and one Ridge fit.

## Package publication safety

The deterministic package builder may publish only to an absent destination or an existing completely empty directory. It preflights the entire destination before loading fit inputs, fitting, or serializing. Any populated state—complete, partial, matching, conflicting, extra, hidden, temporary, or nested—is a strict restart refusal and must leave every destination byte and timestamp unchanged.
