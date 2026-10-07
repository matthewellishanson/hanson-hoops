# NBA preview research tool

A small, local, cache-first Python workflow for the 2026 Hanson Hoops team previews. It acquires or imports source tables once, validates and saves them, then supports offline filtering, comparison, joins, year-over-year changes, and exact CSV exports with companion provenance notes.

The default window is the five regular seasons from `2021-22` through `2025-26`. Every command still records explicit season and season type; playoff, preseason, team-stint, and combined rows are never silently mixed.

## Current first-release status

As of October 7, 2026, the code path is complete for NBA player/team Base totals and per-game, NBA Advanced, Base per 100 possessions, player shot zones, team-specific player on/off, derived shooting tables, manual CSV imports, validation, query, comparison, joins, year-over-year changes, coverage, benchmarks, and export.

The local `stats.nba.com` request was time-boxed and remained unavailable with a `ConnectionError`. No empty or zero-filled dataset was created. To prove the workflow, immutable audited NBA response captures already present in Pair Fit v2 were copied through the generic JSON importer into this project's ignored cache; Pair Fit files were only read and were not changed. This produced actual player Base Totals, Per100, and locally calculated shooting tables for the full five-season window, plus shot-zone tables for the first three seasons.

| Season | Player totals | Player per-game | Player Per100 | Player shooting | Player Advanced | Team tables | On/off | Zones |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021-22 | 605, structural | not acquired | 605, structural | 605, structural | not acquired | not acquired | not acquired | 605, structural |
| 2022-23 | 539, structural | not acquired | 539, structural | 539, structural | not acquired | not acquired | not acquired | 539, structural |
| 2023-24 | 572, structural | not acquired | 572, structural | 572, structural | not acquired | not acquired | not acquired | 572, structural |
| 2024-25 | 569, structural | not acquired | 569, structural | 569, structural | not acquired | not acquired | not acquired | not acquired |
| 2025-26 | 582, structural + benchmark | not acquired | 582, structural | 582, structural + benchmark | not acquired | not acquired | not acquired | not acquired |

Run `coverage` for the live local status. Local caches and exports are intentionally ignored by Git, so another checkout begins at `not_acquired` until acquisition/import is run.

## Setup on Windows

Run from `C:\Users\mehan\code\hanson-hoops\research\preview-research`:

```powershell
Set-Location C:\Users\mehan\code\hanson-hoops\research\preview-research
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[notebook,test]"
.\.venv\Scripts\python.exe -m pytest -q
```

The folder has its own `pyproject.toml`, dependencies, source package, tests, notebook, cache layout, and instructions so it can later move to a standalone repository. It has no runtime dependency on backend code or Pair Fit.

For this Hanson Hoops checkout only, the optional bootstrap script reproduces the current five-season local player cache from audited response captures already in the repository. It reads and copies those files; it does not modify them. A future standalone repository can omit this convenience script and use live/manual imports.

```powershell
.\scripts\bootstrap_from_repo_captures.ps1
```

## Acquire data

Broad league tables are preferred. This acquires the core tables sequentially for the five-season default window, waits at least one second between requests, uses a bounded timeout and one limited transport retry, and resumes from successful caches:

```powershell
Set-Location C:\Users\mehan\code\hanson-hoops\research\preview-research
.\.venv\Scripts\python.exe -m preview_research.cli acquire `
  --dataset player_base_totals `
  --dataset player_base_per_game `
  --dataset player_advanced `
  --dataset player_per100 `
  --dataset team_base_totals `
  --dataset team_base_per_game `
  --dataset team_advanced `
  --dataset team_per100
```

For a single season:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli acquire `
  --dataset player_base_totals --season 2025-26 --season-type "Regular Season"
```

Endpoint parameters are created and verified against the installed `nba_api==1.10.1` signatures before the direct request. Source bytes are saved before transformation with parameters, UTC retrieval time, endpoint, package version, response schema, row counts, byte count, and SHA-256. A failed request writes an explicit `unavailable` metadata record and no processed CSV.

The existing safe proxy environment names are supported without logging their values: `NBA_RUNTIME_PROXY`, `PROXY_URL`, or `NBA_STATS_PROXY`. Set `NBA_TRUST_ENV_PROXY=1` only if inherited proxy variables are deliberately required.

Build chart-ready shooting fields after Base Totals. Advanced tables are joined when present; local `CALC_TS_PCT` and `CALC_EFG_PCT` still build from makes/attempts/points when Advanced is unavailable:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli build-shooting --entity player
.\.venv\Scripts\python.exe -m preview_research.cli build-shooting --entity team
```

Shot zones are a single broad request per season:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli acquire --dataset player_shot_zones --season 2025-26
```

On/off is team-scoped by the NBA endpoint. It is deliberately never hidden inside a league-wide player loop:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli acquire `
  --dataset player_on_off --season 2025-26 --team-id 1610612760
```

After `team_base_totals` exists, an explicit resumable all-team loop is:

```powershell
$teamFile = ".\data\processed\nba\2025-26\regular_season\team_base_totals.csv"
$teamIds = Import-Csv $teamFile | Select-Object -ExpandProperty TEAM_ID -Unique
foreach ($teamId in $teamIds) {
  .\.venv\Scripts\python.exe -m preview_research.cli acquire `
    --dataset player_on_off --season 2025-26 --team-id $teamId
}
```

## Import saved responses or public CSVs

A saved NBA endpoint response is checked against its payload identity, copied into this project's raw cache, then passed through the same validator. This is how the current 2025-26 proof was created without touching Pair Fit data:

```powershell
$sourceRoot = "..\pair-fit-v2\cache\phase4a\2025-26-player-profiles\external"
.\.venv\Scripts\python.exe -m preview_research.cli import-nba-json `
  "$sourceRoot\02-totals\verified-response.json" `
  --dataset player_base_totals --season 2025-26 `
  --source "Audited Pair Fit v2 Phase 4A stats.nba.com capture" `
  --source-metadata "$sourceRoot\02-totals\verification.json"
```

Manual free-source CSVs are copied before transformation and keep separate provider/provenance. Keys and row scope are mandatory so combined rows and team stints cannot be confused:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli import-csv `
  C:\path\to\basketball-reference-table.csv `
  --dataset br_player_table --season 2025-26 `
  --provider basketball_reference `
  --source "Basketball Reference Standard table" `
  --source-url "https://www.basketball-reference.com/" `
  --grain "player x team stint x season" `
  --key Player --key Tm --row-scope team_stint
```

No equivalence between NBA and Basketball Reference metrics is implied. Add a deliberate column mapping outside the immutable raw copy if a downloaded table uses different headers.

## Query, compare, join, and export

All commands below read saved CSVs only and work with the network disconnected.

First query and export, from this project directory:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli query `
  --dataset player_shooting --season 2025-26 `
  --where "MIN>=1000" --where "FG3A>=200" `
  --sort CALC_TS_PCT --descending --limit 25 `
  --columns PLAYER_ID,PLAYER_NAME,TEAM_ABBREVIATION,GP,MIN,PTS,FG3A,CALC_FG3_PCT,CALC_EFG_PCT,CALC_TS_PCT `
  --export 2025-26-shooting-shortlist.csv
```

The exact filtered rows go to `exports\2025-26-shooting-shortlist.csv`; `exports\2025-26-shooting-shortlist.notes.md` records filters, units, source hashes, validation/benchmark state, timestamp, and export hash.

Compare actual scoring and shooting efficiency for one player across the two locally available seasons:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli compare `
  --dataset player_shooting --season 2024-25 --season 2025-26 `
  --entity "Shai Gilgeous-Alexander" `
  --metrics PTS,FG3A,FG3_PCT,CALC_EFG_PCT,CALC_TS_PCT
```

Find actual 2025-26 rows whose three-point percentage increased from 2024-25 while meeting a 200-attempt threshold:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli yoy `
  --dataset player_shooting --season 2024-25 --season 2025-26 `
  --metric CALC_FG3_PCT `
  --where "CHANGE_CALC_FG3_PCT>0" --where "FG3A>=200" `
  --sort CHANGE_CALC_FG3_PCT --descending --limit 25 `
  --columns PLAYER_ID,PLAYER_NAME,TEAM_ABBREVIATION,SEASON,FG3M,FG3A,CALC_FG3_PCT,CHANGE_CALC_FG3_PCT `
  --export 2025-26-three-point-improvers.csv
```

Join totals to per-100 values with stable player/season keys, then apply a real total-minutes threshold. `TEAM_ID` is not used as a player join key because it may merely display a traded player's current/final team:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli join `
  --left-dataset player_base_totals --right-dataset player_per100 `
  --season 2025-26 --keys PLAYER_ID,SEASON,SEASON_TYPE `
  --where "MIN_LEFT>=1000" --sort PTS_RIGHT --descending --limit 20 `
  --columns PLAYER_ID,PLAYER_NAME_LEFT,TEAM_ABBREVIATION_LEFT,GP_LEFT,MIN_LEFT,PTS_RIGHT
```

Rank teams after team acquisition:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli yoy `
  --dataset team_advanced --season 2024-25 --season 2025-26 `
  --metric NET_RATING --where "CHANGE_NET_RATING>-100" `
  --sort CHANGE_NET_RATING --descending --limit 30 `
  --columns TEAM_ID,TEAM_NAME,SEASON,NET_RATING,CHANGE_NET_RATING
```

Export one team's on/off table when acquired:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli query `
  --dataset player_on_off --season 2025-26 --team-id 1610612760 `
  --sort MIN --descending `
  --columns TEAM_ID,TEAM_NAME,VS_PLAYER_ID,VS_PLAYER_NAME,ON_OFF,GP,MIN,OFF_RATING,DEF_RATING,NET_RATING `
  --export 2025-26-okc-player-on-off.csv `
  --note "Descriptive team on/off splits; not causal impact and not Pair Fit."
```

## Notebook

Open the documented workflow from this project directory:

```powershell
.\.venv\Scripts\python.exe -m jupyter lab .\notebooks\preview_workflow.ipynb
```

The notebook uses the same cache-only functions as the CLI and includes coverage, player comparison, three-point improvement, team ranking, compatible joins, and team on/off export examples. It does not contain invented basketball conclusions.

## Coverage and publication checks

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli coverage
```

A successful request is only `structurally_checked`. Record an independently published benchmark before treating a recent-season table as publication-ready:

```powershell
.\.venv\Scripts\python.exe -m preview_research.cli benchmark `
  --dataset player_base_totals --season 2025-26 `
  --column FG_PCT --entity-column PLAYER_ID --entity 1628983 `
  --expected 0.553 --tolerance 0.0005 `
  --source "Named independent published table" `
  --source-url "https://publisher.example/table"
```

The current 2025-26 proof passed a limited independent cross-check against the separately sourced packaged Kaggle version 515 table for Shai Gilgeous-Alexander's field-goal and three-point percentages. This is evidence for those checked values, not a claim that every row/field is independently verified. The analogous 2024-25 packaged `raw_fg_pct` differs from the imported NBA response (`.517` versus `.519`), so 2024-25 remains `not_checked` and should be reconciled before publication.

## Important publication limitations

- The production `/player_stats` route exposes only game date and points. It is not used here.
- Existing player radar values include cap-normalized values; they are not league percentiles and are not used here.
- The legacy `build_multiseason_snapshots.py` fallback computes fields named `PTS_PER100`, `FGA_PER100`, and similar by multiplying per-minute rates by 48. Those are per-48 shortcuts, not possession-based statistics, and are not used here.
- Legacy fit feature code can zero-fill fields when a source table is absent. This research package instead records `unavailable` and creates no table.
- Existing comparison coverage flags establish file presence, not research-quality completeness. This package maintains its own structural and benchmark status.
- The warning above does not apply to the separately audited Pair Fit v2 production package. Audited immutable NBA response bodies from that research area were used only as copied source captures for this local proof.
- Advanced, team, on/off, and current shot-zone acquisition remain locally unavailable until `stats.nba.com` access succeeds or suitable source files are imported. On/off requests are team-scoped and can be relatively expensive.
- No BPM, PER, or Win Shares are calculated.

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for grains, units, local formulas, traded-player rules, and validation states.
