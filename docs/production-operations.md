# Production operations

## Deployment layout

- Source: `matthewellishanson/hanson-hoops`, branch `main`.
- Backend: Render, built with `backend/Dockerfile` from the repository root.
- Frontend artifact: `matthewellishanson/matthewellishanson.github.io`, branch `master`, under `hanson-hoops/comparisons/` with shared files under `hanson-hoops/assets/`.
- Frontend URL: `https://matthewellishanson.github.io/hanson-hoops/comparisons/index.html#/players`.
- Backend URL: `https://hanson-hoops.onrender.com`.

On 2026-08-08, source `main` was `1a0d00db0e594e650aea158dfb80ee60b4f9640d`. The deployed comparisons artifact was introduced by Pages commit `0bbc3da3d1410352fc7dc32a7507cf9b7dcf6cc9` and loaded `assets/index-85WZ0AZ5.js`; inspection of that bundle confirmed the fit-panel code from the source handoff. Render's exact deployed source commit still needs to be confirmed in the Render dashboard or deploy log because the public service does not expose build metadata.

## Render environment

Recommended non-secret values:

```text
FRONTEND_ORIGIN=https://matthewellishanson.github.io
NBA_REQUEST_TIMEOUT_SECONDS=8
NBA_TRUST_ENV_PROXY=0
WARM_LEAGUE_SHOTS_ON_STARTUP=0
NBA_RUNTIME_CACHE_DIR=/tmp/hanson-hoops-cache
WEB_CONCURRENCY=1
```

`WEB_CONCURRENCY=1` avoids duplicated in-memory/runtime caches on a small Render service. Packaged snapshots work with any worker count, so this can be raised after memory and upstream refresh behavior are measured.

Review these variable names in Render without revealing their values:

```text
NBA_RUNTIME_PROXY
PROXY_URL
NBA_STATS_PROXY
HTTP_PROXY
HTTPS_PROXY
http_proxy
https_proxy
NO_PROXY
no_proxy
```

Remove obsolete proxy variables. If a proxy is truly required, keep only one NBA-specific variable and rotate any credential that was ever shared publicly. Do not set `NBA_TRUST_ENV_PROXY=1` unless inherited proxy use is deliberate.

## Snapshot refresh

Run refreshes from a trusted machine or scheduled job, not from an API request:

```powershell
cd backend
python -m app.scripts.refresh_fit_snapshot --season 2025-26
```

The command uses bounded NBA calls, writes season/model-versioned CSV and metadata files atomically, and leaves an existing packaged snapshot unchanged if the upstream returns no rows. Review and test refreshed artifacts before deployment.

The comparison snapshots are built from redistributable sources:

- Kaggle dataset `eoinamoore/historical-nba-data-and-player-box-scores`,
  version 515 (CC0/public domain), using `PlayerStatistics.csv`. It is derived
  from NBA.com data, retains NBA player/team IDs, and supplies basic player and
  team profiles from 1946-47 through 2025-26. Fit inputs are packaged only from
  1996-97 onward, where the required box-score fields are available.
- `shufinskiy/nba_data` at
  `e829d4678be1e075f99e5d41a1c5f97089be446b` (Apache-2.0), using
  the revision-pinned `datasets/shotdetail_<start-year>.tar.xz` archives for
  1996 through 2025. These are the available regular-season shot-location years.

After downloading and extracting those files outside the packaged snapshot
directory, rebuild the compact artifacts from `backend`:

```powershell
curl.exe -sS -L -o C:\path\to\PlayerStatistics.csv `
  "https://www.kaggle.com/api/v1/datasets/download/eoinamoore/historical-nba-data-and-player-box-scores/PlayerStatistics.csv?datasetVersionNumber=515"
python -m app.scripts.build_multiseason_snapshots `
  --kaggle-player-stats C:\path\to\PlayerStatistics.csv
```

To rebuild player shot snapshots, download and extract the revision-pinned
archives into a temporary directory outside `app/cache/snapshots`, then run:

```powershell
$revision = "e829d4678be1e075f99e5d41a1c5f97089be446b"
$archiveDir = "C:\path\to\shot-archives"
$inputDir = "C:\path\to\extracted-shot-csvs"
New-Item -ItemType Directory -Force $archiveDir, $inputDir | Out-Null
1996..2025 | ForEach-Object {
  curl.exe -sS -L -o "$archiveDir\shotdetail_$_.tar.xz" `
    "https://raw.githubusercontent.com/shufinskiy/nba_data/$revision/datasets/shotdetail_$_.tar.xz"
  tar -xf "$archiveDir\shotdetail_$_.tar.xz" -C $inputDir
}
cd C:\path\to\hanson-hoops\backend
python -m app.scripts.build_shot_snapshots `
  --input-dir $inputDir
```

The input directory may contain any subset of `shotdetail_1996.csv` through
`shotdetail_2025.csv`; only those seasons are rebuilt. The command keeps one
compressed file per season so API reads can scan a single season and cache only
the requested player's rows instead of retaining a league-wide table in memory.

The generator excludes non-regular-season rows, aggregates shooting percentages
from makes and attempts, keeps NBA IDs, writes three consolidated deterministic
gzip files, and records coverage plus input SHA-256 in `coverage.json`. Review
that manifest and run endpoint tests before replacing an existing snapshot.

## Pre-deployment checks

From the source repository:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest backend\tests -q
cd nba-dashboard
npm ci
npm test
npm run lint
npm run build
```

Do not copy or publish `dist` until the source changes have been reviewed and deployment is separately authorized.

## Production validation

Use GET for endpoint validation. `curl -I` sends HEAD and a 405 only means the route does not support HEAD.

```powershell
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/health"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/players?search=LeBron&limit=5"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_bio?player_id=2544&season=2023-24"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_profile_stats?player_id=2544&season=2023-24&scale=percentile"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_shots?player_id=2544&season=2023-24"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_shots?player_id=201951&season=2012-13"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_shots?player_id=893&season=1996-97"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_profile_stats?player_id=1630162&season=2023-24&scale=percentile"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/player_shots?player_id=203932&season=2023-24"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/fit/player/2544?season=2023-24&min_minutes=300"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/fit/pair/2544/203932?season=2023-24&min_minutes=300&offense=1&defense=1&spacers=1&rebounding=1&primary_handler=auto"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/fit/pair/2544/203932?season_a=2012-13&season_b=2025-26&min_minutes=300&offense=1&defense=1&spacers=1&rebounding=1&primary_handler=auto"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/team_profile_stats?team_id=1610612747&season=2025-26&scale=percentile&opp_scale=percentile"
curl.exe -sS -i -H "Origin: https://matthewellishanson.github.io" "https://hanson-hoops.onrender.com/team_shots?team_id=1610612747&season=2025-26"
```

Every response should include `Access-Control-Allow-Origin: https://matthewellishanson.github.io`. Controlled failures should be JSON with `detail.code`, `detail.message`, `detail.retryable`, and `detail.request_id`; the same request ID is returned in `X-Request-ID` for Render log correlation.

Validate preflight separately:

```powershell
curl.exe -sS -i -X OPTIONS -H "Origin: https://matthewellishanson.github.io" -H "Access-Control-Request-Method: GET" "https://hanson-hoops.onrender.com/fit/pair/2544/203932"
```

## Deployment checklist

1. Confirm the source commit selected in Render.
2. Review the redacted Render variable names and remove/rotate obsolete proxy configuration.
3. Deploy the backend from the reviewed source commit.
4. Run the production GET and OPTIONS validations above and save request IDs for any failure.
5. Build the frontend with `npm run build`.
6. Copy the reviewed build artifact into `hanson-hoops/comparisons/` and `hanson-hoops/assets/` in the Pages repository without changing the `/hanson-hoops/` base.
7. Deploy Pages separately, then test the hash route, mixed-season player cards, and independently selected team seasons in a browser.

No commit, push, Render setting change, or deployment is implied by these instructions.
