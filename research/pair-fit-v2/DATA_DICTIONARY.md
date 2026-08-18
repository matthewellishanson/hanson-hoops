# Pair-fit v2 data dictionary

This data dictionary covers the research-only Phase 0 scaffold and the bounded Phase 1A audit. It is intentionally provisional and subject to revision.

## Pair identity fields

- `pair_key`: canonical unordered pair key, typically represented as a tuple of two player IDs sorted to enforce A+B = B+A.
- `player_a_id`: canonical first player ID in a pair record.
- `player_b_id`: canonical second player ID in a pair record.
- `GROUP_ID`: raw lineup/group identifier returned by the NBA endpoint.
- `GROUP_NAME`: raw lineup/group label returned by the NBA endpoint.

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
- `observation_key`: the canonical four-team-pilot observation key of (target season, team ID, canonical player 1 ID, canonical player 2 ID). The same player or pair on a different team is a distinct observation and is never deduplicated across teams.
- `schema_fingerprint`: result-set name, ordered column list, and column count. Row count is data volume and is not part of schema identity.
- `duplicate_pair_flag`: indicates whether the canonical pair key appears more than once.
- `missing_prior_player_flag`: indicates whether one or both players lack prior player features. Phase 0F observed this at 4/23 unique players (17.4%) and 40/183 pairs (21.9%) for the Warriors 2024-25 population against 2023-24 `LeagueDashPlayerStats`.
- `possession_rate_target_eligible`: explicit boolean; false when Advanced `POSS` is missing or `POSS <= 0`, regardless of returned numeric rating values. This eligibility flag does not delete or alter the row.
- `zero_or_missing_possession_flag`: identifies Advanced rows requiring the retained zero/missing-possession audit.
- `zero_minute_flag`: measure-qualified audit flag. An Advanced zero can reflect rounding while Base `MIN` remains positive, so it must not overwrite the Base exposure value.

## Notes

- This dictionary is provisional and should evolve with the final feature contract.
- Phase 0 does not claim that the final feature set is correct or complete.
- The pair identity is unordered and canonicalized to avoid double-counting A+B and B+A.
- Future validation must be time-ordered or rolling-origin, preserve 2025-26 as the untouched final test season, and reject a random pair-row split because overlapping players and pairs violate row independence.
- Phase 1B is limited to architecture and ingestion design. Model training and historical expansion remain prohibited until the exposure policy, uniform missing-history treatment, and validation design are approved.
