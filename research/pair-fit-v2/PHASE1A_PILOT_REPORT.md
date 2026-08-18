# Phase 1A pilot report: bounded multi-team ingestion and validation

## Scope and status

This report is separate from the Phase 0 feasibility chronology in `FEASIBILITY_REPORT.md`. It covers only the bounded Phase 1A multi-team pilot: three new teams (Boston Celtics, Washington Wizards, Brooklyn Nets), combined with the existing cached Golden State Warriors data, all for the 2024-25 target season and the existing 2023-24 prior-player cache.

**Revised feasibility classification:**

`Phase 1A bounded multi-team pilot complete; schema and join behavior are consistent across the four pilot teams; prior-history coverage varies materially within this bounded sample`

This report does not claim predictive validity, does not select a final feature set, does not apply an exposure threshold, and does not construct a train/test split. No model was trained.

## Evidence classification

- **Live observations**: the six new Phase 1A `TeamDashLineups` responses (Boston/Washington/Brooklyn, Base and Advanced), fetched once each and cached.
- **Cached observations**: the Warriors Base/Advanced responses and the 2023-24 `LeagueDashPlayerStats` response, all reused from Phase 0 without refetching.
- **Derived summaries**: all coverage rates, join results, schema fingerprints, and possession/rating distributions computed from the above.
- **Projections**: the one-season 30-team and multi-season volume estimates below. These are rough and explicitly not guaranteed.
- **Unverified assumptions**: that observed schemas and coverage patterns hold for other seasons, playoff data, or teams outside this four-team sample.
- **Modeling decisions still pending**: exposure/possession threshold, final feature set, train/validation/test split design, and the no-history fallback model.

## Git baseline

- Starting branch: `research/pair-fit-v2`
- Starting commit: `1fc0eef` ("Reached readiness for Phase 1A development of a bounded multi-team ingestion and validation pilot")
- Working tree was clean before this pilot began.

## Validated Phase 0 cache (used, not refetched)

All three required Phase 0 caches were validated against their recorded canonical JSON hashes before any new request was made:

- `team_dash_lineups_1610612744_2024-25_base.json`: hash `71e194d4338e09b0` — match
- `team_dash_lineups_1610612744_2024-25_advanced.json`: hash `58b62bbde00ba68a` — match
- `league_dash_player_stats_2023-24_base_per100possessions.json`: hash `46103a3e96e524f8` — match

## Pilot team manifest (validated against cached 2024-25 LeagueStandingsV3)

| Team | Team ID | Abbreviation | Source | Role in pilot |
| --- | --- | --- | --- | --- |
| Golden State Warriors | `1610612744` | GSW | Phase 0 cache only | Baseline team (not refetched) |
| Boston Celtics | `1610612738` | BOS | Phase 1A new | Stable veteran contender |
| Washington Wizards | `1610612764` | WAS | Phase 1A new | Young/rebuilding roster |
| Brooklyn Nets | `1610612751` | BKN | Phase 1A new | Higher roster turnover/trade exposure |

All four team ID/name/abbreviation pairs were cross-checked against the cached `LeagueStandingsV3` response (`TeamID`, `TeamCity`+`TeamName`, `TeamSlug`) and matched exactly; the prompt's labels were not relied on alone.

## Live acquisition: exact requests and results

Six new live requests were planned (max allowed) and all six succeeded, in the required sequential order, using the proven direct `requests.Session` transport, canonical headers, 30-second timeout, no proxy, no retries:

| # | Team | Measure | Result | Latency (s) | Payload (bytes, on-disk indented JSON) | Canonical JSON hash |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Boston Celtics | Base | HTTP 200 | 1.796 | 136,558 | `2d02052655469872` |
| 2 | Boston Celtics | Advanced | HTTP 200 | 1.837 | 123,846 | `b8174589a6727ee3` |
| 3 | Washington Wizards | Base | HTTP 200 | 1.892 | 200,588 | `31c70fcac7c8e03a` |
| 4 | Washington Wizards | Advanced | HTTP 200 | 1.816 | 182,140 | `05e9e403129391d9` |
| 5 | Brooklyn Nets | Base | HTTP 200 | 1.820 | 197,118 | `f17163909cbfae2b` |
| 6 | Brooklyn Nets | Advanced | HTTP 200 | 2.065 | 178,434 | `68c1916f0ac6edda` |

No failures occurred, so the stop/resume path was not exercised on live data; it is covered offline instead (see Tests).

**Hash and payload-size semantics:** each successful HTTP acquisition establishes the recorded source event. The stored canonical JSON hash verifies semantic cache-content integrity relative to the hash recorded at acquisition: parsing the cache and hashing the same sorted-key JSON representation produces the recorded value. It does not independently prove source authenticity, and it does not prove byte-for-byte file identity after JSON reserialization because insignificant whitespace and object-key order can change while parsed JSON content remains equivalent.

The Phase 0D metadata for the Warriors Base response records `payload_size_bytes: 58754`, which does not match the current on-disk cache-file size (177,060 bytes), even though the canonical JSON hash still matches. The two sizes were measured under different conventions (an earlier response-body byte count versus the later indented on-disk file size). This historical metadata discrepancy is preserved; all volume estimates below use a uniform on-disk file-size measurement for all four teams. Future acquisition metadata should distinguish `response_body_bytes`, `cache_file_bytes`, `canonical_json_hash`, an optional `raw_body_hash`, and a `serialization_version`.

## Actual schemas, row counts, and per-team validation

All four teams returned identical result-set structure: `Overall` (57 Base / 49 Advanced columns, 1 row) and `Lineups` (56 Base / 48 Advanced columns, N rows). The pair result set was identified from observed `GROUP_ID` content (`-PLAYER_ID_1-PLAYER_ID_2-` pattern), not position alone.

| Team | Base pair rows | Advanced pair rows | Malformed pairs | Duplicate canonical pairs | Zero-game rows | Zero-minute rows (Base / Advanced) |
| --- | --- | --- | --- | --- | --- | --- |
| Golden State Warriors | 183 | 183 | 0 | 0 | 0 | 0 / 0 |
| Boston Celtics | 141 | 141 | 0 | 0 | 0 | 0 / 0 |
| Washington Wizards | 208 | 208 | 0 | 0 | 0 | 0 / 2 |
| Brooklyn Nets | 204 | 204 | 0 | 0 | 0 | 0 / 0 |

**Observed checks only, not "perfect" claims:** every team passed identity parsing (exactly two distinct player IDs per pair), canonical unordered pair-key uniqueness within team/season/measure, and zero malformed or duplicate pairs. Washington's two Advanced-measure zero-minute rows correspond to Base rows with small nonzero fractional minutes (0.483 and 0.143); this indicates Advanced `MIN` is rounded to whole numbers while Base `MIN` retains fractional precision for the same pairs — a measure-level precision difference, not a team-specific defect.

## Per-team Base-to-Advanced joins

Joined on target season, team ID, and canonical unordered player-ID pair, attaching season/team context from the validated request (not from row order or names):

| Team | Base pairs | Advanced pairs | Matched | Base-only | Advanced-only | Base match rate | Advanced match rate | Duplicate-key violations | One-to-one |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Golden State Warriors | 183 | 183 | 183 | 0 | 0 | 100.0% | 100.0% | 0 | Yes |
| Boston Celtics | 141 | 141 | 141 | 0 | 0 | 100.0% | 100.0% | 0 | Yes |
| Washington Wizards | 208 | 208 | 208 | 0 | 0 | 100.0% | 100.0% | 0 | Yes |
| Brooklyn Nets | 204 | 204 | 204 | 0 | 0 | 100.0% | 100.0% | 0 | Yes |

No unmatched rows occurred in any team, so no unmatched-row reasons needed to be determined for this pilot.

## Combined four-team canonical key validation

Canonical observation key: (target season, team ID, canonical player 1 ID, canonical player 2 ID).

- Combined row count: 183 + 141 + 208 + 204 = **736**
- Unique observation keys: **736** (no duplicates)
- Duplicate observation-key count: **0**
- Cross-team players (same `PLAYER_ID` on two different pilot teams this season — legitimate trade-context observations, not deduplicated):
  - `203471` — Golden State Warriors and Brooklyn Nets
  - `1641736` — Golden State Warriors and Brooklyn Nets
  - `1641798` — Brooklyn Nets and Washington Wizards
- Cross-team pairs (the same two-player pair appearing for more than one team): **0**

**Explicit non-independence disclosure:** pair rows overlap extensively — every teammate pair sharing a player is not statistically independent of every other pair involving that player, and the three cross-team players above show the same individual contributing observations to two different team-context rows this season. No random train/test split was created or is appropriate without addressing this overlap.

### Validation direction

Future validation should be time-ordered or rolling-origin so that every evaluated target is predicted only from information available earlier in time. The 2025-26 season remains untouched as the final test season. A random pair-row split is explicitly rejected: overlapping players and pairs violate row independence and would allow closely related observations to cross split boundaries.

## Prior-player join coverage (per team and combined)

Reused the cached 2023-24 `LeagueDashPlayerStats` table; no new player-stat request was made. Joined both canonical player IDs independently per pair, by stable `PLAYER_ID` only.

### Player-level coverage

| Team | Unique player IDs | Matched to 2023-24 | No 2023-24 record | Coverage rate |
| --- | --- | --- | --- | --- |
| Golden State Warriors | 23 | 19 | 4 | 82.6% |
| Boston Celtics | 18 | 16 | 2 | 88.9% |
| Washington Wizards | 24 | 19 | 5 | 79.2% |
| Brooklyn Nets | 24 | 18 | 6 | 75.0% |
| **Combined (unique across 4 teams)** | **86** | **71** | **15** | **82.6%** |

Missing IDs are described only as "no 2023-24 LeagueDashPlayerStats record":
- Warriors: `1641736` (R. Beekman), `1641879` (Y. Collins), `1642050` (J. Rowe), `1642366` (Q. Post)
- Celtics: `1631248` (B. Scheierman), `1641936` (M. Norris)
- Wizards: `1641798` (J. Martin), `1642259` (A. Sarr), `1642267` (B. Carrington), `1642273` (K. George), `1642358` (A. Johnson)
- Nets: `1630623` (T. Etienne), `1631166` (D. Timme), `1631213` (T. Martin), `1641736` (R. Beekman), `1641798` (J. Martin), `1642385` (C. Yongxi)

### Pair-level coverage

| Team | Total pairs | Complete | One missing | Both missing | Complete rate | Incomplete rate |
| --- | --- | --- | --- | --- | --- | --- |
| Golden State Warriors | 183 | 143 | 37 | 3 | 78.1% | 21.9% |
| Boston Celtics | 141 | 115 | 25 | 1 | 81.6% | 18.4% |
| Washington Wizards | 208 | 119 | 79 | 10 | 57.2% | 42.8% |
| Brooklyn Nets | 204 | 130 | 64 | 10 | 63.7% | 36.3% |
| **Combined** | **736** | **507** | **205** | **24** | **68.9%** | **31.1%** |

**This is the central Phase 1A coverage finding:** prior-history coverage varies materially across the four pilot teams. The pattern is consistent with the deliberately selected roster profiles, but this four-team sample does not establish roster type as the cause or prove that the same relationship holds league-wide. A single one-team coverage estimate should not be treated as representative of unobserved teams.

### Exposure-weighted diagnostic coverage (explicit sums, not inferred from percentages)

These are overlapping, per-pair-row sums recalculated directly from the cached tables — not estimates of unique team minutes or possessions, and not used as predictive features.

| Team | Complete-prior Base minutes | Incomplete-prior Base minutes | Total Base minutes | Complete % | Complete-prior Advanced possessions | Incomplete-prior Advanced possessions | Total Advanced possessions | Complete % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Golden State Warriors | 36,469.44 | 2,990.56 | 39,460.00 | 92.4% | 77,640 | 6,365 | 84,005 | 92.4% |
| Boston Celtics | 37,999.26 | 1,660.74 | 39,660.00 | 95.8% | 78,057 | 3,298 | 81,355 | 96.0% |
| Washington Wizards | 15,931.53 | 23,528.47 | 39,460.00 | 40.4% | 34,613 | 50,904 | 85,517 | 40.5% |
| Brooklyn Nets | 31,323.29 | 8,236.71 | 39,560.00 | 79.2% | 64,460 | 17,229 | 81,689 | 78.9% |
| **Combined** | **121,723.52** | **36,416.48** | **158,140.00** | **77.0%** | **254,770** | **77,796** | **332,566** | **76.6%** |

For the Washington Wizards specifically, only about 40% of shared-court exposure this season belongs to pairs with complete prior-season history for both players — a materially different picture from the Warriors' 92%.

## Missing-history policy applied

The Phase 0F provisional baseline policy was applied unchanged, with no new policy decision made in Phase 1A:

- All 736 combined pair rows are preserved; none were dropped.
- Each pair row is classified with `prior_history_status`: `complete`, `one_missing`, or `both_missing` (counts above).
- `complete`-status pairs (507 of 736) form the future primary baseline population, subject independently to valid-target eligibility.
- No prior NBA statistics were zero-imputed.
- `one_missing` and `both_missing` rows remain available for later evaluation of one universal no-history fallback; no fallback model was built.
- The same policy applies to every team; no roster-specific policy is introduced.

**Effect per team:** the policy retains 100% of rows everywhere, while the `complete` share available to the primary baseline varies from 57.2% (Wizards) to 81.6% (Celtics). This difference is descriptive within the four-team sample and is not attributed causally to roster type.

## Target and reliability audit (per team and combined)

`NET_RATING` is confirmed as a rate target in all four teams; Base `PLUS_MINUS` remains a cumulative, non-rate statistic (combined Base `PLUS_MINUS` range: -470 to +388, mean -7.95 across 736 rows — clearly cumulative, not a per-100-possession figure).

| Team | OFF_RATING range / mean | DEF_RATING range / mean | NET_RATING range / mean | Advanced POSS range / mean | Base MIN range / mean |
| --- | --- | --- | --- | --- | --- |
| Golden State Warriors | 0.0-200.0 / 108.62 | 0.0-142.9 / 107.04 | -83.3-200.0 / 1.58 | 1-3,046 / 459.04 | 0.79-1,419.12 / 215.63 |
| Boston Celtics | 38.7-143.8 / 108.11 | 60.0-180.0 / 106.13 | -80.0-70.2 / 1.98 | 5-3,677 / 576.99 | 2.0-1,776.163333 / 281.28 |
| Washington Wizards | 0.0-148.5 / 99.39 | 0.0-200.0 / 111.94 | -200.0-53.3 / -12.55 | 0-2,967 / 411.14 | 0.143333-1,373.69 / 189.71 |
| Brooklyn Nets | 0.0-166.7 / 102.34 | 0.0-175.0 / 107.92 | -115.0-166.7 / -5.58 | 2-2,230 / 400.44 | 1.116667-1,086.308333 / 193.92 |
| **Combined** | 0.0-200.0 / 104.17 | 0.0-200.0 / 108.50 | -200.0-200.0 / -4.32 | 0-3,677 / 451.86 | 0.143333-1,776.163333 / 214.86 |

`NET_RATING - (OFF_RATING - DEF_RATING)` stayed within ±0.1 for every comparable row in all four teams and combined (736/736 comparable rows, 0 unavailable) — consistent with displayed rounding in every team, not just the Warriors.

Sparse-possession rows produce extreme ratings across all four teams (e.g., Washington and Warriors both show `NET_RATING` reaching ±200 at very low possession counts), confirming this is a general pattern, not Warriors-specific. **No minimum-minute or minimum-possession threshold was applied.**

### Exact zero/missing-possession audit

The cache-only replay inspected all 736 Advanced `Lineups` rows and matched Base exposure by the complete canonical observation identity `(season, team ID, unordered canonical player pair)`, never by `GROUP_ID` alone. It found one row with missing or nonpositive possessions, and that row has `POSS = 0`; no row has missing `POSS`.

| Season | Team | Team ID | Canonical pair IDs | GROUP_ID | GROUP_NAME | Base MIN | Advanced MIN | POSS | OFF_RATING | DEF_RATING | NET_RATING | Possession-rate target eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-25 | Washington Wizards | `1610612764` | `1629667`, `203114` | `-203114-1629667-` | K. Middleton - J. McDaniels | 0.143333 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | No |

This is the only zero- or missing-possession row across Golden State (0/183), Boston (0/141), Washington (1/208), and Brooklyn (0/204). The row and every returned endpoint value are retained unchanged for audit. Numeric ratings returned at `POSS <= 0` do not make the row eligible for a possession-based rate target; no value is deleted, imputed, or altered.

For offline replay, load each team's cached Base and Advanced JSON, extract the `Lineups` result set, attach the recorded `2024-25` season and team ID with `attach_pair_context()`, then call `identify_zero_or_missing_possession_rows(advanced_rows, base_rows)`. That path reads only `cache/live_responses/` and performs no endpoint request.

### Reliability-field convention

- Base `MIN` is the shared-minute exposure field because it preserves fractional precision.
- Advanced `POSS` is the possession-exposure field.
- Advanced `MIN` is retained as returned but is not assumed interchangeable with Base `MIN`, particularly at sparse exposure where the observed values round differently.
- `POSS <= 0` or missing `POSS` makes a row ineligible for a possession-based rate target even if the endpoint returns numeric ratings.
- No positive minimum-minute or minimum-possession threshold is selected in Phase 1A.

### Possession distribution (descriptive only; informs a future threshold decision, does not select one)

| Team | Count | Min | P25 | Median | P75 | Max | <10 | <25 | <50 | <100 | <200 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Golden State Warriors | 183 | 1 | 66.5 | 258.0 | 677.0 | 3,046 | 9 | 19 | 41 | 59 | 77 |
| Boston Celtics | 141 | 5 | 55.0 | 148.0 | 830.0 | 3,677 | 3 | 16 | 34 | 56 | 82 |
| Washington Wizards | 208 | 0 | 60.0 | 172.5 | 483.25 | 2,967 | 16 | 30 | 46 | 72 | 112 |
| Brooklyn Nets | 204 | 2 | 79.0 | 245.5 | 572.0 | 2,230 | 13 | 22 | 40 | 57 | 87 |
| **Combined** | 736 | 0 | 64.0 | 212.0 | 590.5 | 3,677 | 41 | 87 | 161 | 244 | 358 |

Across the combined 736 pairs, 41 (5.6%) have fewer than 10 possessions and 244 (33.2%) have fewer than 100 — a substantial low-exposure tail across all four teams, not an isolated Warriors artifact.

## Schema consistency across all four teams

- **Base `Lineups`**: identical 56-column schema and column order across all four teams (`all_identical: True`, no differences).
- **Advanced `Lineups`**: identical 48-column schema and column order across all four teams (`all_identical: True`, no differences).
- **Result-set naming**: `Overall`/`Lineups` identical across all four teams and both measures.
- **Required identity fields** (`GROUP_ID`, `GROUP_NAME`, `MIN`): present and non-null in every team's Base and Advanced response.
- **Datatype/precision difference observed** (not a column-schema mismatch): Advanced `MIN` appears rounded to whole numbers for very small values while Base `MIN` retains fractional precision for the same pairs (see Washington Wizards zero-minute finding above). This is evidence worth further investigation before treating the two measures' `MIN` fields as interchangeable at low exposure.

Schema fingerprints were generated and compared programmatically from the result-set name, ordered column list, and column count. Row count is data volume, not schema identity, and is reported separately. No schema differences required investigation beyond the `MIN`-precision note above.

## Cache, manifest and resumability

- Every successful response has a unique cache filename combining endpoint, team ID, season, and measure type (`team_dash_lineups_{team_id}_{season}_{measure}.json`); Base and Advanced cannot collide, and no two teams can overwrite each other's cache.
- Rerunning the full six-step acquisition plan after this pilot completed used the cache for all six steps and made zero live requests (verified).
- A partially completed manifest resumes correctly: an offline test simulates two of six steps already cached and confirms `first_missing_step` correctly identifies the third (Washington Wizards Base) as the next request.
- Two independent cache-only replays of the complete Phase 1A pipeline (schema fingerprints, combined key validation, prior-player coverage, exposure summaries, and per-team canonical JSON hashes) produced identical results.
- All raw payload and metadata files remain under the existing Git-ignored `research/pair-fit-v2/cache/live_responses/` directory.

## Volume and architecture estimates (rough, unverified; not executed)

Using the four observed teams (uniform on-disk file-size measurement):

| Metric | Min | Mean | Max |
| --- | --- | --- | --- |
| Pair rows per team (Base/Advanced, same count) | 141 | 184.0 | 208 |
| Base payload bytes per team | 136,558 | 177,831 | 200,588 |
| Advanced payload bytes per team | 123,846 | 161,190.75 | 182,140 |

**One 30-team, one-season projection (rough):**
- Pair rows: roughly 4,230-6,240, mean estimate ≈ 5,520
- Raw JSON payload bytes (Base + Advanced): mean estimate ≈ 30 x (177,831 + 161,191) ≈ **10.17 MB**
- Request count: 30 teams x 2 measures = **60 requests** (plus 1 league-wide player-stat request per season)

**Multi-season rough projection (clearly labeled, not a commitment):** if a future historical ingestion covers 5 target seasons (consistent with the `MODELSPEC.md` 2021-22 through 2025-26 discussion) at similar per-season volume, this would suggest roughly 300 requests and roughly 51 MB of raw JSON across seasons — **this assumes constant schemas and volumes across seasons, which is explicitly not verified and may not hold** (season-to-season roster size, trade rate, and NBA API schema changes are all unverified for this projection).

These estimates are intended only to inform a later raw JSON → curated Parquet → DuckDB architecture decision. No Parquet, DuckDB, SQLite, or PostgreSQL implementation occurred in Phase 1A.

## Files changed or created

- `research/pair-fit-v2/src/pair_fit_v2/team_manifest.py` (new): pilot team manifest, acquisition plan, sequential cache-aware/resumable acquisition
- `research/pair-fit-v2/src/pair_fit_v2/multi_team_audit.py` (new): schema fingerprinting/comparison, combined observation-key validation, possession distribution
- `research/pair-fit-v2/src/pair_fit_v2/lineup_audit.py` (updated): cache-only zero/missing-possession diagnostics joined by full canonical observation identity
- `research/pair-fit-v2/tests/test_phase1a_pilot_audit.py` (new): 27 offline tests
- `research/pair-fit-v2/PHASE1A_PILOT_REPORT.md` (new, this file)
- `research/pair-fit-v2/MODELSPEC.md`, `DATA_DICTIONARY.md`, `README.md` (updated)
- `research/pair-fit-v2/FEASIBILITY_REPORT.md` (updated only to align historical hash and row-count semantics)
- Six new Git-ignored cache payload files and six new Git-ignored metadata files under `cache/live_responses/`

## Tests

- Collected: 83
- Passed: 83
- Phase 1A tests: 27 (manifest validation, bounded 6-request plan, sequential order, cache-hit skip, failure-stops-queue, resume-from-first-missing, cache-key uniqueness, schema fingerprinting/comparison including row-count exclusion, combined-key uniqueness, cross-team player/pair reporting, coverage/status/exposure reporting, sparse-possession buckets, zero/missing/positive-possession eligibility, numeric ratings at zero possessions, full-identity Base/Advanced matching, and no-threshold/no-split/no-model guards)

## Phase 1B go/no-go recommendation

**Go, bounded**, for Phase 1B historical architecture and ingestion *design* only:

- Cache-aware acquisition was reliable across all three new teams and reused cache correctly (no unnecessary live requests).
- Base and Advanced schemas are compatible across all four teams (identical column sets and order).
- Canonical pair parsing is valid across all four teams (0 malformed, 0 duplicate pairs anywhere).
- Base-to-Advanced joins are 100% matched, one-to-one, in every team.
- Prior-history coverage is quantified per team and combined, and varies from 57.2% to 81.6% pair-level completeness. This is consistent with the deliberately selected roster profiles, but the four-team sample neither establishes roster type as the cause nor supports a league-wide conclusion.
- Failure handling and resumability are demonstrated offline (mocked failure stops the queue; resume finds the correct next step).
- No unresolved player-identity corruption was found (0 duplicate `PLAYER_ID` values in the reused prior-player table; 3 legitimate cross-team players correctly attributed to two teams each, not merged or duplicated).
- Sparse-target and non-independence risks are explicitly disclosed above (possession tail, overlapping pair rows, no random split performed).

**No-go, still, for model training or full historical expansion.** Even with this Phase 1B design-only recommendation, both remain prohibited until the exposure policy, uniform missing-history treatment, and time-ordered validation design (accounting for documented pair-row overlap and non-independence) are approved by the user.

## Remaining user decisions

1. Whether to proceed with Phase 1B historical architecture/ingestion design (raw JSON → curated Parquet → DuckDB), given the volume estimates above.
2. How the universal no-history fallback should later be evaluated for retained `one_missing` and `both_missing` rows; the uniform status policy and complete-history primary baseline remain in force across teams.
3. What minimum-possession or minimum-minute threshold (if any) should eventually be applied, informed by the descriptive distributions above — not decided in Phase 1A.
4. Which time-ordered or rolling-origin validation design should be approved while preserving 2025-26 as the untouched final test season; a random pair-row split is rejected.
5. Whether any use beyond the adopted convention—Base `MIN` for minute exposure and Advanced `POSS` for possession exposure—needs further reconciliation of Advanced `MIN` rounding behavior.

## Confirmation

No commit, push, production change, or model training occurred during Phase 1A. No Phase 1B work was started beyond this design-input report.
