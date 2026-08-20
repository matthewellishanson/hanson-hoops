# Pair-fit v2 data dictionary

This data dictionary covers the research-only Phase 0 scaffold, bounded Phase 1A audit and Phase 1B architecture contract. It is intentionally provisional and subject to revision.

## Pair identity fields

- `pair_key`: canonical unordered pair key, typically represented as a tuple of two player IDs sorted to enforce A+B = B+A.
- `league_id`: league namespace included in every Phase 1B season and observation key; NBA is currently `00`.
- `target_season`: normalized NBA season label in `YYYY-YY` form.
- `season_type`: normalized lowercase season-type slug, such as `regular-season`.
- `team_id`: positive decimal-string team ID normalized without leading zeroes.
- `player_1_id`: lexicographically first canonical player ID in a pair record.
- `player_2_id`: lexicographically second canonical player ID in a pair record.
- `GROUP_ID`: raw lineup/group identifier returned by the NBA endpoint.
- `GROUP_NAME`: raw lineup/group label returned by the NBA endpoint.

The stable `observation_key` is (`league_id`, `target_season`, `season_type`, `team_id`, `player_1_id`, `player_2_id`). `GROUP_ID`, names and source row order are never key components.

## Target fields

- `TEAM_ID`: team id associated with the pair-season observation.
- `TEAM_ABBREVIATION`: team abbreviation for readability.
- `OFF_RATING`: observed Advanced-measure offensive rating while both players share the court.
- `DEF_RATING`: observed Advanced-measure defensive rating while both players share the court.
- `NET_RATING`: observed Advanced-measure net rating; reconciled to `OFF_RATING - DEF_RATING` within displayed rounding across all four Phase 1A pilot teams.
- `E_OFF_RATING`, `E_DEF_RATING`, `E_NET_RATING`: separately returned estimated rating fields. They must not be silently conflated with the non-estimated rating fields.
- Base `MIN`: canonical shared-minute exposure for the pair while on the court; selected because the Base response preserves fractional precision.
- Advanced `MIN`: retained as returned for audit, but not assumed interchangeable with Base `MIN` at sparse exposure because Phase 1A observed different rounding.
- Advanced `POSS`: observed possession exposure; reliability/sample-size information, not player quality. Missing `POSS` or `POSS <= 0` makes the row ineligible for a possession-based rate target even when numeric ratings are returned; the row and endpoint values remain unchanged.
- `GP`: games in which the pair appears, where available.
- `PTS`: total points produced by the pair while on the court.
- `PLUS_MINUS`: cumulative on-court team point differential while the pair shares the court. It is not net rating, an on/off statistic or a per-100-possession target.

## Reliability fields

- Base `MIN`: shared-minute reliability and sample-size field, not a player-quality feature.
- Advanced `POSS`: possession reliability and sample-size field, not a player-quality feature.
- Advanced `MIN`: audit field retained as returned; not substituted for Base `MIN` at sparse exposure.
- `GP`: used to evaluate exposure and coverage.
- `W_PCT`: context for reliability and validation, not a quality label.
- `GROUP_SET`: identifies the grouping context from the NBA endpoint.

## Prior player feature fields

The exact final feature matrix is not yet selected. Phase 0F confirmed the observed 2023-24 `LeagueDashPlayerStats` (Base, Per100Possessions) schema returns, per player:

- `PLAYER_ID`, `PLAYER_NAME`: stable identity fields. Joins must use `PLAYER_ID` only, never `PLAYER_NAME`.
- `TEAM_ID`, `TEAM_ABBREVIATION`, `TEAM_COUNT`: team context; `TEAM_COUNT > 1` indicates a player traded during the season, with the endpoint returning one aggregate row rather than one row per team stint.
- `AGE`, `GP`: identity/sample-size context. `GP` can exceed 82 for a traded player because the two teams involved may have played a different number of games by the trade date; this is a valid combined-team total, not an error, and must not be capped or rejected.
- `MIN`: observed to be reported under the same `Per100Possessions` normalization as rate fields, not season-total minutes. It must not be used as the prior player's season-total eligibility or reliability measure; a later ingestion phase needs a validated `Totals`-per-mode response (or another trustworthy season-total-minutes field) for that purpose. Phase 0F establishes join coverage only, not the final prior-player reliability contract.
- Non-ranking Base statistics (`FGM`, `FGA`, `FG_PCT`, `FG3M`, `FG3A`, `FG3_PCT`, `FTM`, `FTA`, `FT_PCT`, `OREB`, `DREB`, `REB`, `AST`, `TOV`, `STL`, `BLK`, `BLKA`, `PF`, `PFD`, `PTS`, `PLUS_MINUS`, `NBA_FANTASY_PTS`, `DD2`, `TD3`, `WNBA_FANTASY_PTS`): candidate future features, not yet selected or validated.

The initial research set may include:

- `player_id`
- `team_id` or team history
- `minutes`
- `usage_pct`
- `true_shooting_pct`
- `fg_pct`, `fg3_pct`, `ft_pct`
- `ast_pct`
- `tov_pct`
- `orb_pct`, `drb_pct`
- `stl_pct`, `blk_pct`
- `height`, `weight`, `age`, `experience`

These are classified as follows:

- capability: true shooting, usage, assist %, rebound %, efficiency metrics
- role/style: usage, assist %, turnover %, offensive style variables
- physical context: height, weight, age, experience
- reliability: minutes, games, possessions, exposure fields
- team context: team ID, team history, team environment features
- unresolved: any variable with unclear interpretation or limited cross-season comparability

## Validation and data-quality fields

- `is_valid_pair`: boolean indicating whether the row passes the minimal pair validation checks.
- `prior_history_status`: uniform Phase 1 baseline categorical field per pair: `complete` (both players have a prior-season record), `one_missing`, or `both_missing`. Complete-status pairs form the primary baseline population, subject independently to target eligibility. Other statuses are retained for coverage analysis and later evaluation of one universal no-history fallback (not yet defined). No pair is dropped, missing prior statistics are never zero-imputed, and no roster-specific policy is introduced. Phase 1A found the `complete` share varies from 57.2% to 81.6% across four pilot teams; the pattern is consistent with the selected roster profiles but does not establish roster type as the cause or a league-wide relationship.
- `observation_key`: the full Phase 1B key defined above. Phase 1A's fixed NBA/regular-season context is now explicit. The same player or pair on another team, season or season type is a distinct observation.
- `schema_fingerprint`: result-set name, ordered column list, and column count. Row count is data volume and is not part of schema identity.
- `schema_drift_classification`: one of `identical`, `reordered`, `additive`, `subtractive`, `mixed`, `result_set_name_changed` or `invalid_fingerprint`. Only `identical` is accepted automatically; all other values quarantine the asset for review.
- `duplicate_pair_flag`: indicates whether the canonical pair key appears more than once.
- `missing_prior_player_flag`: indicates whether one or both players lack prior player features. Phase 0F observed this at 4/23 unique players (17.4%) and 40/183 pairs (21.9%) for the Warriors 2024-25 population against 2023-24 `LeagueDashPlayerStats`.
- `possession_rate_target_eligible`: explicit boolean; false when Advanced `POSS` is missing or `POSS <= 0`, regardless of returned numeric rating values. This eligibility flag does not delete or alter the row.
- `target_eligibility_reasons`: ordered list explaining derived ineligibility, including missing/nonnumeric possessions, nonpositive possessions and missing/nonnumeric required ratings.
- `zero_or_missing_possession_flag`: identifies Advanced rows requiring the retained zero/missing-possession audit.
- `zero_minute_flag`: measure-qualified audit flag. An Advanced zero can reflect rounding while Base `MIN` remains positive, so it must not overwrite the Base exposure value.
- `base_row_present`, `advanced_row_present`: source-presence booleans produced by the row-preserving full outer reconciliation. An unmatched row is retained and blocks a clean-season release.

## Phase 1B manifest and provenance fields

- `contract_version`: version of the manifest, key and transformation contract.
- `manifest_logical_identity`: complete normalized league, season, season type, numerically ordered team-ID set, canonical measure order, endpoint, `group_quantity`, and governed extra request parameters. The manifest ID is recomputed from this identity and must also agree with the externally approved release contract.
- `manifest_id`: deterministic logical manifest identifier recomputed from `manifest_logical_identity`; not a response-content hash.
- `raw_asset_id`: deterministic ID derived from endpoint plus every normalized request parameter. Validation separately proves that this ID matches the embedded asset identity and that the embedded identity matches the manifest's expected team/measure request.
- `group_quantity`: raw request-identity field fixed at `2` for `pair_observations`; it prevents pair/trio/quartet/five-player raw-cache collisions. Higher-order observations require a new versioned contract with `group_size` and an ordered canonical player-ID collection.
- `raw_asset_status`: `planned`, `acquired`, `verified`, `failed` or `quarantined`.
- `acquired_at`, `http_status`: recorded source-event time and response status.
- `response_body_bytes`: bytes received for the source event.
- `raw_body_hash`: optional hash of exact received bytes.
- `cache_file_bytes`: bytes in the serialized cache file.
- `canonical_json_hash`: semantic parsed-JSON integrity hash under a documented algorithm.
- `serialization_version`: serializer identity/settings required to interpret cache-file bytes.
- `schema_verification.fingerprints`: nonempty fingerprints with unique result-set names and exactly one required `Overall` and `Lineups` entry. Each fingerprint contains result-set name, ordered columns and column count and must classify as `identical` against the approved measure-specific schema contract; a stored `accepted` status is insufficient by itself.
- `input_asset_ids`, `input_canonical_json_hashes`: exact curated-output lineage inputs.
- `transform_contract_version`: version of row reconciliation and field derivation logic.
- `curated_file_hash`, `curated_file_bytes`, `curated_row_count`: future Parquet-output provenance; no such artifact exists in this design phase.

## Phase 1C operational manifest fields

- `operational_manifest_version`: version of the persisted raw-season state machine.
- `transition_sequence`, `transition_history`: monotonically ordered, atomically persisted asset-state changes.
- `attempt_history`: one record per explicitly initiated Phase 1C transport attempt, including status, categorized failure or verified cache evidence, latency when an HTTP response exists, and response bytes.
- `approved_schema_contract_id`: deterministic identifier for the measure-specific `Overall` and `Lineups` fingerprints used by the run.
- `legacy_reconciliation`: explicit description of historical metadata format and fields unavailable from older pilot acquisitions; unknown values remain null and are not fabricated.
- `metadata_relative_path`: Git-ignored sidecar containing the request identity, source event, cache evidence, and schema result for a newly acquired asset.
- `authorization.maximum_new_live_requests`: persisted ceiling on Phase 1C transport attempts. The original 52-attempt ceiling was extended by exactly one user-authorized attempt tied to Charlotte Advanced; all 53 recorded attempts are now consumed.
- `authorization.extensions`: auditable asset-specific additions to the original ceiling, including asset ID, added attempt count, timestamp, and authorization note.

## Phase 1D endpoint-diagnostic fields

- `diagnostic_version`: versioned identity, sequencing, validation, and replay contract for the bounded population-exhaustiveness diagnostic.
- `diagnostic_asset_id`: deterministic `phase1d-diagnostic-asset:` ID derived from endpoint and every normalized request parameter. The separate namespace and `phase1d/diagnostics/` cache path prevent collision with Phase 1C `raw-asset:` IDs and production raw-season paths.
- `diagnostic_sequence`: fixed authorization order. Later requests remain untouched after a conclusive result or any request failure.
- `diagnostic_identity`: complete endpoint, season, season type, league, team/filter, measure, group quantity, and endpoint-specific parameters, including `LastNGames`.
- `diagnostic_status`: `planned`, `verified`, `failed`, or `verified_after_offline_revalidation`. The last value preserves the original stopped attempt while recording validation of the same immutable payload after a narrowly documented response-normalization correction; it is not a new request.
- `diagnostic_attempt_count`: count of explicitly initiated live attempts. A failed attempt is never automatically retried.
- `diagnostic_raw_body_hash`, `diagnostic_canonical_json_hash`, `diagnostic_response_body_bytes`, `diagnostic_latency_seconds`: exact diagnostic source/cache evidence, isolated from Phase 1C provenance.
- `boundary_classification`: `boundary_signal_present` or `no_boundary_signal` for cache-only row-count/combinatorial evidence. A signal alone is not proof of truncation or omission.
- `distinct_player_count`, `theoretical_unordered_pair_count`, `absent_theoretical_pair_count`: combinatorial diagnostics over valid returned pair IDs. Theoretical absence does not assert that every theoretical pair shared the court.
- `maximum_rank_values`, `low_end_base_minutes`, `low_end_advanced_possessions`, `low_end_advanced_minutes`: measure-qualified endpoint-behavior diagnostics; never model features or eligibility thresholds.
- `response_envelope.pagination_or_truncation_metadata`: explicit inspection result for page, total, limit, continuation, and truncation fields.
- `matched_full_season_keys`, `diagnostic_only_keys`, `full_season_only_keys`: canonical unordered pair-key set comparison. Partial-window rows are not inserted into the full-season observation table.
- `population_exhaustiveness_classification`: `proven_non_exhaustive` when at least one structurally valid same-season diagnostic key is outside the full-season set; otherwise `not_proven_exhaustive`. Absence of a new key never yields `proven_exhaustive`.
- `offline_revalidation`: audit record for the Request 1 `PORound` empty-request/numeric-zero response normalization, including the original stopped error, zero additional live requests, unchanged later sequence, validation result, and pair-key comparison.

## Phase 1E window-recovery fields

- `phase1e_version`: versioned request-identity, window, validation, aggregation, gate, and replay contract.
- `window_label`, `date_from`, `date_to`: fixed early/late label and exact inclusive ISO date bounds. The two authorized windows are contiguous and non-overlapping.
- `request_parameters`: normalized `TeamDashLineups` parameters, including measure, team, season, season type, group quantity, and endpoint-formatted `DateFrom`/`DateTo`.
- `request_identity`, `diagnostic_asset_id`: deterministic complete identity and separate `phase1e-diagnostic-asset:` ID. Phase 1E payloads use `cache/phase1e/windows/` and cannot collide with Phase 1C `raw-asset:` or Phase 1D diagnostic IDs.
- `attempt_count`, `status`, `latency_seconds`, `http_status`, `response_body_bytes`, `raw_body_hash`, `canonical_json_hash`, `acquired_at`, `validation_classification`: immutable acquisition and validation evidence. A failed request is never retried or followed by a later request.
- `result_set_schemas`, `row_counts`: ordered header fingerprints and data volume for every response result set.
- `window_reconciliation`: full-outer Base/Advanced pair audit containing matched, Base-only, Advanced-only, malformed, same-player, duplicate, possession-validity, and target-eligibility counts. Unmatched and ineligible rows remain visible.
- `recovered_pair_count`, `full_season_keys_found`, `full_season_only_keys`, `window_union_only_keys`, `early_only_keys`, `late_only_keys`, `both_window_keys`: canonical unordered pair-set reconciliation. `window_union_only_keys` are “recovered-only”; a larger observed union is not a claim of global exhaustiveness.
- `phase1d_proving_keys_present`: whether the Charlotte union contains all three keys that proved the full-season response non-exhaustive in Phase 1D.
- `additive_field_audit`: field-by-field early-plus-late comparison against immutable full-season values. Supported Base fields are counts/totals validated empirically in Phase 1E; Advanced `POSS` is supported. Percentages, ranks, pace, rate fields, and Advanced `MIN` are not additive under this contract.
- `rate_recomposition`: possession-weighted comparison for `OFF_RATING`, `DEF_RATING`, and `NET_RATING`, including comparable count, mean/median/maximum absolute error, counts and percentages within `0.1` and `0.2`, and every discrepancy above `0.2`. `POSS=0` rows are preserved but excluded from rate arithmetic.
- `independent_rating_derivation`: evidence classification for rate calculations attempted from Base `PTS`/`PLUS_MINUS` and Advanced `POSS`; one of `validated`, `approximate`, `unsupported`, or `unresolved`.
- `recovered_only_exposure`: player identities, defensibly additive games, summed Base `MIN`, summed Advanced `POSS`, and distribution summaries for recovered-only pairs. Base `MIN` is the exposure field; Advanced `MIN` remains audit-only.
- `threshold_sensitivity`: diagnostic counts and possession shares at `POSS >= 1`, `5`, `10`, `25`, `50`, and `100`. These fields support eligibility/reliability research only and do not select a final threshold or define predictive player-quality features.
- `continuation_gate`: named Charlotte gate conditions and results controlling whether Philadelphia requests are allowed.
- `recovery_classification`: one of `window recovery not demonstrated`, `window recovery demonstrated; target recomposition unresolved`, `window recovery and target recomposition demonstrated for Charlotte only`, or `window recovery and target recomposition demonstrated for both affected team-seasons`. None asserts global population exhaustiveness.

## Player-feature registry fields

- `feature_source_id`, `feature_source_version`: stable source and definition identity.
- `feature_source_kind`, `feature_source_locator`: provider/endpoint or unresolved proposed-source locator without embedding credentials.
- `feature_aggregation_contract`: declared meaning of one source row, including trade aggregation behavior.
- `feature_season`, `player_id`: player-season join key, always earlier than the target season/cutoff.
- `feature_source_status`: `observed`, `proposed` or `retired`.
- `feature_family`: one or more of capability, role/style, physical context, reliability, team context, heliocentrism or unresolved.
- `availability_rule`: must be `strictly_before_target_season` for registered prior-player sources.
- `field_contract`: versioned source field definitions; candidate fields are not automatically model features.

Future heliocentrism sources use the same registry. Their source, formula, denominator, grain, trade aggregation, missingness and availability timing must be documented before activation; Phase 1B selects none of them.

## Notes

- This dictionary is provisional and should evolve with the final feature contract.
- Phase 0 does not claim that the final feature set is correct or complete.
- The pair identity is unordered and canonicalized to avoid double-counting A+B and B+A.
- Future validation must be time-ordered or rolling-origin, preserve 2025-26 as the untouched final test season, and reject a random pair-row split because overlapping players and pairs violate row independence.
- Phase 1E demonstrated Charlotte window-population recovery and additive-total reconstruction but left defensive/net target recomposition unresolved. Model training and historical expansion remain prohibited until that target question and the exposure, uniform missing-history, and validation policies are resolved.
- The proposed Parquet and DuckDB fields describe future artifacts only; none were created in Phase 1B design verification.
