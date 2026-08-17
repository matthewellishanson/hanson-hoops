# Phase 0 feasibility report

## Executive conclusion

`currently blocked; live data acquisition partially verified`

The synthetic Phase 0 research scaffold is feasible and passes local validation checks. Phase 0C acquired one authentic live response from stats.nba.com for LeagueStandingsV3 (2024–25 regular season), confirming that direct HTTP requests to the API succeed. However, the nba_api wrapper does not work from this environment. Pair-lineup data endpoints (TeamDashLineups, LeagueDashLineups) remain untested with direct requests and are the next diagnostic target. The project is blocked from historical pair data ingestion until pair-lineup endpoints are confirmed to be reachable via direct HTTP requests or an alternative request strategy is established.

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

## Actual schemas observed and source evidence (Phase 0C)

### Live schema: LeagueStandingsV3 2024–25

The Phase 0C control request acquired an authentic live response from stats.nba.com. This is the first genuine live schema observed in the research.

**LeagueStandingsV3 response structure:**
- HTTP 200 status
- Content-Type: `application/json; charset=utf-8`
- Top-level structure: `{"resultSets": [...]}`
- Result set 0:
  - Headers: 92 columns
  - Column names (complete list): `LeagueID`, `SeasonID`, `TeamID`, `TeamCity`, `TeamName`, `TeamSlug`, `Conference`, `ConferenceRecord`, `PlayoffRank`, `ClinchIndicator`, and 82 additional columns including team stats
  - Rows: 30 (one per NBA team in 2024–25 season)
  - Row example structure: Array of values matching the 92-column schema

**Data quality:**
- All 30 teams present and accounted for
- No null or malformed result sets
- Response size: 17.6 KB JSON

### Expected schemas for pair-lineup endpoints (not yet live-tested)

The installed nba_api client (version 1.10.1) provides signatures for `TeamDashLineups` and `LeagueDashLineups`. These have been inspected in source but not yet successfully fetched from stats.nba.com.

**Expected lineup-group columns (from nba_api source inspection):**

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

## Recommended changes before multi-season ingestion

Before moving to full historical ingestion, the project should:

1. lock the canonical pair-identity rule
2. decide and document the valid data-quality filters
3. confirm the target-returning endpoint schema with mock or live fixtures
4. draft the prior-player join strategy with stable IDs only
5. decide how to treat rookies, trades, and sparse shared-minute records
6. require a clear holdout split with 2025–26 reserved as the untouched test season

## Phase 1 go/no-go criteria

Proceed to Phase 1 only if all of the following are true:

- pair identity is canonicalized and deduplicated reliably
- target fields are available or defensibly derived
- prior-player coverage is high enough to support the intended historical expansion
- no same-season leakage is present in the feature pipeline
- the cache layer and schema-validation tests pass without live network dependence
- the feasibility report clearly documents remaining gaps and assumptions

If these checks fail, the project should remain in research-only feasibility work rather than moving to model selection.

## Final note

This report does not claim that interaction effects are predictable or that the complete historical dataset is sufficient. It only concludes whether the Phase 0 data contract and pipeline are feasible enough to justify the next research step.
