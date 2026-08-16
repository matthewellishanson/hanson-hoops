# Phase 0 feasibility report

## Executive conclusion

`currently blocked`

The synthetic Phase 0 research scaffold is feasible and passes local validation checks. The live NBA pair-season audit is currently blocked by upstream NBA stats access and timeout behavior, which prevented a successful bounded live request for the required 2024–25 pair-lineup data. The project remains blocked from claiming data feasibility or predictive validity until a successful live schema-and-coverage audit is completed.

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

## Actual schemas observed and source evidence

The installed library confirms the endpoint class is `LeagueDashLineups` in the `nba_api` package, version 1.10.1. The expected schema includes lineup/group columns such as:

- `GROUP_SET`
- `GROUP_ID`
- `GROUP_NAME`
- `TEAM_ID`
- `TEAM_ABBREVIATION`
- `GP`
- `MIN`
- `PTS`
- `PLUS_MINUS`
- additional efficiency and volume fields

The key caveat is that this endpoint exposes lineup-group rows rather than a dedicated player-pair table with `PLAYER_ID_1` and `PLAYER_ID_2` columns. Pair identity must therefore be parsed from `GROUP_ID` and/or `GROUP_NAME`, with explicit canonicalization and validation.

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
