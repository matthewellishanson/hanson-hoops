# Phase 1F target semantics and preliminary reliability audit

## Primary classification

**`direct full-season target semantics supported; reliability threshold unresolved`**

The directly returned full-season standard ratings have coherent, sufficiently documented semantics for an observed pair-lineup outcome. A pair-row rating describes the team's performance while both named players share the court; it includes the other three teammates, opponents, and game context. It is not either player's individual rating, is not limited to the pair's personal box-score production, and is not an on/off differential.

The failure to reconstruct some full-season `DEF_RATING` and `NET_RATING` values from two windows does not invalidate those directly returned full-season fields. It instead shows that the available window response does not expose every denominator or precision component needed for safe reconstruction. Charlotte supplies useful preliminary exposure evidence, but not enough independent contexts or high-exposure pairs to select a final reliability threshold.

No live request, Philadelphia request, other-season access, historical ingestion, materialization, target/threshold/feature selection, validation split, or modeling occurred.

## Starting state and immutable replay gate

- Starting/final branch: `research/pair-fit-v2`
- Starting HEAD: `e6ca6c15dc28606ad8155a131801929fccf69f7a`
- Latest commit: `Add comprehensive tests for phase1e recovery process`
- Initial working tree: clean
- Phase 1C manifest SHA-256: `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c`
- Phase 1D ledger SHA-256: `f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9`
- Phase 1E ledger SHA-256: `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde`

The Phase 1C manifest gate, all 60 asset identities/hashes/schemas, Phase 1D ledger and diagnostic payload, and all four verified Phase 1E Charlotte window assets replayed without transport. Before/after hashes were identical.

Exact reproduced evidence:

- Phase 1C: 60/60 verified; 5,297 Base rows; 5,297 Advanced rows; 5,297 matches; no unmatched rows; 8 zero-possession target-ineligible rows.
- Phase 1D: Charlotte `proven_non_exhaustive`; three shorter-window-only proving pairs.
- Phase 1E: early 163 Base/163 Advanced; late 177/177; 257 union keys; 250/250 full-season keys recovered; seven recovered-only pairs totaling 23 possessions; none at `POSS >= 10`; all supported additive totals exact; all 250 `OFF_RATING` recompositions within `0.1`; nine `DEF_RATING` and ten `NET_RATING` errors over `0.2`.

## Evidence sources and cache-only access boundary

| Source | URL or local source | Review/access record |
|---|---|---|
| NBA Stats glossary | `https://www.nba.com/stats/help/glossary` | Authoritative locator recorded 2026-08-25; not fetched in Phase 1F because zero network calls were permitted. Definitions below are paraphrased, not quoted. |
| NBA Stats Lineups Advanced | `https://www.nba.com/stats/lineups/advanced?Season=2024-25&SeasonType=Regular%20Season` | Official interface previously accessed during Phase 1E on 2026-08-19; not re-fetched in Phase 1F. |
| NBA Stats response endpoint | `https://stats.nba.com/stats/teamdashlineups` | Only immutable cached 2024-25 responses were read in Phase 1F. |
| Installed `nba_api` endpoint source | `nba_api.stats.endpoints.teamdashlineups`, package 1.10.1; upstream `https://github.com/swar/nba_api` | Local source inspected 2026-08-25 for schema names only, not undocumented semantics. |

The official glossary reference and user-approved semantic contract support the standard definitions. The installed endpoint source and cached response schemas establish that the fields are directly returned. The exact algorithms behind the `E_` estimated variants were not available in the local authoritative evidence, so no formula is asserted.

## Rating semantics

- `POSS`: returned team-possession exposure for the lineup row. It is cumulative, not a player-quality feature.
- `OFF_RATING`: team points scored per 100 team possessions while both players share the court.
- `DEF_RATING`: opponent points scored per 100 opponent possessions during those shared minutes.
- `NET_RATING`: `OFF_RATING - DEF_RATING`, subject to published one-decimal rounding.
- `E_OFF_RATING`, `E_DEF_RATING`, `E_NET_RATING`: directly returned NBA estimated variants. “Estimated” is an NBA field label, not a prediction from this project. Their exact methodology is not documented by the evidence available to this cache-only phase.
- Base `PLUS_MINUS`: cumulative team points minus opponent points while the pair shares the court. It is neither a rate nor on/off differential.

Direct validity, window recomposability, and low-exposure reliability are distinct. A directly returned field can be internally coherent while not reconstructable from rounded windows, and a coherent target can still be too noisy at low possessions.

## Direct full-season coherence and availability

All six fields are numeric in Charlotte full season (250/250), early window (163/163), late window (177/177), and all Phase 1C teams (5,297/5,297). There is no missing or nonnumeric estimated-rating value.

| Identity | Comparable | MAE | Median AE | Max AE | Within 0.1 | Over 0.2 |
|---|---:|---:|---:|---:|---:|---:|
| `NET_RATING - (OFF_RATING - DEF_RATING)` | 5,297 | 0.021899 | 0 | 0.100000 | 100% | 0 |
| `E_NET_RATING - (E_OFF_RATING - E_DEF_RATING)` | 5,297 | 0.024429 | 0 | 0.100000 | 100% | 0 |

Thus directly returned full-season standard `NET_RATING` is internally coherent with its two components throughout the cached league. This supports its validity as the endpoint's observed full-season pair outcome, subject to endpoint population selection and exposure reliability. It does not prove predictive usefulness.

## Standard-rating recomposition diagnosis

The audit emits a deterministic per-pair ledger for all 250 Charlotte full-season keys with early/late/total possessions, both window rates, possession-weighted result, direct full-season rate, and signed/absolute error. Summary:

| Field | Comparable | MAE | Median AE | Max AE | Within 0.1 | Within 0.2 | Within 0.5 | Over 0.2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `OFF_RATING` | 250 | 0.009408 | 0 | 0.078351 | 100.0% | 100.0% | 100.0% | 0 |
| `DEF_RATING` | 250 | 0.025377 | 0 | 0.710112 | 92.8% | 96.4% | 99.6% | 9 |
| `NET_RATING` | 250 | 0.027691 | 0 | 0.694382 | 91.6% | 96.0% | 99.6% | 10 |

### Denominator test

- `100 * Base PTS / Advanced POSS` matches full-season `OFF_RATING` for 250/250 rows within `0.1` (MAE `0.023085`; max `0.049275`). Returned `POSS` therefore behaves as the offensive denominator.
- Opponent points are arithmetically derivable as `Base PTS - Base PLUS_MINUS`.
- `100 * opponent points / returned POSS` does not reproduce `DEF_RATING`: MAE `2.379619`, median AE `1.558796`, max AE `26.7`, and only 35/250 within `0.2`.
- The Advanced schema exposes only `POSS`; it has no separately named opponent-possession field.

This is consistent with the documented denominator distinction: offense uses team possessions, while defense uses opponent possessions. Weighting defense by returned team `POSS` is therefore not established as valid, and directly weighting net by team `POSS` inherits that problem. The cached fields strongly support this explanation, but do not prove the exact internal NBA computation because opponent possessions and full precision are absent.

### Published-rounding interval test

A displayed one-decimal rate was treated as the closed interval `value ± 0.05`. Each window interval was possession-weighted and compared with the full-season interval. No discrepancy was dismissed merely because it was small.

- `OFF_RATING`: no error exceeds `0.2`; all observed differences are compatible with published one-decimal intervals.
- `DEF_RATING`: all nine errors over `0.2` have non-overlapping team-`POSS`-weighted intervals, but are classified `indeterminate_due_to_missing_denominator_or_precision` because team `POSS` is not the documented defensive denominator.
- `NET_RATING`: all ten errors over `0.2` receive the same indeterminate classification because direct team-`POSS` weighting is not established for a difference of rates with different denominators.
- Zero standard discrepancies are affirmatively classified as rounding-only merely on size.

### Complete standard discrepancy ledger (`absolute error > 0.2`)

| Field | Pair IDs | Pair | Early/Late POSS | Recomposed | Full | Error | Classification |
|---|---|---|---:|---:|---:|---:|---|
| DEF | `201959`,`1629006` | T. Gibson—J. Okogie | 23/19 | 131.409524 | 131.7 | -0.290476 | indeterminate denominator/precision |
| DEF | `201959`,`1631217` | T. Gibson—M. Diabaté | 3/86 | 118.510112 | 117.8 | +0.710112 | indeterminate denominator/precision |
| DEF | `203995`,`1642354` | V. Micić—K. Simpson | 60/8 | 115.547059 | 115.9 | -0.352941 | indeterminate denominator/precision |
| DEF | `1629006`,`1629610` | J. Okogie—D. Jeffries | 67/120 | 109.619786 | 109.3 | +0.319786 | indeterminate denominator/precision |
| DEF | `1629006`,`1641733` | J. Okogie—N. Smith Jr. | 111/83 | 103.815979 | 103.6 | +0.215979 | indeterminate denominator/precision |
| DEF | `1629610`,`1631209` | D. Jeffries—I. Wong | 166/104 | 98.425185 | 98.2 | +0.225185 | indeterminate denominator/precision |
| DEF | `1631109`,`1631217` | M. Williams—M. Diabaté | 6/106 | 131.923214 | 132.2 | -0.276786 | indeterminate denominator/precision |
| DEF | `1631209`,`1641733` | I. Wong—N. Smith Jr. | 58/32 | 92.902222 | 92.6 | +0.302222 | indeterminate denominator/precision |
| DEF | `1631209`,`1642275` | I. Wong—T. Salaün | 187/54 | 106.419502 | 106.7 | -0.280498 | indeterminate denominator/precision |
| NET | `201959`,`1629006` | T. Gibson—J. Okogie | 23/19 | -17.128571 | -17.4 | +0.271429 | indeterminate denominator/precision |
| NET | `201959`,`1631217` | T. Gibson—M. Diabaté | 3/86 | -12.894382 | -12.2 | -0.694382 | indeterminate denominator/precision |
| NET | `203995`,`1642354` | V. Micić—K. Simpson | 60/8 | -42.017647 | -42.4 | +0.382353 | indeterminate denominator/precision |
| NET | `1629006`,`1629610` | J. Okogie—D. Jeffries | 67/120 | -9.070053 | -8.8 | -0.270053 | indeterminate denominator/precision |
| NET | `1629610`,`1631209` | D. Jeffries—I. Wong | 166/104 | 0.835556 | 1.1 | -0.264444 | indeterminate denominator/precision |
| NET | `1631109`,`1631217` | M. Williams—M. Diabaté | 6/106 | -23.921429 | -24.2 | +0.278571 | indeterminate denominator/precision |
| NET | `1631109`,`1642275` | M. Williams—T. Salaün | 135/228 | -12.392562 | -12.6 | +0.207438 | indeterminate denominator/precision |
| NET | `1631209`,`1641733` | I. Wong—N. Smith Jr. | 58/32 | 14.831111 | 15.1 | -0.268889 | indeterminate denominator/precision |
| NET | `1631209`,`1642275` | I. Wong—T. Salaün | 187/54 | -17.222407 | -17.5 | +0.277593 | indeterminate denominator/precision |
| NET | `1642275`,`1642354` | T. Salaün—K. Simpson | 151/488 | -12.364319 | -12.6 | +0.235681 | indeterminate denominator/precision |

Errors are not confined to low total possessions: one net discrepancy occurs at 639 total possessions. They are more concentrated where one window is sparse: four of nine defensive and four of ten net discrepancies have a minimum window below 25 possessions. This supports denominator/precision caution rather than a claim that simple sparsity alone causes every recomposition error.

| Total POSS band | OFF MAE / >0.2 | DEF MAE / >0.2 | NET MAE / >0.2 |
|---|---:|---:|---:|
| 0–9 | 0 / 0 | 0 / 0 | 0 / 0 |
| 10–24 | 0 / 0 | 0 / 0 | 0 / 0 |
| 25–49 | .002019 / 0 | .012593 / 1 | .012045 / 1 |
| 50–99 | .004978 / 0 | .041402 / 3 | .041451 / 3 |
| 100–199 | .005097 / 0 | .030046 / 3 | .027618 / 2 |
| 200–499 | .010933 / 0 | .020668 / 2 | .025552 / 3 |
| 500–999 | .017772 / 0 | .031032 / 0 | .041088 / 1 |
| 1000+ | .027957 / 0 | .022840 / 0 | .017929 / 0 |

| Minimum-window POSS band | OFF MAE / >0.2 | DEF MAE / >0.2 | NET MAE / >0.2 |
|---|---:|---:|---:|
| 0–4 | .000305 / 0 | .004403 / 1 | .004561 / 1 |
| 5–9 | .022304 / 0 | .240861 / 2 | .239356 / 2 |
| 10–24 | .033988 / 0 | .082010 / 1 | .098236 / 1 |
| 25–49 | .028737 / 0 | .089250 / 1 | .092814 / 1 |
| 50–99 | .033106 / 0 | .091798 / 3 | .086374 / 2 |
| 100–199 | .026700 / 0 | .056232 / 1 | .068715 / 3 |
| 200–299 | .023302 / 0 | .054178 / 0 | .084315 / 0 |
| 300+ | .028912 / 0 | .024522 / 0 | .026768 / 0 |

## Estimated-rating audit

The estimated fields are directly and completely available, and estimated net is internally coherent with estimated offense minus defense. Their precise estimation methodology and denominators remain undocumented in the locally available evidence, so direct numeric availability is not equivalent to sufficiently documented target semantics.

| Field | Comparable | MAE | Median AE | Max AE | Within 0.1 | Within 0.2 | Within 0.5 | >0.2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `E_OFF_RATING` | 250 | .052616 | 0 | 3.911765 | 93.6% | 96.4% | 98.4% | 9 |
| `E_DEF_RATING` | 250 | .030307 | 0 | .461905 | 88.8% | 96.4% | 100.0% | 9 |
| `E_NET_RATING` | 250 | .072606 | 0 | 3.900000 | 84.4% | 92.4% | 96.8% | 19 |

Possession-weighting does not empirically recompose the estimated variants, including estimated offense. Every estimated error over `0.2` is `indeterminate_due_to_missing_denominator_or_precision`; the exact formula is unavailable, so Phase 1F does not substitute a guessed one. Largest discrepancies occur for LaMelo Ball—KJ Simpson (`E_OFF_RATING` +3.911765; `E_NET_RATING` +3.9) and Taj Gibson—Moussa Diabaté (`E_OFF_RATING` -2.476404; `E_NET_RATING` -2.153933).

Classification by field:

- All three: directly available but exact formula undocumented.
- `E_OFF_RATING`: not empirically recomposable with returned `POSS`; still a viable future candidate, not suitable for current target selection.
- `E_DEF_RATING`: not empirically recomposable with returned `POSS`; still a viable future candidate, not suitable for current target selection.
- `E_NET_RATING`: direct identity is coherent, but window recomposition is not; still a viable future candidate, not suitable for current target selection.

No estimated variant is declared superior merely because of a numerical comparison.

## Early-versus-late stability

There are 83 pairs in both Charlotte windows. “Small” is defined prospectively as fewer than 10 comparable pairs; no evaluated threshold falls below that line, though 15–22 observations at the two highest thresholds remain too narrow for a robust policy decision. Pearson/Spearman are undefined only when fewer than two rows or zero variance occurs; neither occurs in the observed table.

### Standard fields

| Min POSS each | n/share | Field | Pearson | Spearman | MAE | RMSE | Median | Net sign | Early/Late variance |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83/100% | OFF | -.087 | -.018 | 14.735 | 24.912 | 8.0 | — | 278.664 / 292.285 |
| 1 | 83/100% | DEF | .218 | .253 | 13.370 | 18.569 | 8.4 | — | 189.295 / 165.749 |
| 1 | 83/100% | NET | .012 | .049 | 20.522 | 30.468 | 13.0 | 60.2% | 360.343 / 517.060 |
| 5 | 80/96.4% | OFF | .024 | .031 | 12.144 | 17.750 | 7.8 | — | 157.891 / 164.247 |
| 5 | 80/96.4% | DEF | .238 | .237 | 12.701 | 16.997 | 8.4 | — | 130.896 / 166.634 |
| 5 | 80/96.4% | NET | .039 | .053 | 19.296 | 27.753 | 12.95 | 60.0% | 320.461 / 427.708 |
| 10 | 77/92.8% | OFF | .006 | .058 | 11.400 | 16.644 | 7.2 | — | 145.015 / 131.850 |
| 10 | 77/92.8% | DEF | .207 | .208 | 12.013 | 16.170 | 8.0 | — | 113.477 / 145.172 |
| 10 | 77/92.8% | NET | -.008 | .031 | 17.648 | 25.128 | 12.6 | 59.7% | 270.284 / 318.687 |
| 25 | 72/86.7% | OFF | .085 | .107 | 9.504 | 13.310 | 6.6 | — | 99.483 / 92.379 |
| 25 | 72/86.7% | DEF | .140 | .140 | 11.444 | 15.641 | 7.7 | — | 103.171 / 116.180 |
| 25 | 72/86.7% | NET | -.053 | .019 | 16.703 | 24.097 | 11.9 | 59.7% | 228.637 / 249.752 |
| 50 | 64/77.1% | OFF | .149 | .131 | 8.788 | 11.800 | 6.25 | — | 106.017 / 56.272 |
| 50 | 64/77.1% | DEF | .273 | .202 | 9.800 | 12.784 | 7.4 | — | 98.269 / 81.994 |
| 50 | 64/77.1% | NET | .059 | .118 | 13.816 | 18.537 | 11.5 | 60.9% | 225.355 / 105.711 |
| 100 | 46/55.4% | OFF | .299 | .317 | 7.117 | 9.714 | 5.35 | — | 91.190 / 35.194 |
| 100 | 46/55.4% | DEF | .245 | .256 | 8.143 | 10.427 | 6.6 | — | 62.919 / 42.700 |
| 100 | 46/55.4% | NET | .219 | .222 | 9.861 | 13.073 | 7.65 | 63.0% | 151.216 / 36.601 |
| 200 | 22/26.5% | OFF | .456 | .400 | 4.127 | 5.262 | 3.4 | — | 22.139 / 26.073 |
| 200 | 22/26.5% | DEF | .191 | .125 | 6.255 | 7.865 | 5.4 | — | 17.635 / 25.468 |
| 200 | 22/26.5% | NET | .418 | .448 | 7.286 | 9.334 | 6.15 | 63.6% | 35.695 / 44.399 |
| 300 | 15/18.1% | OFF | .499 | .446 | 3.207 | 4.233 | 3.0 | — | 13.687 / 20.312 |
| 300 | 15/18.1% | DEF | .253 | .254 | 5.313 | 6.472 | 4.8 | — | 18.022 / 18.786 |
| 300 | 15/18.1% | NET | .426 | .447 | 5.813 | 7.674 | 3.6 | 60.0% | 26.570 / 39.299 |

### Estimated fields

| Min POSS each | n/share | Field | Pearson | Spearman | MAE | RMSE | Median | Net sign | Early/Late variance |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83/100% | E_OFF | -.178 | -.019 | 16.136 | 29.154 | 8.1 | — | 397.667 / 323.156 |
| 1 | 83/100% | E_DEF | .253 | .179 | 12.808 | 16.384 | 10.5 | — | 131.068 / 144.072 |
| 1 | 83/100% | E_NET | -.076 | .024 | 22.830 | 33.981 | 14.8 | 67.5% | 452.391 / 542.725 |
| 5 | 80/96.4% | E_OFF | -.007 | .062 | 12.314 | 18.859 | 7.95 | — | 158.996 / 193.956 |
| 5 | 80/96.4% | E_DEF | .221 | .153 | 12.701 | 16.322 | 10.2 | — | 113.140 / 143.996 |
| 5 | 80/96.4% | E_NET | .053 | .080 | 19.754 | 27.833 | 14.5 | 68.8% | 312.121 / 443.515 |
| 10 | 77/92.8% | E_OFF | -.015 | .097 | 11.338 | 17.413 | 7.6 | — | 135.338 / 162.772 |
| 10 | 77/92.8% | E_DEF | .183 | .110 | 12.306 | 15.778 | 9.9 | — | 107.291 / 125.892 |
| 10 | 77/92.8% | E_NET | .015 | .058 | 18.178 | 25.347 | 13.9 | 68.8% | 258.564 / 346.968 |
| 25 | 72/86.7% | E_OFF | .039 | .115 | 9.403 | 13.759 | 6.0 | — | 90.916 / 102.532 |
| 25 | 72/86.7% | E_DEF | .153 | .061 | 11.889 | 15.480 | 9.1 | — | 95.862 / 116.028 |
| 25 | 72/86.7% | E_NET | -.030 | .066 | 17.081 | 24.106 | 13.2 | 69.4% | 212.285 / 263.390 |
| 50 | 64/77.1% | E_OFF | .135 | .154 | 8.369 | 11.458 | 5.8 | — | 96.386 / 54.233 |
| 50 | 64/77.1% | E_DEF | .286 | .145 | 10.208 | 12.905 | 7.9 | — | 96.643 / 81.932 |
| 50 | 64/77.1% | E_NET | .132 | .194 | 13.866 | 17.802 | 11.75 | 73.4% | 218.564 / 91.276 |
| 100 | 46/55.4% | E_OFF | .305 | .312 | 6.589 | 9.169 | 4.6 | — | 83.697 / 31.010 |
| 100 | 46/55.4% | E_DEF | .225 | .164 | 8.883 | 11.101 | 7.25 | — | 65.199 / 45.020 |
| 100 | 46/55.4% | E_NET | .257 | .244 | 10.754 | 13.715 | 9.05 | 78.3% | 160.362 / 38.041 |
| 200 | 22/26.5% | E_OFF | .479 | .444 | 3.627 | 4.904 | 2.3 | — | 20.226 / 20.764 |
| 200 | 22/26.5% | E_DEF | .151 | .150 | 6.895 | 9.038 | 5.45 | — | 18.155 / 33.098 |
| 200 | 22/26.5% | E_NET | .452 | .445 | 8.377 | 10.527 | 7.2 | 81.8% | 42.143 / 49.434 |
| 300 | 15/18.1% | E_OFF | .523 | .520 | 2.933 | 3.938 | 2.2 | — | 11.766 / 16.699 |
| 300 | 15/18.1% | E_DEF | .211 | .150 | 5.647 | 7.204 | 4.8 | — | 19.599 / 19.887 |
| 300 | 15/18.1% | E_NET | .490 | .508 | 6.433 | 8.229 | 6.3 | 86.7% | 25.625 / 39.029 |

The broad pattern is reduced error and variance at higher exposure, especially from 100 to 300 possessions per window. Correlations remain modest and the high-threshold sample shrinks sharply. Legitimate instability is expected because the windows differ in opponents, injuries, trades, teammate combinations, coaching/role changes, and random shooting variance. These are not repeated measurements under identical basketball contexts.

## League-wide full-season exposure context

Across 5,297 Phase 1C rows, `POSS` has minimum 0, Q1 54, median 211, Q3 603, P90 1,317.2, P95 1,897.6, P99 3,211.36, maximum 4,817, and summed overlapping pair-row possessions 2,517,129.

| POSS threshold | Retained | Excluded | Retained row share | Retained possession share | NET variance | `|NET| >= 50` |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5,289 | 8 | 99.85% | 100.000% | 829.530 | 355 (6.71%) |
| 5 | 5,146 | 151 | 97.15% | 99.986% | 503.679 | 268 (5.21%) |
| 10 | 4,976 | 321 | 93.94% | 99.941% | 397.206 | 192 (3.86%) |
| 25 | 4,561 | 736 | 86.11% | 99.668% | 259.788 | 80 (1.75%) |
| 50 | 4,027 | 1,270 | 76.02% | 98.897% | 182.335 | 25 (0.62%) |
| 100 | 3,412 | 1,885 | 64.41% | 97.101% | 126.387 | 1 (0.03%) |
| 200 | 2,702 | 2,595 | 51.01% | 93.044% | 93.979 | 0 |
| 300 | 2,193 | 3,104 | 41.40% | 88.006% | 84.037 | 0 |

| POSS band | Rows | Possessions | NET variance | `|NET|>=25` | `|NET|>=50` | `|NET|>=100` |
|---|---:|---:|---:|---:|---:|---:|
| 0–9 | 321 | 1,496 | 7,630.899 | 215 | 164 (51.09%) | 74 |
| 10–24 | 415 | 6,859 | 1,816.873 | 241 | 112 (26.99%) | 13 |
| 25–49 | 534 | 19,408 | 838.516 | 211 | 55 (10.30%) | 0 |
| 50–99 | 615 | 45,212 | 486.340 | 142 | 24 (3.90%) | 0 |
| 100–199 | 710 | 102,107 | 245.719 | 83 | 1 (0.14%) | 0 |
| 200–499 | 1,130 | 370,307 | 116.423 | 30 | 0 | 0 |
| 500–999 | 793 | 556,730 | 83.011 | 3 | 0 | 0 |
| 1000+ | 779 | 1,415,010 | 63.684 | 4 | 0 | 0 |

Extreme net ratings are heavily concentrated at low exposure. Shrinking variance does not by itself prove predictive reliability; pair role, roster selection, and context also change with exposure.

## Endpoint-omission sensitivity

| POSS threshold | Known omitted pairs | Known omitted POSS | Omitted exposure share | Full rows / observed union | Bounded result |
|---:|---:|---:|---:|---:|---|
| 1 | 6 | 23 | 0.027860% | 250 / 256 | known omissions survive |
| 5 | 2 | 12 | 0.014538% | 250 / 252 | known omissions survive |
| 10 | 0 | 0 | 0% | 244 / 244 | no known omission survives this threshold |
| 25 | 0 | 0 | 0% | 232 / 232 | no known omission survives this threshold |
| 50 | 0 | 0 | 0% | 208 / 208 | no known omission survives this threshold |
| 100 | 0 | 0 | 0% | 170 / 170 | no known omission survives this threshold |
| 200 | 0 | 0 | 0% | 122 / 122 | no known omission survives this threshold |
| 300 | 0 | 0 | 0% | 92 / 92 | no known omission survives this threshold |

This does not mean the endpoint is exhaustive above 10 possessions. It means only that none of the seven currently observed Charlotte omissions survives the evaluated threshold. Threshold choice must be justified by stability and usable sample size, not omission removal alone.

## Decision questions

1. **Are standard full-season rating semantics sufficiently documented?** Yes, for an observed team-while-pair-on-court rate. The field is not individual or on/off.
2. **Are estimated-rating semantics sufficiently documented?** No. Availability and identity are clear; the exact estimation method is not.
3. **Why did offensive recomposition succeed while defensive/net failed?** Returned `POSS` empirically acts as the offensive team-possession denominator. Defense is defined over opponent possessions, which are not separately exposed; net inherits the denominator mismatch. Missing internal precision may also contribute. Exact causation is not claimed beyond those fields.
4. **Is that failure a problem for directly returned full-season `NET_RATING`?** No. Direct validity and independent-window reconstruction are separate. All 5,297 direct net values are coherent with direct offense minus defense within rounding.
5. **Is there evidence for a plausible reliability-threshold range?** There is a preliminary study range around 100–300 possessions per window: errors and variance fall materially there while some rows remain. It is evidence for further evaluation, not an approved range.
6. **Is the evidence sufficient to select a final threshold?** No. Charlotte has only 46 qualifying both-window pairs at 100, 22 at 200, and 15 at 300; contexts are not controlled.
7. **Would Philadelphia window testing materially improve the decision?** It would add one affected team, but would not reveal the missing opponent denominator or alone establish a league-wide reliability policy. It is not necessary to settle standard semantics.
8. **Is additional multi-team window evidence required?** Yes before final threshold policy or recovered-window target construction. A broader deliberately sampled audit is more informative than Philadelphia alone.
9. **Can historical raw ingestion proceed while threshold selection is deferred?** Conditionally yes, under separate authorization, if it remains immutable raw-only acquisition, records the endpoint-returned population limitation, and defers curation/model eligibility. Phase 1F itself performs none.
10. **What should happen next?** Approve a bounded multi-team temporal-reliability phase using predeclared teams/windows and no target reconstruction, or begin raw-only historical acquisition with threshold and curated-table work explicitly deferred. Before any model-ready materialization, resolve the final target variant, reliability threshold, and endpoint-population policy.

## Secondary classifications

- Standard target direct validity: **supported as an observed full-season endpoint outcome**.
- Standard target window recomposability: **`OFF_RATING` supported; `DEF_RATING` and `NET_RATING` not safely recomposable from available window fields**.
- Estimated target direct validity: **directly available and internally coherent, but semantic formula unresolved; unsuitable for current selection and still a candidate**.
- Estimated target window recomposability: **not empirically recomposable with returned `POSS`**.
- Endpoint-omission risk: **no known omission at `POSS >= 10`; residual/global risk unproven**.
- Reliability-threshold readiness: **unresolved; Charlotte suggests a 100–300 study range but cannot establish policy**.
- Philadelphia diagnostic necessity: **not necessary for semantic resolution; insufficient alone for reliability policy**.
- Historical-ingestion readiness: **conditionally ready for separately authorized immutable raw-only acquisition; not ready for curation or modeling**.

## Implementation and replay

`phase1f_target_audit.py` is a pure cache-analysis module with no requests import, transport function, or network surface. It validates the committed Phase 1C–1E evidence before producing results. Every full-season Charlotte recomposition row and all summary tables are retained in the deterministic in-memory result; no curated dataset or database was written.

Two independent cache-only analyses must match `summary_sha256`; final verification records the resulting hash, tests, Git checks, ignore checks, stale-language search, prohibited-artifact search, and task-local basetemp cleanup.

## Final verification

- Two independent cache-only analyses: identical.
- Deterministic summary SHA-256, both runs: `bbe5b0f3805e06ce553774779ad5210b5af8678f3cd84da4d0820ecf3a700d19`.
- Network protection: socket creation and `requests.Session.request` were blocked during the integration test; analysis still passed.
- Immutable artifacts remained unchanged at the three SHA-256 values recorded above.
- Focused Phase 1F tests: 14 passed.
- Complete offline research suite: 183 passed.
- Pytest warnings: two non-failing access warnings for the pre-existing inaccessible `.pytest_cache`; it was not altered.
- `git diff --check`: passed.
- Git-ignore verification: Phase 1C, Phase 1D, Phase 1E caches and the task-local pytest basetemp are ignored by `research/pair-fit-v2/.gitignore`.
- Stale-language review: Phase 1E's prior classification remains only as historical evidence; current contract documents Phase 1F's direct-validity/recomposability distinction.
- Prohibited-artifact search: no Parquet, DuckDB, Feather, SQLite/database, or 2025-26 research artifact.
- Task-local `research/pair-fit-v2/.pytest_tmp`: safely removed after tests; the pre-existing `.pytest_cache` was untouched.
