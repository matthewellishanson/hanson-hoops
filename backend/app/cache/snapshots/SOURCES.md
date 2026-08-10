# Comparison snapshot sources

The packaged comparison files are generated data, not hand-authored fixtures.
`coverage.json` records feature availability by season and exact source details.

- Player/team profiles and derived fit inputs: Kaggle dataset
  `eoinamoore/historical-nba-data-and-player-box-scores`, version 515,
  CC0/public domain. Its `PlayerStatistics.csv` retains NBA.com player/team IDs
  and covers 1946-47 through 2025-26.
- Shot locations: `shufinskiy/nba_data`, Apache-2.0 license. The source archive
  identifies the underlying records as NBA shot-detail data.

Only the columns required by Hanson Hoops are packaged. The downloaded source
archives are temporary build inputs and are not committed.

Regenerate after downloading the source files documented in
`docs/production-operations.md`:

```powershell
cd backend
python -m app.scripts.build_multiseason_snapshots `
  --kaggle-player-stats <PlayerStatistics.csv>
```

`build_shot_snapshots` rebuilds every extracted
`shotdetail_<start-year>.csv` it finds into a compact, per-season gzip file and
updates shot availability in `coverage.json`. `build_comparison_snapshots`
remains available for rebuilding a single profile-and-shot season. Keep
downloaded source data outside the snapshot directory and commit only the
compact generated artifacts.
