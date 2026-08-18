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

The exact final feature matrix is not yet selected. The initial research set may include:

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
- `duplicate_pair_flag`: indicates whether the canonical pair key appears more than once.
- `missing_prior_player_flag`: indicates whether one or both players lack prior player features.
- `zero_minute_flag`: identifies rows with unusable shared-minute totals.

## Notes

- This dictionary is provisional and should evolve with the final feature contract.
- Phase 0 does not claim that the final feature set is correct or complete.
- The pair identity is unordered and canonicalized to avoid double-counting A+B and B+A.
