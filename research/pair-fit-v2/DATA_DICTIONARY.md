# Pair-fit v2 data dictionary

This data dictionary covers the research-only Phase 0 feasibility scaffold. It is intentionally provisional and subject to revision.

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
- `NET_RATING`: observed Advanced-measure net rating; reconciled to `OFF_RATING - DEF_RATING` within displayed rounding in the one-team smoke test.
- `E_OFF_RATING`, `E_DEF_RATING`, `E_NET_RATING`: separately returned estimated rating fields. They must not be silently conflated with the non-estimated rating fields.
- `MIN`: shared minutes for the pair while on the court.
- `POSS`: observed Advanced-measure possessions; reliability/sample-size information, not player quality.
- `GP`: games in which the pair appears, where available.
- `PTS`: total points produced by the pair while on the court.
- `PLUS_MINUS`: cumulative on-court team point differential while the pair shares the court. It is not net rating, an on/off statistic or a per-100-possession target.

## Reliability fields

- `MIN`: used as a reliability and sample-size field, not as a player-quality feature.
- `POSS`: used as a reliability and sample-size field, not as a player-quality feature.
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
- `prior_history_status`: adopted provisional Phase 1 baseline categorical field per pair: `complete` (both players have a prior-season record), `one_missing`, or `both_missing`. Complete-status pairs are used for the primary baseline model; other statuses are retained for coverage analysis and a possible later no-history fallback (not yet defined). No pair is dropped from raw or curated datasets, and missing prior statistics are never zero-imputed. This policy is provisional and subject to reevaluation after the Phase 1A multi-team pilot. Phase 1A (see `PHASE1A_PILOT_REPORT.md`) found the `complete` share varies materially by roster type (57.2%-81.6% across four pilot teams); this is disclosed, not resolved.
- `observation_key`: the canonical four-team-pilot observation key of (target season, team ID, canonical player 1 ID, canonical player 2 ID). The same player or pair on a different team is a distinct observation and is never deduplicated across teams.
- `duplicate_pair_flag`: indicates whether the canonical pair key appears more than once.
- `missing_prior_player_flag`: indicates whether one or both players lack prior player features. Phase 0F observed this at 4/23 unique players (17.4%) and 40/183 pairs (21.9%) for the Warriors 2024-25 population against 2023-24 `LeagueDashPlayerStats`.
- `zero_minute_flag`: identifies rows with unusable shared-minute totals.

## Notes

- This dictionary is provisional and should evolve with the final feature contract.
- Phase 0 does not claim that the final feature set is correct or complete.
- The pair identity is unordered and canonicalized to avoid double-counting A+B and B+A.
