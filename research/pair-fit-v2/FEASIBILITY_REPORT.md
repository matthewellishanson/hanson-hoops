# Phase 0 feasibility report

## Executive conclusion

`live Base pair-lineup acquisition verified; rate-target and prior-player join feasibility remain pending`

Phase 0 progress summary:

1. **Synthetic software-scaffold feasibility**: ✓ Verified (tests pass, pair canonicalization logic works)
2. **Live control-endpoint acquisition**: ✓ Verified (LeagueStandingsV3 2024–25 acquired and cached)
3. **One-team Base pair-lineup acquisition**: ✓ Verified (TeamDashLineups Warriors 2024–25 Base acquired, 183 rows parsed)
4. **Pair structure parsing**: ✓ Verified (GROUP_ID parsing, two-player extraction, canonical deduplication work)
5. **Rate-target availability**: ⏳ Pending (PLUS_MINUS is cumulative differential, not a rate; Advanced measure required)
6. **Prior-player join feasibility**: ⏳ Pending (no prior-season stats acquired or joined yet)
7. **Multi-team and multi-season feasibility**: ⏳ Unverified (one Warriors smoke test; 30-team scale unknown)

The direct `requests.Session` pattern succeeds where the nba_api wrapper times out. One authentic TeamDashLineups response has been cached and replayed. The project requires Phase 0E (prior-player join audit) and Advanced measure validation before Phase 1 modeling work can begin.

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

### Blocker classification

All three requests failed with identical network-layer errors:

```
ConnectionError: HTTPSConnectionPool(host='stats.nba.com', port=443): 
Max retries exceeded with url: ... 
(Caused by ReadTimeoutError("HTTPSConnectionPool(host='stats.nba.com', port=443): 
Read timed out. (read timeout=30)"))
```

This confirms:

- ✗ NOT a size/complexity issue with league-wide pair-season requests
- ✗ NOT specific to LeagueDashLineups endpoint
- ✗ NOT specific to pair-lineup endpoints generally
- ✓ **Blocker source: General `stats.nba.com` access timeout from current local environment**

The timeout occurred at the network layer (HTTPSConnectionPool read timeout), not during API response parsing or schema validation. Even a single-team, two-player lineup request and a lightweight standings endpoint both timed out identically, indicating upstream network access failure rather than endpoint-specific issues.

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
- Cached schema (columns and row count) is identical to live response
- Content hash matches: response is authentic and not corrupted

**Diagnostic finding:**
- Network layers (DNS, TCP, TLS) are all functioning
- Direct HTTP requests to stats.nba.com succeed and return valid JSON
- The earlier timeouts in Phase 0B were caused by the nba_api wrapper's request construction or retry logic, not by the environment or network
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
- ORTG: Not returned (would require Advanced measure)
- DRTG: Not returned (would require Advanced measure)
- NET_RTG: Not returned (would require Advanced measure)
- POSS (Possessions): Not returned (would require Advanced measure)
- Available: `PLUS_MINUS` (cumulative on-court team point differential during pair's shared minutes)
  - Example: Curry–Green recorded +239 over 1419.1 minutes
  - This is a cumulative total, not a per-100-possession rate
  - Embeds playing-time opportunity in the outcome
  - Not suitable as-is for rate-based modeling without normalization
- **Rate-target validation**: Requires Advanced measure fetch (OFF_RATING, DEF_RATING, NET_RATING)

**Pair data validation (Warriors Base response):**
- Total rows: 183
- Valid pairs (two distinct players, GP > 0, MIN > 0): 183
- Zero-minute pairs: 0
- Zero-game pairs: 0
- Malformed pair identifiers: 0
- Duplicate canonical pairs after unordered deduplication: 0
- **Data quality observation**: No structural failures detected among the 183 rows in this one Warriors Base response under the current validation checks. This smoke-test result does not establish league-wide data quality, minimum-sample reliability for modeling, target validity, or cross-measure compatibility.

**Sample valid pairs (Warriors 2024–25):**
1. Curry-Green: 60 games, 1419.1 minutes, +239 net
2. Curry-Hield: 70 games, 968.5 minutes, +224 net
3. Green-Podziemski: 51 games, 902.2 minutes, +93 net
4. Green-Moody: 56 games, 893.1 minutes, +185 net
5. Curry-Wiggins: 37 games, 883.4 minutes, +10 net

**Cache replay verification:**
- Cached response loaded from disk without making a new live request
- Cached schema (columns and row count) is identical to live response
- Content hash matches: response is authentic and not corrupted

**Implementation artifact: direct_fetch.py**
- Created reusable research-only module `src/pair_fit_v2/direct_fetch.py`
- Exports: `create_research_session()`, `fetch_team_dash_lineups()`, `fetch_league_dash_lineups()`, `cache_response()`, `load_cached_response()`
- Canonical headers: Mozilla/5.0 user-agent, nba.com referer, gzip/deflate encoding
- Timeout: Explicit 30 seconds, no unbounded retries
- Serves as baseline for Phase 0E and Phase 1 acquisition

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
   - **Corollary:** Pair-lineup data endpoints (TeamDashLineups, LeagueDashLineups) have not yet been tested with direct requests. They were tested only via nba_api wrapper and timed out. Whether those endpoints are accessible via direct requests remains unknown.

3. **Can the resulting data support a predictively useful model?**
   - **Unresolved.** Phase 0C acquires one control endpoint response; it does not yet establish pair-lineup data availability or sufficiency. Model feasibility is a separate question deferred to Phase 1.

**Current status:**
- Environment-specific request-wrapper incompatibility is narrower and more addressable than a general network access blocker.
- Data acquisition from stats.nba.com is feasible via direct HTTP requests from this environment.
- Pair-lineup data acquisition via direct requests remains untested and is the next diagnostic step.
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

### Reconciled target field assessment

**Observed in Base measure:**
- `PLUS_MINUS`: Cumulative on-court vs off-court point differential
  - Example: Curry–Green pair, 60 games, 1419.1 minutes, PLUS_MINUS = +239
  - Interpretation: Total points scored minus points allowed while this pair was on court
  - Statistical nature: Cumulative total, confounded with playing time
  - Modeling suitability: Requires normalization for rate-based analysis

**Not observed in Base measure (Advanced required):**
- `OFF_RATING`: Points per 100 possessions scored
- `DEF_RATING`: Points per 100 possessions allowed
- `NET_RATING`: Offensive rating minus defensive rating
- Possessions data

**Conclusion on targets:**
Rate-target feasibility remains pending. Direct Advanced measure acquisition is required to validate whether OFF_RATING, DEF_RATING, and NET_RATING are available and suitable for rate-based pair-fit modeling.

## Row counts after each processing step

Phase 0 is intentionally designed to keep a small reproducible skeleton. The expected processing path is:

1. raw lineup fetch: 1 payload per measure type
2. schema validation: eliminate malformed or duplicate rows
3. pair canonicalization: unordered pair deduplication using canonical IDs
4. join to prior-player table: coverage measurement for both players

Expected research summary rows:

- raw pair rows: to be populated by live fetch or fixture process
- valid rows: must exclude malformed, zero-minute, duplicate or missing target rows
- unique canonical pair rows: should be lower than raw rows after deduplication
- complete prior-player coverage rows: final join-rate metric

Phase 0 does not assert that the final dataset will be large enough to model a full historical sample until more live validation is done.

## Duplicate and missingness findings

The most likely failure modes for pair data are:

- duplicate rows caused by the same canonical pair appearing multiple times
- malformed `GROUP_ID` / `GROUP_NAME` records
- zero-minute or zero-game rows
- rows missing `ORTG`, `DRTG`, or `NET_RTG`
- missing prior player record for one or both players

The research scaffold explicitly tests for these conditions and records them as validation failures rather than silently coercing them into usable rows.

## Prior-feature join coverage

Prior-player feature coverage is a critical feasibility check. The intended join is by stable player ID, not by name.

The expected coverage issues include:

- rookies with no prior-season feature history
- inactive or unavailable players
- trades and team changes creating multiple historical rows or ambiguous team context
- ID mismatches or missing player IDs

The Phase 0 summary logic reports:

- `pair_rows`
- `complete_prior_rows`
- `missing_prior_rows`
- `complete_prior_rate`

This is the right metric for deciding whether the pair-table can be joined to prior player feature tables before historical expansion.

## Shared-minutes distribution and possessions

The Phase 0 contract treats shared minutes and possessions as reliability and sample-size information rather than as player-quality features.

The essential validity checks are:

- minimum shared-minute threshold
- duplicate or zero-minute row removal
- possession availability check
- explicit callout if possessions are absent and an estimate is not defensibly supported

If possessions are absent, the recommendation is to avoid a silent deduction and instead document the blocker or a clearly provisional derivation only after source validation.

## Target availability

The target should be evaluated using shared-court team efficiency measures that are reliably returned for the pair/lineup operating window. The likely targets are:

- ORtg
- DRtg
- net rating = ORtg - DRtg

The analysis must confirm whether they are directly returned, or whether a derived target is required after a trustworthy join.

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

## Recommended steps before Phase 1 modeling

Before proceeding to Phase 1 historical ingestion and model work, the project should complete:

1. **Phase 0E: Prior-player join audit**
   - Acquire one prior-season (2023–24) player-level stats response
   - Validate join keys and player ID stability
   - Quantify prior-player coverage for the Warriors pairs

2. **Advanced measure response validation**
   - Acquire one Warriors Advanced measure response (same team, 2024–25, GroupQuantity=2)
   - Validate OFF_RATING, DEF_RATING, NET_RATING, POSS availability
   - Confirm cross-measure join compatibility between Base and Advanced

3. **Multi-team feasibility smoke test**
   - Acquire Base pair-lineup data for 2–3 additional teams
   - Verify response structure consistency and data quality across teams
   - Estimate total historical data volume for 30-team, multi-season ingestion

4. **Data pipeline and schema validation**
   - Lock the canonical pair-identity rule
   - Document data-quality filters and validation checks
   - Establish caching and immutability guardrails
   - Design the prior-player join strategy with stable IDs

## Phase 1 go/no-go criteria

Proceed to Phase 1 only if all of the following are demonstrated:

- Pair identity parsing and canonicalization are reliable and tested
- Base measure data structures are consistent across multiple teams and seasons
- Prior-player feature records are available and joinable with stable IDs
- Rate-target fields (OFF_RATING, DEF_RATING, NET_RATING) are confirmed available in Advanced measure
- No same-season leakage is present in the feature pipeline
- Cache layer and schema-validation tests pass without live network dependence
- The feasibility report documents remaining gaps, data-quality limitations and untested assumptions

If these checks are not satisfied, the project should remain in Phase 0E diagnostics until the blockers are resolved.

If Advanced measure is unavailable or rate-target feasibility cannot be established, the project may explore alternative approaches (cumulative-differential modeling, semi-supervised learning on rank fields, or outcome-only studies) but should document these departures explicitly.

## Final note

Phase 0 research has established that the pair-fit v2 software-scaffold can be built, that live pair-lineup data is acquirable from stats.nba.com via direct HTTP requests, and that pair structure (identity, deduplication, validation) works correctly on observed Warriors data.

Phase 0 has **not yet** established:
- Rate-target field availability (requires Advanced measure)
- Prior-player historical feature coverage (requires 2023–24 acquisition and join)
- Multi-team and multi-season data consistency
- Predictive model feasibility

This report does not claim that rate-based efficiency targets are available, that cross-measure joins are compatible, that prior-player data is sufficient, or that a predictive model will succeed. Those questions require Phase 0E (prior-player audit) and Phase 1 (Advanced measure validation and multi-team ingestion) work.
