# Phase 3A population and policy audit

## Plain-English result

The complete 2014-15–2023-24 cache supports a full-population curation audit, but it does **not** support selecting curation policies yet. The raw endpoint produced 46,938 valid team-season-pair observations (46,786 with positive possessions and 152 preserved at zero). Very low exposures contain dramatically more extreme and variable returned net ratings. `POSS >= 100` is a credible candidate for later evaluation—not an approved rule: it retains 30,580 rows (65.15%) and 97.52% of overlapping pair possessions, while reducing target variance from 944.07 over all returned rows to 112.44. A low floor plus a capped or transformed possession weight is also credible and should be evaluated alongside hard thresholds.

## Decisions now requiring user input

1. Which bounded Phase 3B candidate set should be materialized for later evaluation: a hard-floor range (recommended: 50, 75, 100, 150), a low floor with capped/square-root/log weight, or both?
2. Which missing-history candidates should continue: complete-case benchmark, 1/2/3/5-year most-recent profile with `history_gap`, and fold-only imputation plus missingness indicators? Recommendation: retain all as evaluation candidates; do not approve a handcrafted archetype fallback.
3. Authorize a narrowly specified supplemental prior-player feature acquisition before Phase 3B only if shot-zone profiles are required. Current caches cannot provide pace or shot zones.
4. Approve the exact Phase 3B curation/evaluation contract separately. This report does not select a final target threshold, weight, history policy, feature list, fold boundary, metric, or model.

## Recommendations and alternatives

- Carry `POSS >= 50`, `>=75`, `>=100`, `>=150`, and `floor 25 + capped-linear-300` forward. The 100 rule is interpretable and removes most small-sample volatility without concentrating all weight in a small set of star pairs; it is not “best” without future-only evaluation.
- Compare equal, square-root, log1p, capped-linear 100/300/500, and floor-25+capped-300 weights. Avoid uncapped linear possession weighting as the sole candidate: its effective sample size is only 15,981 and the top tenth of rows has 44.2% of weight.
- Carry strict one-year history, bounded 2/3/5-year most-recent history with an explicit gap, and fold-only numeric imputation plus indicators. Treat no-history examples as a separate later cohort.
- Keep 2019-20 and 2020-21; add an explicit pandemic-era flag for later sensitivity analysis. Do not manually correct or discard them, and do not add recency weights now.
- Add endpoint provenance flags—not automatic exclusions—for exact-250 returned team-seasons, zero-possession rows, schema contract version, raw asset hashes, and source/reuse status.

## Technical evidence

### Immutable starting evidence and scope

The audit began on `research/pair-fit-v2`, HEAD `682d40ea47664d6fed27a6b4317bb78ae8fcbf0a` (`Phase 2E complete…`), with a clean `git status --short --untracked-files=all`. Repository guidance was read before changes. The cache-only replay verifies raw-body hashes of every assembled asset and the following committed anchors: Phase 1C manifest `5465…a30c`, Phase 1D ledger `f687…dee9`, Phase 1E ledger `5e51…ccfd`, Phase 1F analysis `bbe5…0d19`, all 20 persisted Phase 2B–2E manifest/ledger state hashes, and Phase 2E combined analysis `d57840f80172df49ea7350520fbf1961499c6f558c70c40ced2bab38c7b5379f`.

It uses the complete 2014-15 through 2023-24 acquired training window: 600 pair response assets, 18 release-owned player assets plus two reused verified player dependencies, and the established 2024-25 Phase 1 validation population only as protected provenance evidence. It neither accesses nor creates 2025-26 data. Global endpoint-population exhaustiveness remains unproven.

### Row grain and target

One proposed modeling row is **team × target season × canonical unordered pair of stable positive player IDs**. The observation key retains team and season, so the same pair is deliberately not collapsed across teams or years. Base and Advanced keys reconcile one-to-one before the Advanced `POSS` and ratings are joined to Base shared minutes. A pair that occurs for two teams (including after trades) represents two valid contextual observations, not a duplicate. A duplicate is only repeated full observation key `(season, team, sorted player IDs)`. Zero-possession rows remain in the raw audit and are target-ineligible rather than silently removed.

The order is canonical because the target is team performance while both players share the court: swapping the listed players does not change that shared-court event. Thus its primary prediction should be order-invariant. A primary-handler adjustment would introduce a different, unapproved task and is intentionally absent.

`NET_RATING` is the primary supported candidate: directly returned full-season team net rating while the pair shares the court. It is **not** a context-free measurement of pair chemistry; teammates, opponents, roles, coaching, injuries, and selection into minutes remain part of the observation. A later product fit score may transform model outputs without redefining this training outcome. `OFF_RATING` and `DEF_RATING` remain secondary outcomes. All 46,938 returned net values are numeric; all 46,786 positive-possession rows satisfy returned `NET_RATING ≈ OFF_RATING - DEF_RATING` within the documented 0.1 display tolerance.

| Population | Mean | Median | SD | Q1 / Q3 | P1 / P99 | Min / max | `|NET| >= 50` |
|---|---:|---:|---:|---:|---:|---:|---:|
| All returned rows | -4.51 | -1.9 | 30.73 | -12.1 / 6.0 | -107.8 / 80.5 | -300 / 300 | available in deterministic ledger |
| `POSS >= 100` | -1.85 | -1.2 | 10.60 | -8.1 / 4.8 | -30.2 / 23.3 | -63.3 / 65.4 | 17 (0.06%) |

Every season is retained. Unweighted target variance is higher in 2021-22 (1,125.42) and 2023-24 (1,064.02) than in 2019-20 (817.79), while this describes returned rows rather than comparable basketball conditions. Season and team-season distributions, extrema, and row-level target/exposure records are in the deterministic in-memory machine-readable summary.

### Exposure sensitivity (descriptive, not predictive accuracy)

| Minimum `POSS` | Rows retained | Row share | Possession share | NET variance | Complete / one / both history |
|---:|---:|---:|---:|---:|---:|
| >0 | 46,786 | 99.68% | 100.000% | 907.84 | 30,688 / 14,171 / 1,927 |
| 5 | 45,450 | 96.83% | 99.986% | 555.90 | 30,068 / 13,541 / 1,841 |
| 10 | 43,698 | 93.10% | 99.936% | 384.42 | 29,314 / 12,667 / 1,717 |
| 25 | 39,928 | 85.07% | 99.679% | 235.50 | 27,493 / 10,986 / 1,449 |
| 50 | 35,771 | 76.21% | 99.062% | 160.17 | 25,283 / 9,335 / 1,153 |
| 75 | 32,825 | 69.93% | 98.318% | 128.81 | 23,670 / 8,198 / 957 |
| **100** | **30,580** | **65.15%** | **97.517%** | **112.44** | **22,358 / 7,378 / 844** |
| 150 | 27,001 | 57.52% | 95.699% | 91.74 | 20,184 / 6,161 / 656 |
| 200 | 24,311 | 51.79% | 93.779% | 80.88 | 18,505 / 5,284 / 522 |
| 300 | 20,302 | 43.25% | 89.700% | 67.51 | 15,847 / 4,087 / 368 |
| 500 | 14,986 | 31.93% | 81.095% | 56.15 | 12,056 / 2,707 / 223 |
| 1000 | 7,880 | 16.79% | 60.089% | 44.95 | 6,664 / 1,146 / 70 |

All thresholds retain all ten seasons and all 300 team-seasons through 1,000 possessions; their per-season/team representation, quantiles, extreme shares, and exact-250 flags are retained in the summary. The evidence shows descriptive target stabilization and exposure sensitivity, not predictive accuracy. It does not approve 100 because Charlotte’s known omissions vanish above 10; an exposure cutoff cannot prove endpoint exhaustiveness.

For adjacent-season repeat diagnostics, all repeated pair observations have correlation .056 and MAE 15.39 at positive exposure; at `>=100` in both seasons these are .258 and 8.39 (7,909 matches). Same-team repeats are .259 and 8.35 (7,723 matches). At 300 in both seasons, same-team correlation reaches .383 but only under changed basketball context. This is a reliability/stability diagnostic, not a claim of invariant pair chemistry.

### Candidate weighting, without a model

Effective sample size answers: “how many equally weighted rows would carry roughly the same amount of information as these unequal weights?” It falls when a few rows dominate.

| Formula | Eligible rows | Effective sample size | Top 10% row-weight share | `<100 POSS` weight share |
|---|---:|---:|---:|---:|
| Equal | 46,786 | 46,786 | 10.0% | 34.64% |
| Linear possessions | 46,786 | 15,981 | 44.2% | 2.48% |
| Square root | 46,786 | 30,150 | 25.9% | 10.59% |
| `log1p(POSS)` | 46,786 | 42,293 | 14.8% | 21.80% |
| Capped linear 100 | 46,786 | 39,316 | 12.8% | 16.44% |
| Capped linear 300 | 46,786 | 32,843 | 16.3% | 7.01% |
| Capped linear 500 | 46,786 | 29,161 | 19.4% | 4.98% |
| Capped linear 1000 | 46,786 | 23,843 | 26.7% | 3.43% |
| Floor 25 + cap 300 | 39,928 | 32,268 | 14.1% | 6.16% |

The deterministic summary also reports normalized total weight, concentration by player (half weight allocated to each member), team-season, and season. Capping and transforms are more interpretable compromises than letting a few durable/star/rotation pair observations dominate; equal weighting gives fragile rows equal influence. These are prospective tradeoffs, not a selected formula.

### Missing prior-player history

Strict history uses only the immediately preceding season and stable league-wide player ID; a normal team change is not missingness. Of 1,424 observed players, 1,088 have strict prior history and 336 do not. Across rows: 30,773 complete, 14,237 one-missing, and 1,928 both-missing. Their overlapping pair possessions are 19,493,056, 4,357,305, and 390,781 respectively; pair minutes are 9,320,600.03, 2,070,675.53, and 185,303.09. These are overlapping pair exposures, not league totals.

| Most-recent allowed lookback | Complete | One missing | Both missing | Rows upgraded to complete | Remaining missing rows |
|---:|---:|---:|---:|---:|---:|
| 1 season (strict) | 30,773 | 14,237 | 1,928 | — | 16,165 |
| 2 seasons | 31,923 | 13,362 | 1,653 | 1,150 | 15,015 |
| 3 seasons | 32,375 | 13,042 | 1,521 | 1,602 | 14,563 |
| 5 seasons | 32,493 | 12,954 | 1,491 | 1,720 | 14,445 |

The 5-year ledger has observed gaps of 1: 75,783 player-row appearances; 2: 1,425; 3: 584; 4: 120; 5: 28. Earlier target seasons are constrained by the acquired 2013-14 starting profile. Where evidence permits, the audit calls a player “absent immediately prior but earlier acquired record available”; where no earlier acquired profile exists it says exactly that. It does not speculate that such cases are rookies, retirees, source errors, or non-NBA players.

Candidate fallbacks are: (1) complete-case benchmark (simple but potentially unrepresentative); (2) bounded most-recent history plus `history_gap` (temporal and interpretable); (3) numeric imputation calculated **inside each applicable training fold only**, with explicit missingness indicators; and (4) a generic/cohort fallback reserved for later research. Zero is not an acceptable universal substitute: zero attempts, steals, or minutes means something different from unknown. Using all seasons to calculate replacements would leak future information. A hand-built cohort profile adds untested basketball assumptions. No fallback is approved here.

### Current feature inventory and feasibility

The acquired source is prior-season `LeagueDashPlayerStats`, Base, `Per100Possessions`, one league-aggregate player-season row keyed by `PLAYER_ID`; the matching Totals source supplies prior `TOTAL_MIN` as a reliability field. Across 5,219 acquired profile rows, all listed non-rank primitives are numerically present. They are prior to each target season and may be candidate inputs after fold-specific processing, but are not a final feature set.

| Group | Available primitive fields / safe derivations | Unit and caution |
|---|---|---|
| Scoring, shooting | `FGM`, `FGA`, `FG_PCT`, `PTS`; `FG3M`, `FG3A`, `FG3_PCT`; `(FGA-FG3A)`, `(FGM-FG3M)` | Per-100 source rates/counts; preserve undefined rate if denominator is zero |
| Free throws | `FTM`, `FTA`, `FT_PCT`; `FTA/FGA` | Per-100; denominator guarded |
| Playmaking/turnovers | `AST`, `TOV` | Per-100, prior-season only |
| Rebounding | `OREB`, `DREB`, `REB` | Per-100 |
| Defensive events/fouls | `STL`, `BLK`, `BLKA`, `PF`, `PFD` | Per-100 |
| Availability/reliability | `GP`, Per100 `MIN`, Totals `MIN` | Totals minutes are a diagnostic/eligibility quantity, not inherent quality |
| Context/provenance | `AGE`, `TEAM_COUNT`, source season, source hashes | age is prior context; team count exposes aggregate traded-season record |

Safe derived candidates are three-point attempt share `FG3A/FGA`, two-point attempt share `(FGA-FG3A)/FGA`, free-throw attempt rate `FTA/FGA`, three-point accuracy `FG3M/FG3A`, two-point accuracy `(FGM-FG3M)/(FGA-FG3A)`, and overall FG accuracy `FGM/FGA`. Rank columns, names, team identifiers as quality, target-season player stats, target-season pair outcomes, and accidental row order are forbidden substantive features.

Player-level pace is absent. Returned Advanced pair `PACE` is target-season shared-court team context and would leak if used as a predictor; even a future prior team pace is team context rather than a player-intrinsic skill. Coarse shot zones are absent: rim, paint, midrange, corner-three, and above-the-break-three distributions cannot be recovered from the cache. If approved later, acquire a compact prior-season player shooting-split source at player-season grain (zone attempts, makes, and shares) rather than raw shot events; use a small defined set of zone shares/efficiencies. This is bounded supplemental acquisition planning only—no request was made.

Candidate pair features should be symmetric transformations of primitives: sum, mean, min, max, absolute difference, combined attempts, usage-related differences if a documented source is acquired, and learned overlap/complementarity interactions. Keep individual features, symmetric pair features, team/context fields, and provenance/diagnostic fields distinct. Do not encode a manual “good/bad” basketball penalty in the target.

### Season and endpoint caveats

Pandemic flags are justified for 2019-20 (4,545 rows; 4,531 positive) and 2020-21 (5,014; 4,991); both remain in population. The 2021-22 row count is high (5,745) and should be visible to later season-fixed validation. The endpoint exact-250 flags, with displayed names generated from the verified team-ID directories, are 2020-21 Houston (`1610612745`) and 2023-24 Toronto (`1610612761`), Memphis (`1610612763`), and Detroit (`1610612765`). Many other team-seasons have zero-possession rows; none are deleted. All assembled assets use the certified Base/Advanced contracts; no unusual schema was accepted. No threshold proves unreturned pairs are low exposure or proves population exhaustiveness.

### Later evaluation boundary

Phase 3A trains no model and estimates no predictive accuracy. The proposed later structure is chronological rolling/forward validation on historical seasons, then 2024-25 development validation, with 2025-26 untouched for one final test. Report all-future-pair (every later pair), previously unseen-pair (a pair identity absent from training), complete/partial/no-history cohorts, exposure bands, and pandemic-season sensitivity separately. Final folds, metrics, baselines, and model selection remain user decisions.

## Glossary

- **Exposure:** possessions while the two players share the court; larger exposure generally makes a returned rate less noisy.
- **Effective sample size:** the comparable count of equally weighted rows after unequal weights concentrate influence.
- **Imputation:** replacing missing numeric values with a value learned only from the relevant training fold.
- **Missingness indicator:** a separate flag telling a model that a value was unavailable.
- **Leakage:** using information unavailable at the time a prediction would be made, such as target-season player results.
- **Rolling/forward validation:** training on earlier seasons and evaluating on later ones, mirroring actual forecasting.

## Classifications

Primary classification: **`full-population audit supported; curation policy candidates ready for user decision`**.

- Proposed row grain: supported.
- Primary-target readiness: supported as directly returned contextual team shared-court outcome.
- 100-possession candidate: plausible candidate; not approved.
- Weighting-policy readiness: bounded candidates ready; no formula selected.
- Missing-history-policy readiness: bounded candidates ready; no policy selected.
- Current-feature readiness: basic prior player profiles supported; final feature list unresolved.
- Shot-profile readiness: unavailable from current cache.
- Supplemental-acquisition necessity: conditionally needed if zone profile is required.
- Temporal-evaluation readiness: proposed only; final contract requires approval.
- Phase 3B readiness: ready after the listed user decisions.

Deterministic cache-only analysis SHA-256: `dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f`.
