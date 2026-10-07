# Data dictionary and research rules

## Dataset identities

Every table is identified by dataset, provider, season, season type, and (for on/off) team ID. Regular season, playoffs, and preseason are separate cache paths and can never be concatenated accidentally by the loader.

| Dataset | Source measure / mode | Row grain | Stable key |
|---|---|---|---|
| `player_base_totals` | NBA Base / Totals | combined player × season | `PLAYER_ID`, `SEASON`, `SEASON_TYPE` |
| `player_base_per_game` | NBA Base / PerGame | combined player × season | `PLAYER_ID`, `SEASON`, `SEASON_TYPE` |
| `player_advanced` | NBA Advanced / Totals | combined player × season | `PLAYER_ID`, `SEASON`, `SEASON_TYPE` |
| `player_per100` | NBA Base / Per100Possessions | combined player × season | `PLAYER_ID`, `SEASON`, `SEASON_TYPE` |
| `team_base_totals` | NBA Base / Totals | team × season | `TEAM_ID`, `SEASON`, `SEASON_TYPE` |
| `team_base_per_game` | NBA Base / PerGame | team × season | `TEAM_ID`, `SEASON`, `SEASON_TYPE` |
| `team_advanced` | NBA Advanced / Totals | team × season | `TEAM_ID`, `SEASON`, `SEASON_TYPE` |
| `team_per100` | NBA Base / Per100Possessions | team × season | `TEAM_ID`, `SEASON`, `SEASON_TYPE` |
| `player_shot_zones` | NBA shot locations / By Zone / Totals | combined player × season | `PLAYER_ID`, `SEASON`, `SEASON_TYPE` |
| `player_on_off` | NBA TeamPlayerOnOffSummary / Advanced | player × team × season × on/off state | `TEAM_ID`, `VS_PLAYER_ID`, `ON_OFF`, `SEASON`, `SEASON_TYPE` |
| `player_shooting` | Local calculation from NBA totals, optionally joined to NBA Advanced | combined player × season | `PLAYER_ID`, `SEASON`, `SEASON_TYPE` |
| `team_shooting` | Local calculation from NBA totals, optionally joined to NBA Advanced | team × season | `TEAM_ID`, `SEASON`, `SEASON_TYPE` |

`LeagueDashPlayerStats` rows are labeled `ROW_SCOPE=combined`. `TEAM_ID`, `TEAM_ABBREVIATION`, and `TEAM_COUNT` are retained from the source, but the displayed team must not be used to infer a traded player's stint membership. A manual stint table must use `ROW_SCOPE=team_stint` and include team identity in its key.

## Units

- NBA percentage fields such as `FG_PCT`, `FG3_PCT`, `FT_PCT`, `TS_PCT`, and `EFG_PCT` are fractions from 0 to 1.
- Counts/rates retain the endpoint's requested `PerMode`. In particular, `MIN` in `player_per100` is not a season total-minutes eligibility field. Join to `player_base_totals` and use its `MIN` for a total-minutes threshold.
- `player_on_off` keeps NBA's `OFF_RATING`, `DEF_RATING`, and `NET_RATING` definitions and the source's `MIN`. On/off is descriptive context, not causal player impact and not a Pair Fit prediction.
- Source rank fields ending in `_RANK` stay in immutable raw JSON and are excluded from processed research-stat tables.
- Local calculations always begin with `CALC_`:
  - `CALC_FG2_PCT = (FGM - FG3M) / (FGA - FG3A)`
  - `CALC_FG3_ATTEMPT_RATE = FG3A / FGA`
  - `CALC_FT_RATE = FTA / FGA`
  - `CALC_TS_PCT = PTS / (2 × (FGA + 0.44 × FTA))`
  - `CALC_EFG_PCT = (FGM + 0.5 × FG3M) / FGA`
- A zero-attempt percentage is missing, not zero. Missing values are preserved. Infinite numeric values fail validation and export.
- Combined percentages must be calculated from summed makes and attempts, never by averaging percentages.

## Validation states

| State | Meaning |
|---|---|
| `acquired` / `imported_raw_response` | Source bytes and request/import identity were saved. This alone is not publication readiness. |
| `structurally_checked` | Required columns, stable-key uniqueness, finite values, percentage units, and expected population passed. |
| `benchmark_checked` | At least one explicitly recorded value matched a separately named published source within tolerance. |
| `benchmark_failed` | A recorded independent comparison did not match. Investigate before publication. |
| `unavailable` | Request/import failed. No processed table was created. |
| `incomplete` | Reserved for a known partial population; it must never be represented as zero-filled complete data. |

NBA and Basketball Reference tables retain different `provider`, `source`, units, and definitions. A stable-ID one-to-one join is allowed only when the writer deliberately supplies compatible keys; same-named metrics are not assumed equivalent.

This release does not calculate BPM, PER, or Win Shares.

