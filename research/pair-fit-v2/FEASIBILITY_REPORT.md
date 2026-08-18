<!-- \hanson-hoops\research\pair-fit-v2\FEASIBILITY_REPORT.md -->
# Phase 0 feasibility report

## Executive conclusion

`one-team prior-player join feasibility quantified; provisional missing-history baseline policy adopted; multi-team scale remains pending`

Phase 0 progress summary:

1. **Synthetic software-scaffold feasibility**: ✓ Verified (tests pass, pair canonicalization logic works)
2. **Live control-endpoint acquisition**: ✓ Verified (LeagueStandingsV3 2024–25 acquired and cached)
3. **One-team Base pair-lineup acquisition**: ✓ Verified (TeamDashLineups Warriors 2024–25 Base acquired, 183 rows parsed)
4. **Pair structure parsing**: ✓ Verified (GROUP_ID parsing, two-player extraction, canonical deduplication work)
5. **Live Advanced rate-target availability**: ✓ Verified for one Warriors response (directly returned `OFF_RATING`, `DEF_RATING`, `NET_RATING`, `POSS`, `PACE`, `MIN`)
6. **Base-to-Advanced canonical join**: ✓ Verified for one Warriors response (183/183 pairs, one-to-one, no unmatched pairs)
7. **Prior-player response acquisition**: ✓ Verified (one live 2023-24 LeagueDashPlayerStats response, 572 unique player rows, 0 duplicate IDs)
8. **Prior-player join quantification**: ✓ Quantified for one team (player-level 19/23 = 82.6%; pair-level 143/183 = 78.1%)
9. **Missing-history policy**: ✓ Provisional Phase 1 baseline adopted (`complete` / `one_missing` / `both_missing` categorical status; see `MODELSPEC.md`), subject to reevaluation after the multi-team pilot
10. **Multi-team and multi-season feasibility**: ⏳ Unverified (one Warriors smoke test; 30-team scale unknown) — this is the explicit purpose of the recommended Phase 1A pilot

The direct `requests.Session` pattern succeeds where the nba_api wrapper times out. Successful HTTP acquisitions of the Base, Advanced, and prior-player TeamDashLineups/LeagueDashPlayerStats responses were recorded, cached, and replayed. Their canonical JSON hashes verify semantic cache-content integrity relative to the recorded hashes; they do not independently prove source authenticity or byte-for-byte cache-file identity after JSON reserialization. The project is ready for a bounded Phase 1A multi-team ingestion and validation pilot; full Phase 1 modeling and historical expansion remain no-go until that pilot's results are reviewed.

## Data and seasons tested

- Target season: 2024–25 regular season
- Prior feature season: 2023–24
- Final untouched test season: 2025–26 remains reserved
- Research scope: phase 0 smoke test only
- Focus: pair-lineup feasibility, schema validation, and prior-player join coverage

## Endpoint calls attempted

The Phase 0 pipeline is designed to test the following request patterns:

- `LeagueDashLineups(group_quantity=2, measure_type_detailed_defense="Base")`
- `LeagueDashLineups(group_quantity=2, measure_type_detailed_defense="Advanced")`
- `LeagueDashLineups(group_quantity=2, measure_type_detailed_defense="Four Factors")`
- `LeagueDashLineups(group_quantity=2, measure_type_detailed_defense="Usage")`

The research folder keeps the pipeline cache-aware and testable without live NBA calls. The live endpoint schema and reliability were audited via the installed `nba_api` source and the repository's HTTP/session reliability layer.

### Phase 0B bounded live diagnostic (2024–25 season only)

Three live endpoints were tested with minimal parameters to isolate the blocker source:

1. **TeamDashLineups** (single team, minimal load):
   - Parameters: `team_id='1610612744'` (Golden State Warriors), `group_quantity='2'`, `season='2024-25'`, `season_type_all_star='Regular Season'`, `measure_type_detailed_defense='Base'`, `timeout=30`
   - Result: HTTPSConnectionPool read timeout after 30 seconds
   - URL: `/stats/teamdashlineups?...TeamID=1610612744&GroupQuantity=2&Season=2024-25&...`

2. **LeagueDashLineups** (team-filtered to same team):
   - Parameters: `team_id_nullable='1610612744'` (Golden State Warriors), `group_quantity='2'`, `season='2024-25'`, `season_type_all_star='Regular Season'`, `measure_type_detailed_defense='Base'`, `timeout=30`
   - Result: HTTPSConnectionPool read timeout after 30 seconds
   - URL: `/stats/leaguedashlineups?...TeamID=1610612744&GroupQuantity=2&Season=2024-25&...`

3. **LeagueStandingsV3** (lightweight control endpoint):
   - Parameters: `season='2024-25'`, `season_type='Regular Season'`, `timeout=30`
   - Result: HTTPSConnectionPool read timeout after 30 seconds
   - URL: `/stats/leaguestandingsv3?Season=2024-25&SeasonType=Regular+Season&...`

### Historical Phase 0B blocker classification (superseded)

All three requests failed with identical network-layer errors:

```
ConnectionError: HTTPSConnectionPool(host='stats.nba.com', port=443): 
Max retries exceeded with url: ... 
(Caused by ReadTimeoutError("HTTPSConnectionPool(host='stats.nba.com', port=443): 
Read timed out. (read timeout=30)"))
```

At the Phase 0B stage, the matching timeout pattern supported this working inference:

- ✗ NOT a size/complexity issue with league-wide pair-season requests
- ✗ NOT specific to LeagueDashLineups endpoint
- ✗ NOT specific to pair-lineup endpoints generally
- ✓ **Working inference: General `stats.nba.com` access timeout from the current local environment**

The timeout occurred at the network layer (HTTPSConnectionPool read timeout), not during API response parsing or schema validation. At that time, even a single-team, two-player lineup request and a lightweight standings endpoint timed out identically. This inference was superseded by Phases 0C-0E: direct `requests.Session` requests succeeded for the control endpoint and the Warriors Base and Advanced TeamDashLineups responses. The exact configuration-level cause of the nba_api request-path timeouts remains unresolved.

### Phase 0C single-response acquisition diagnostic (2024–25 season only)

**Breakthrough:** A direct `requests.Session` call to `LeagueStandingsV3` succeeded where the nba_api wrapper had previously timed out.

**Successful response acquired:**
- Endpoint: `LeagueStandingsV3` (2024–25 Regular Season)
- Method: Direct `requests.Session.get()` with repository-baseline headers
- Status: HTTP 200
- Latency: 0.75 seconds
- Payload size: 17.6 KB JSON
- Result-set structure: 1 result set with 92 columns, 30 rows (all 30 NBA teams)
- Columns (first 10): `LeagueID`, `SeasonID`, `TeamID`, `TeamCity`, `TeamName`, `TeamSlug`, `Conference`, `ConferenceRecord`, `PlayoffRank`, `ClinchIndicator`
- Content hash: `b44b1f751bba84da` (SHA256, first 16 characters)
- Cache file: `research/pair-fit-v2/cache/live_responses/league_standings_v3_2024-25_regular.json`

**Cache replay verification:**
- Cached response loaded from disk without making a new live request
- Cached ordered columns match the live response; row count also matches as a separate data-volume check
- Canonical JSON hash matches the recorded hash, verifying semantic cache-content integrity rather than source authenticity or byte-for-byte serialized-file identity

**Diagnostic finding:**
- Network layers (DNS, TCP, TLS) are all functioning
- Direct HTTP requests to stats.nba.com succeed and return valid JSON
- The timeouts occurred on the currently configured nba_api request path, while the direct requests.Session path succeeded. The exact configuration-level cause remains unresolved.
- **The nba_api wrapper does not succeed for LeagueStandingsV3 or pair-lineup endpoints from this environment; direct requests do**

### Phase 0D direct pair-lineup acquisition diagnostic (2024–25 season only)

**Successful pair-lineup response acquired:**
- Endpoint: `TeamDashLineups`
- Team: Golden State Warriors (team_id='1610612744')
- Season: 2024–25 Regular Season
- Group quantity: 2 (two-player lineups)
- Measure type: Base
- Method: Direct `requests.Session.get()` with same canonical headers as Phase 0C
- Status: HTTP 200
- Latency: 2.14 seconds
- Payload size: 58.7 KB JSON
- Result-set structure: 2 result sets
  - Overall: 57 columns, 1 row
  - Lineups: 56 columns, 183 rows
- Content hash: `71e194d4338e09b0` (SHA256, first 16 characters)
- Cache files:
  - `team_dash_lineups_1610612744_2024-25_base.json` (52.4 KB)
  - `team_dash_lineups_1610612744_2024-25_base_metadata.json`

**Lineups result set columns (56 total):**
- Pair identity: `GROUP_SET`, `GROUP_ID` (format: `-PLAYER_ID_1-PLAYER_ID_2-`), `GROUP_NAME` (e.g., "S. Curry - D. Green")
- Performance: `GP`, `W`, `L`, `W_PCT`, `MIN`, `FGM`, `FGA`, `FG_PCT`, `FG3M`, `FG3A`, `FG3_PCT`, `FTM`, `FTA`, `FT_PCT`
- Rebounding: `OREB`, `DREB`, `REB`
- Playmaking: `AST`, `TOV`
- Defense: `STL`, `BLK`, `BLKA`, `PF`, `PFD`
- Scoring: `PTS`
- **Target efficiency**: `PLUS_MINUS` (cumulative on-court point differential)
- Ranking: 22 columns of `_RANK` fields
- Additional: `SUM_TIME_PLAYED`

**Critical finding: Base measure provides cumulative differential, not rate-based efficiency**
- ORTG / DRTG / NET_RTG: Not returned under these legacy names
- POSS (Possessions): Not returned in Base
- Available: `PLUS_MINUS` (cumulative on-court team point differential during pair's shared minutes)
  - Example: Curry–Green recorded +239 over 1419.1 minutes
  - This is a cumulative total, not a per-100-possession rate
  - Embeds playing-time opportunity in the outcome
  - Not suitable as-is for rate-based modeling without normalization
- **Phase 0E outcome**: Advanced directly returned `OFF_RATING`, `DEF_RATING`, `NET_RATING` and `POSS` for the same pair population

**Pair data validation (Warriors Base response):**
- Total rows: 183
- Valid pairs (two distinct players, GP > 0, MIN > 0): 183
- Zero-minute pairs: 0
- Zero-game pairs: 0
- Malformed pair identifiers: 0
- Duplicate canonical pairs after unordered deduplication: 0
- **Data quality observation**: No structural failures detected among the 183 rows in this one Warriors Base response under the current validation checks. This smoke-test result does not establish league-wide data quality, minimum-sample reliability for modeling, target validity, or cross-measure compatibility.

**Sample valid pairs (Warriors 2024–25):**
1. Curry-Green: 60 games, 1419.1 minutes, +239 cumulative plus-minus
2. Curry-Hield: 70 games, 968.5 minutes, +224 cumulative plus-minus
3. Green-Podziemski: 51 games, 902.2 minutes, +93 cumulative plus-minus
4. Green-Moody: 56 games, 893.4 minutes, +185 cumulative plus-minus
5. Curry-Wiggins: 37 games, 883.4 minutes, +10 cumulative plus-minus

**Cache replay verification:**
- Cached response loaded from disk without making a new live request
- Cached ordered columns match the live response; row count also matches as a separate data-volume check
- Canonical JSON hash matches the recorded hash, verifying semantic cache-content integrity rather than source authenticity or byte-for-byte serialized-file identity

**Implementation artifact: direct_fetch.py**
- Created reusable research-only module `src/pair_fit_v2/direct_fetch.py`
- Exports: `create_research_session()`, `fetch_team_dash_lineups()`, `fetch_league_dash_lineups()`, `cache_response()`, `load_cached_response()`
- Canonical headers: Mozilla/5.0 user-agent, nba.com referer, gzip/deflate encoding
- Timeout: Explicit 30 seconds, no unbounded retries
- Serves as baseline for Phase 0E and Phase 1 acquisition

### Phase 0E bounded Advanced rate-target audit (2024-25 season only)

**Single successful request:**
- Endpoint: `TeamDashLineups`
- Team: Golden State Warriors (`1610612744`)
- Season/type: 2024-25 Regular Season
- Group quantity / measure: `2` / `Advanced`
- Transport: direct `requests.Session`; explicit 30-second timeout; no retry or proxy
- Result: HTTP 200 valid JSON in 2.626 seconds
- Payload size: 160,343 bytes
- Content hash: `58b62bbde00ba68a` (first 16 characters of canonical SHA-256)
- Cache: `team_dash_lineups_1610612744_2024-25_advanced.json`, with ignored metadata alongside it

**Actual result sets and complete schemas:**
- `Overall`: 49 columns, 1 row: `GROUP_SET`, `GROUP_VALUE`, `TEAM_ID`, `TEAM_ABBREVIATION`, `TEAM_NAME`, `GP`, `W`, `L`, `W_PCT`, `MIN`, `E_OFF_RATING`, `OFF_RATING`, `E_DEF_RATING`, `DEF_RATING`, `E_NET_RATING`, `NET_RATING`, `AST_PCT`, `AST_TO`, `AST_RATIO`, `OREB_PCT`, `DREB_PCT`, `REB_PCT`, `TM_TOV_PCT`, `EFG_PCT`, `TS_PCT`, `E_PACE`, `PACE`, `PACE_PER40`, `POSS`, `PIE`, `GP_RANK`, `W_RANK`, `L_RANK`, `W_PCT_RANK`, `MIN_RANK`, `OFF_RATING_RANK`, `DEF_RATING_RANK`, `NET_RATING_RANK`, `AST_PCT_RANK`, `AST_TO_RANK`, `AST_RATIO_RANK`, `OREB_PCT_RANK`, `DREB_PCT_RANK`, `REB_PCT_RANK`, `TM_TOV_PCT_RANK`, `EFG_PCT_RANK`, `TS_PCT_RANK`, `PACE_RANK`, `PIE_RANK`
- `Lineups`: 48 columns, 183 rows: `GROUP_SET`, `GROUP_ID`, `GROUP_NAME`, `GP`, `W`, `L`, `W_PCT`, `MIN`, `E_OFF_RATING`, `OFF_RATING`, `E_DEF_RATING`, `DEF_RATING`, `E_NET_RATING`, `NET_RATING`, `AST_PCT`, `AST_TO`, `AST_RATIO`, `OREB_PCT`, `DREB_PCT`, `REB_PCT`, `TM_TOV_PCT`, `EFG_PCT`, `TS_PCT`, `E_PACE`, `PACE`, `PACE_PER40`, `POSS`, `PIE`, `GP_RANK`, `W_RANK`, `L_RANK`, `W_PCT_RANK`, `MIN_RANK`, `OFF_RATING_RANK`, `DEF_RATING_RANK`, `NET_RATING_RANK`, `AST_PCT_RANK`, `AST_TO_RANK`, `AST_RATIO_RANK`, `OREB_PCT_RANK`, `DREB_PCT_RANK`, `REB_PCT_RANK`, `TM_TOV_PCT_RANK`, `EFG_PCT_RANK`, `TS_PCT_RANK`, `PACE_RANK`, `PIE_RANK`, `SUM_TIME_PLAYED`

The pair result set was identified by observed `GROUP_ID` values in the validated `-PLAYER_ID_1-PLAYER_ID_2-` form, not solely by position.

**Observed candidate fields:**
- Direct rate fields: `OFF_RATING`, `DEF_RATING`, `NET_RATING`
- Separately reported estimated fields: `E_OFF_RATING`, `E_DEF_RATING`, `E_NET_RATING`
- Reliability/sample-size fields: `POSS`, `MIN`; context rate: `PACE`
- None of those fields was missing or nonnumeric across the 183 pair rows. There were no zero or missing possessions, zero-minute rows or zero-game rows.

**Pair and join validation:**
- Advanced raw pair rows / exactly-two-ID rows / unique canonical pairs: 183 / 183 / 183
- Same-player or malformed identifiers / duplicate canonical pairs: 0 / 0
- Base unique pairs / Advanced unique pairs / matched pairs: 183 / 183 / 183
- Base-only / Advanced-only: 0 / 0
- Base and Advanced match rates: 100.0% / 100.0%
- Duplicate join-key violations: 0 on Base and 0 on Advanced; the join is one-to-one using season, team ID and canonical unordered player IDs

**Target checks (no minimum-sample filter applied):**
- `OFF_RATING`: range 0.0 to 200.0, mean 108.62; one zero
- `DEF_RATING`: range 0.0 to 142.9, mean 107.04; two zeros
- `NET_RATING`: range -83.3 to 200.0, mean 1.58; four zeros
- `POSS`: range 1 to 3,046, mean 459.04; no zero, missing or negative values
- `MIN`: range 1 to 1,419, mean 215.62; no zero, missing or negative values
- The zero and extreme rating values occur in the returned raw data at sparse exposure; this audit records them as sample-size concerns rather than silently filtering them or declaring them invalid.
- `NET_RATING - (OFF_RATING - DEF_RATING)` ranges from -0.1 to +0.1 across all 183 comparable rows. The equivalent estimated-field difference has the same range. Both are consistent with displayed rounding.

`NET_RATING` is therefore a **provisional primary rate target** for later feasibility work. This finding does not establish target stability at low possessions, predictive validity, or any model result. Base `PLUS_MINUS` remains a cumulative on-court team point differential; it is not net rating, an on/off statistic or a per-100-possession target.

**Cache replay:** Two complete cache-only runs produced identical Advanced hash, schemas, row counts, pair keys, missingness and target summaries, and Base-to-Advanced join summary. No additional live request was made.

### Phase 0F bounded prior-player join audit (2023-24 prior season only)

**Single successful request:**
- Endpoint: `LeagueDashPlayerStats`
- Season/type: 2023-24 Regular Season
- Measure / per mode / league: `Base` / `Per100Possessions` / `00` (NBA)
- Transport: direct `requests.Session`; explicit 30-second timeout; no retry or proxy
- Result: HTTP 200 valid JSON in 1.831 seconds
- Payload size: 643,961 bytes
- Content hash: `46103a3e96e524f8` (first 16 characters of canonical SHA-256)
- Cache: `league_dash_player_stats_2023-24_base_per100possessions.json`, with ignored metadata alongside it
- Normalized parameters were constructed from the installed `nba_api` `LeagueDashPlayerStats.__init__` parameter dict; all otherwise-unspecified nullable fields defaulted to an empty string.

**Actual result set and complete schema:**
- One result set, `LeagueDashPlayerStats`: 67 columns, 572 rows
- Identity fields confirmed present and usable: `PLAYER_ID`, `PLAYER_NAME`, `TEAM_ID`, `TEAM_ABBREVIATION`, `AGE`, `GP`, `MIN`
- All other non-ranking Base fields observed: `NICKNAME`, `W`, `L`, `W_PCT`, `FGM`, `FGA`, `FG_PCT`, `FG3M`, `FG3A`, `FG3_PCT`, `FTM`, `FTA`, `FT_PCT`, `OREB`, `DREB`, `REB`, `AST`, `TOV`, `STL`, `BLK`, `BLKA`, `PF`, `PFD`, `PTS`, `PLUS_MINUS`, `NBA_FANTASY_PTS`, `DD2`, `TD3`, `WNBA_FANTASY_PTS`, `TEAM_COUNT`; plus 29 `_RANK` columns.
- This single Base response is not treated as the final model feature set.

**Observed `MIN` semantics under `Per100Possessions` (explicitly inspected, not assumed):**
- Top players by games played show `MIN` values around 46-48, not season-total minutes (which would be in the thousands). This confirms `MIN` here is reported on the same per-100-possession normalization as the rate fields, and only coincidentally resembles per-game averages at typical NBA pace.
- This field must not be used as the prior player's season-total eligibility or reliability measure. A later ingestion phase will need a validated `Totals`-per-mode response, or another trustworthy season-total-minutes field, before minutes-based eligibility or reliability weighting can be built. Phase 0F establishes join coverage only; it does not establish the final prior-player reliability contract.

**Stable-ID and traded-player audit:**
- Raw player rows: 572; non-null `PLAYER_ID`: 572; unique `PLAYER_ID`: 572; duplicate `PLAYER_ID` rows: 0; missing/malformed `PLAYER_ID`: 0
- No duplicate player names resolving to different IDs were found in this response
- 78 of 572 rows have `TEAM_COUNT > 1` (players who changed teams during the season). Each such player still has exactly one row: the endpoint appears to return one aggregate record per player rather than one row per team stint, and `TEAM_ABBREVIATION` reflects only one (most recent) team context.
- One row (Buddy Hield, `TEAM_COUNT=2`) shows `GP=84`. This is a **valid** value, not an anomaly: a player traded mid-season can appear in more combined games than either single team's 82-game schedule, because the two teams may have played a different number of games as of the trade date. `GP > 82` is not, by itself, a validation failure for player-season data, and this value supports (rather than undermines) the finding that the endpoint returns one aggregate traded-player row. It is not capped, corrected, or rejected.
- No duplicate IDs were resolved by keeping first/last rows, averaging, summing, or team selection; none were required, since no duplicate `PLAYER_ID` values were found.

**Prior-player join construction:**
- Joined the cached Warriors 2024-25 Advanced pair table (183 canonical pairs) to the 2023-24 player table twice per pair, once per player, using stable `PLAYER_ID` only. No name-based fallback was used.
- Each joined row carries an explicit `feature_season = "2023-24"` and `target_season = "2024-25"`. No 2024-25 individual player statistics were read or used as features.
- Pair shared minutes/possessions/ratings/cumulative `PLUS_MINUS` were preserved only as diagnostic exposure fields, not as prior-player input features.

**Player-level coverage (23 unique Warriors pair-population player IDs):**
- With a 2023-24 record: 19 (82.6%)
- Without a 2023-24 record: 4 (17.4%) — described only as "no 2023-24 LeagueDashPlayerStats record": `1641736` (R. Beekman), `1641879` (Y. Collins), `1642050` (J. Rowe), `1642366` (Q. Post). No rookie, inactive-player, or ID-error label is applied without further evidence.

**Pair-level coverage (183 canonical pairs):**
- Both players matched: 143 (78.1%)
- Only player 1 matched: 29 (15.8%); only player 2 matched: 8 (4.4%); neither matched: 3 (1.6%)
- One-or-more-missing pair rate: 21.9%
- Missing coverage is concentrated in the same 4 players: `1642366` appears in 19 incomplete pairs, `1642050` in 14, `1641879` in 5, `1641736` in 5 — a small number of players account for all incomplete pairs.

**Exposure-weighted diagnostic coverage (2024-25 target-period weights, descriptive only):**
- Shared minutes: complete-prior pairs sum to 36,469.0 minutes; incomplete-prior pairs sum to 2,989.0 minutes; total pair-row shared-minute sum is 39,458.0. Complete share: 92.4% (36,469.0 / 39,458.0); incomplete share: 7.6% (2,989.0 / 39,458.0).
- Possessions: complete-prior pairs sum to 77,640 possessions; incomplete-prior pairs sum to 6,365 possessions; total pair-row possession sum is 84,005. Complete share: 92.4% (77,640 / 84,005); incomplete share: 7.6% (6,365 / 84,005).
- These are overlapping, per-player-row sums recalculated directly from the cached pair table, not estimates of unique team minutes or possessions, and are not used as predictive features. They only describe how missing prior history is distributed across the pair observations.

**Prior-feature missingness for the 19 matched players:**
- No missing values were found for `PLAYER_ID`, `PLAYER_NAME`, `TEAM_ID`, `TEAM_ABBREVIATION`, `AGE`, `GP`, `MIN`, `FG_PCT`, or `TEAM_COUNT`.
- 3 matched players show `FG3_PCT = 0.0` and 1 shows `FT_PCT = 0.0`; these are valid zero observations (no makes/attempts on record), not missing values.
- No values were imputed and no players were removed.

**Missing-history policy families considered, and the adopted provisional baseline:**
1. **Complete-case modeling**: exclude the 40 pairs (21.9%) lacking either prior-player record, retaining 143 pairs, 36,469.0 of 39,458.0 summed shared minutes (92.4%), and 77,640 of 84,005 summed possessions (92.4%).
2. **Explicit missing-history treatment**: retain all 183 pairs with an explicit missingness or no-prior-history indicator for the 4 affected players, preserving the 2,989.0 minutes and 6,365 possessions (7.6% of each) otherwise dropped.
3. **Separate model or baseline for no-history players**: model the 143 complete-prior pairs with the primary approach and treat the 40 pairs involving the 4 missing-history players as a distinct, separately evaluated baseline.

**Adopted provisional Phase 1 baseline policy** (combines elements of 1 and 2, defers 3): preserve all 183 pairs in raw and curated datasets; add a categorical `prior_history_status` of `complete` / `one_missing` / `both_missing`; use the 143 `complete` pairs for the primary baseline model; never zero-impute missing prior statistics; retain the 40 `one_missing`/`both_missing` pairs for coverage analysis and a possible later no-history fallback (not yet defined or implemented). This policy is provisional and subject to reevaluation after the Phase 1A multi-team pilot.

**Cache replay:** Two complete cache-only runs (player-stat parsing, stable-ID audit, join, player/pair/exposure coverage, and feature missingness) produced identical results, including the `46103a3e96e524f8` content hash. No additional live request was made.

### Request-path classification: narrowed

Previous (Phase 0B/0C): "stats.nba.com access is blocked"

Current (Phase 0D): "The currently configured nba_api request path times out, while the direct requests.Session path succeeds."

**Wrapper observation (unresolved root cause):**
The nba_api wrapper with default configuration does not complete pair-lineup requests from this environment, while an equivalent direct requests.Session request completes in 2.14 seconds. Possible contributing factors:
- Wrapper's retry/exponential-backoff logic
- Session object or HTTP adapter configuration
- Header propagation or request construction through wrapper layers
- Timeout handling in wrapper vs. direct requests
- Environment-specific proxy or firewall interaction

Without repeated live testing, the exact root cause remains unresolved.

**Implementation approach:**
The direct `requests.Session` pattern is proven to work for pair-lineup acquisition. It will be the acquisition method for pair-fit v2 Phase 1 and forward. Historical wrapper compatibility investigation is a separate, non-blocking task.

## Data-access blocker vs. synthetic/request-wrapper vs. model infeasibility

**Three distinct questions:**

1. **Can the software rules operate on synthetic inputs?**
   - ✓ **Yes.** The synthetic Phase 0 scaffold and local schema validation tests pass cleanly. Pair canonicalization, row validation logic, and join coverage logic work correctly.

2. **Can an environment acquire and parse real data?**
   - ✓ **Yes, with caveats.** Direct `requests.Session` calls to stats.nba.com succeed and return valid JSON (demonstrated in Phase 0C with LeagueStandingsV3). The nba_api wrapper does not succeed from this environment.
   - **Implication:** The data-access blocker is narrower than initially believed. It is not that stats.nba.com is unreachable; it is that the nba_api wrapper's request construction, headers, retry logic, or timeout handling does not work in this environment.
   - **Corollary:** `TeamDashLineups` direct requests have since been verified for one Warriors Base response and one Warriors Advanced response. Other teams, seasons and pair-lineup endpoints remain untested.

3. **Can the resulting data support a predictively useful model?**
   - **Unresolved.** Phase 0C acquires one control endpoint response; it does not yet establish pair-lineup data availability or sufficiency. Model feasibility is a separate question deferred to Phase 1.

**Current status:**
- Environment-specific request-wrapper incompatibility is narrower and more addressable than a general network access blocker.
- Data acquisition from stats.nba.com is feasible via direct HTTP requests from this environment.
- One-team pair-lineup data acquisition and the Base-to-Advanced join are verified through direct requests; multi-team expansion remains a separate diagnostic step.
- Model feasibility is unresolved and will be addressed only after data ingestion is confirmed to work.

**Distinction from old phrasing:**
- Old (Phase 0B): "data-access blocker" implied stats.nba.com is unreachable.
- Corrected (Phase 0C): "request-wrapper incompatibility" is more precise; the issue is that the nba_api wrapper does not succeed, not that the upstream service is unavailable.
- "Synthetic software-scaffold feasibility" (not "model feasibility") is established; the model-level question is deferred.

## Actual schemas observed and source evidence (Phase 0C-0D)

### Phase 0C live schema: LeagueStandingsV3 2024–25

The Phase 0C control request acquired an authentic live response from stats.nba.com.

**LeagueStandingsV3 response structure:**
- HTTP 200 status
- Content-Type: `application/json; charset=utf-8`
- Top-level structure: `{"resultSets": [...]}`
- Result set 0:
  - Name: "Standings"
  - Headers: 92 columns
  - Rows: 30 (one per NBA team in 2024–25 season)

### Phase 0D live schema: TeamDashLineups Warriors 2024–25 Base

The Phase 0D primary request acquired an authentic live response for one team and measure type.

**TeamDashLineups response structure:**
- HTTP 200 status
- Content-Type: `application/json; charset=utf-8`
- Top-level structure: `{"resultSets": [...]}`
- Result set 0 (Overall): 57 columns, 1 row (team-level summary)
- Result set 1 (Lineups): 56 columns, 183 rows (two-player lineup records)

**Lineups result set columns (Base measure):**
1. Pair identity: GROUP_SET, GROUP_ID, GROUP_NAME
2. Performance metrics: GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
3. Rebounding: OREB, DREB, REB
4. Playmaking: AST, TOV
5. Defense: STL, BLK, BLKA, PF, PFD
6. Scoring: PTS
7. On-court differential: PLUS_MINUS (cumulative, not rate)
8. Rankings: 22 columns with _RANK suffix
9. Time tracked: SUM_TIME_PLAYED

**Key schemas not present in Base measure:**
- OFF_RATING (offensive efficiency rate)
- DEF_RATING (defensive efficiency rate)
- NET_RATING (net efficiency rate)
- POSS (possessions)
- Advanced and Four Factors measures require separate requests

### Phase 0E live schema: TeamDashLineups Warriors 2024-25 Advanced

The Advanced response is described in full in the Phase 0E section above. Its `Lineups` set has 48 columns and 183 rows, and directly contains `OFF_RATING`, `DEF_RATING`, `NET_RATING`, their separately named estimated counterparts, `POSS`, `PACE` and `MIN`.

### Reconciled target field assessment

**Observed in Base measure:**
- `PLUS_MINUS`: Cumulative on-court team point differential during the pair's shared minutes
  - Example: Curry–Green pair, 60 games, 1419.1 minutes, PLUS_MINUS = +239
  - Interpretation: Total points scored minus points allowed while this pair was on court
  - Statistical nature: Cumulative total, confounded with playing time
  - Modeling suitability: Requires normalization for rate-based analysis

**Not observed in Base measure (observed in Phase 0E Advanced):**
- `OFF_RATING`: Points per 100 possessions scored
- `DEF_RATING`: Points per 100 possessions allowed
- `NET_RATING`: Offensive rating minus defensive rating
- Possessions data

**Conclusion on targets:**
One-team rate-target availability and Base-to-Advanced compatibility are verified. Multi-team target stability and model suitability remain pending.

## Row counts after each processing step

These are bounded one-team Warriors 2024-25 smoke-test results, not league-wide findings:

- Base raw pair rows: 183
- Base valid canonical pairs: 183
- Advanced raw pair rows: 183
- Advanced valid canonical pairs: 183
- Base-to-Advanced matched pairs: 183
- Base-only pairs: 0
- Advanced-only pairs: 0
- Duplicate canonical keys: 0 in Base and 0 in Advanced
- Prior-player unique IDs with / without 2023-24 record: 19 / 4 (82.6% player-level coverage)
- Prior-player pair-level complete coverage: 143 / 183 (78.1%)

No minimum-possession threshold was applied. Possessions range from 1 to 3,046; extreme ratings among sparse rows demonstrate why a later eligibility or reliability policy will be necessary. These observations do not establish league-wide data quality, multi-team consistency, or predictive feasibility.

## Duplicate and missingness findings

The most likely failure modes for pair data are:

- duplicate rows caused by the same canonical pair appearing multiple times
- malformed `GROUP_ID` / `GROUP_NAME` records
- zero-minute or zero-game rows
- rows missing `OFF_RATING`, `DEF_RATING`, or `NET_RATING`
- missing prior player record for one or both players

The research scaffold explicitly tests for these conditions and records them as validation failures rather than silently coercing them into usable rows.

## Prior-feature join coverage

Prior-player feature coverage is a critical feasibility check. The join is by stable `PLAYER_ID`, not by name.

Phase 0F quantified this for one team (Warriors, 2024-25 pairs joined to 2023-24 `LeagueDashPlayerStats`):

- Player-level: 19/23 unique player IDs matched (82.6%); 4 unmatched, each described only as "no 2023-24 LeagueDashPlayerStats record"
- Pair-level: 143/183 pairs with both players matched (78.1%); missing coverage concentrated in the same 4 players
- Exposure-weighted: complete-prior pairs sum to 36,469.0 of 39,458.0 shared minutes (92.4%) and 77,640 of 84,005 possessions (92.4%); this is descriptive only, not a feature

The expected coverage issues, observed in this one-team smoke test, include players without 2023-24 record. No player was labeled a rookie, inactive player, or ID error without direct supporting evidence. Trades were observed via `TEAM_COUNT`; the endpoint returned one aggregate row per traded player rather than ambiguous multiple rows.

The Phase 0 summary logic reports:

- `pair_rows`
- `complete_prior_rows`
- `missing_prior_rows`
- `complete_prior_rate`

This is the right metric for deciding whether the pair-table can be joined to prior player feature tables before historical expansion. One-team feasibility is now quantified; multi-team consistency remains unverified.

## Shared-minutes distribution and possessions

The Phase 0 contract treats shared minutes and possessions as reliability and sample-size information rather than as player-quality features.

The essential validity checks are:

- minimum shared-minute threshold
- duplicate or zero-minute row removal
- possession availability check
- explicit callout if possessions are absent and an estimate is not defensibly supported

If possessions are absent, the recommendation is to avoid a silent deduction and instead document the blocker or a clearly provisional derivation only after source validation.

## Target availability

The target should be evaluated using shared-court team efficiency measures that are reliably returned for the pair/lineup operating window. The one-team observed targets are:

- `OFF_RATING`
- `DEF_RATING`
- `NET_RATING` = `OFF_RATING` - `DEF_RATING`, subject to displayed rounding

Later work must confirm they remain directly returned and comparable across teams and seasons.

## API reliability and reproducibility

The repository already contains a safe, environment-aware reliability pattern in [backend/app/services/nba_http.py](backend/app/services/nba_http.py), including:

- managed requests session
- timeout configuration
- retry policy for transient NBA failures
- proxy redaction and environment controls
- structured upstream exception handling

The research pipeline should reuse those patterns for outbound calls where appropriate, while keeping the experiment isolated from production app behavior.

## Leakage and validity risks

The highest-risk issues are:

- using target-season full-player stats as prior features
- treating a pair’s own target-season shared minutes as direct player quality
- failing to canonicalize pair identity
- joining on names instead of stable IDs
- mixing seasons incorrectly
- using same-season features or overlapping windows across the pair and target period

The Phase 0 acceptance standard is straightforward: no final data product should be accepted until the preceding checks are documented and enforced.

## Ambiguous fields and decisions still open

The following are explicitly provisional or unresolved:

- exact final feature list
- usage inclusion criteria
- whether to exclude rookies at the outset
- how to aggregate traded-player histories
- whether possession derivation is allowed without source validation
- pair-level team context standardization

## Recommended steps before full Phase 1 modeling

Before proceeding to full Phase 1 historical ingestion and model work, the project should complete:

1. **Missing-history policy (adopted, provisional)**
   - A provisional Phase 1 baseline policy has been adopted: preserve all pair observations, add a `complete`/`one_missing`/`both_missing` status, model on `complete` pairs, never zero-impute, retain other statuses for coverage analysis and a not-yet-defined no-history fallback
   - Based on the observed 78.1% pair-level and 92.4% exposure-weighted (both minutes and possessions) complete-prior coverage from Phase 0F
   - Subject to reevaluation after the Phase 1A multi-team pilot below

2. **Phase 1A: bounded multi-team ingestion and validation pilot**
   - Acquire Base and Advanced pair-lineup data for 2–3 additional teams
   - Verify response structure consistency and data quality across teams
   - Re-run the prior-player join and coverage audit across those teams
   - Test whether schemas, pair joins, prior coverage and missing-history patterns generalize beyond the Warriors
   - Estimate total historical data volume for 30-team, multi-season ingestion

3. **Data pipeline and schema validation**
   - Lock the canonical pair-identity rule
   - Document data-quality filters and validation checks
   - Establish caching and immutability guardrails
   - Confirm the observed `Per100Possessions` `MIN` semantics before any feature or reliability use; a `Totals`-per-mode (or equivalent season-total-minutes) response is required for that purpose

## Phase 1A pilot vs. full Phase 1 modeling: go/no-go

**Phase 1A bounded multi-team pilot: GO.** Its explicit purpose is to obtain the multi-team evidence not yet available; that evidence is not a precondition for starting the pilot. Phase 1A is scoped to schema/join/coverage validation across a small number of additional teams, not model training or full historical ingestion.

**Full Phase 1 modeling and historical expansion: NO-GO** until all of the following are demonstrated:

- Pair identity parsing and canonicalization are reliable and tested
- Base measure data structures are consistent across multiple teams and seasons
- Prior-player feature records are available and joinable with stable IDs across multiple teams, not just one Warriors smoke test
- The adopted missing-history policy has been reevaluated against Phase 1A multi-team results
- Rate-target fields are confirmed across multiple teams and seasons, including sparse-sample behavior
- No same-season leakage is present in the feature pipeline
- Cache layer and schema-validation tests pass without live network dependence
- The feasibility report documents remaining gaps, data-quality limitations and untested assumptions

If these checks are not satisfied after Phase 1A, the project should remain in bounded-pilot diagnostics until the blockers are resolved.

If rate-target consistency cannot be established across teams and seasons, the project may explore alternative approaches (cumulative-differential modeling, semi-supervised learning on rank fields, or outcome-only studies) but should document these departures explicitly.

## Final note

Phase 0 research has established that the pair-fit v2 software-scaffold can be built, that live pair-lineup data is acquirable from stats.nba.com via direct HTTP requests, and that pair structure (identity, deduplication, validation) works correctly on observed Warriors data.

Phase 0 has **not yet** established:
- Multi-team and multi-season data consistency, including prior-player join consistency and adopted-policy validity beyond one team
- Predictive model feasibility

This report does not claim that rate-based efficiency targets are stable outside one Warriors response, that the 78.1% one-team pair-level prior-player coverage generalizes league-wide, or that a predictive model will succeed. Those questions require the bounded Phase 1A multi-team pilot and later modeling work. The missing-history policy adopted here is provisional and subject to reevaluation once Phase 1A results are available.
