# Pair Fit v2 model card

Model version: `pair-fit-v2.0.0`

## Intended use

Pair Fit v2 estimates the shared-court team NET_RATING for two player versions in the same supported target season. It is a roster-conversation aid and should supplement basketball judgment.

The result is contextual team performance, measured as points per 100 possessions above or below opponents while the pair shares the court. It is not causal chemistry, a player grade, a probability, a win projection, or a guarantee.

## Evidence and model

The final equal-weight training population contains 32,512 direct `POSS >= 150` pair/team/season rows from `2014-15` through `2025-26`. Charlotte and Philadelphia are excluded in `2024-25`; Indiana and Memphis are excluded in `2025-26`. Predictors are 45 symmetric no-shot features built only from strict-prior player profiles.

The estimator is Ridge with `alpha=3000.0`. The frozen `2025-26` final test produced MAE `7.7892`, RMSE `9.9490`, R² `0.1004`, bias `0.3602`, and Spearman `0.3364`, clearing the predeclared baseline-relative gates. Public disclosure: **Typical final-test error: approximately 7.8 points per 100 possessions.** This is not a calibrated interval.

## Support

- Supported target seasons: `2014-15` through `2026-27`.
- Available source profiles: `2013-14` through `2025-26`.
- Both cards must use one common target season and different player IDs.
- The nearest profile strictly before the target is used, up to three seasons back.
- Cross-season, cross-era, pre-`2014-15`, and post-`2026-27` projections are unsupported.

When both histories are found, confidence is `standard`; otherwise it is `lower`. Confidence reports history completeness only and is never numerical.

## Limitations

Teammates, opponents, coaching, roles, injuries, and lineup context are not fully represented. The final R² shows that most observed variation remains unexplained. Ridge regularization intentionally compresses estimates toward average, so unusually strong or weak outcomes tend to be moderated. Associations are predictive, not causal.

## Updates

Annual expansion requires authenticated new full-season pair evidence and the immediately prior individual-profile season, replay of the frozen eligibility/provenance contracts, relearning all preprocessing on the expanded eligible population, one unchanged Ridge fit, transparent reserialization, parity checks, and a separately authorized evaluation plan. `2027-28` must remain unsupported until `2026-27` player profiles are acquired and authenticated.

