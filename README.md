# Hanson Hoops

Hanson Hoops is a React/Vite NBA comparison dashboard backed by FastAPI. The deployed frontend uses GitHub Pages hash routing and reads the API from Render.

## Prerequisites

- Python 3.12.x. Render uses `python:3.12-slim`; use the same Python family locally.
- Node.js 22.12+ (Node 24 is also supported by the current Vite version).
- npm, using the committed `nba-dashboard/package-lock.json`.

This repository uses Python's standard `venv`. It is not a uv-managed project.

## Backend setup

From the repository root, create one local environment:

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements-dev.txt
```

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
```

Confirm that the activated interpreter belongs to this repository:

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

The executable should be under `hanson-hoops/.venv` and report Python 3.12.x.

Start FastAPI from the `backend` directory because the deployable Python package is `app`:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is then available at <http://127.0.0.1:8000>. Do not use the old project-root command `uvicorn backend.app.main:app`; it does not match Render's module layout.

Run backend tests from the repository root:

```powershell
python -m pytest backend\tests -q
```

`backend/requirements.txt` contains runtime dependencies. `backend/requirements-dev.txt` adds test dependencies and is the normal local-development install target.

## Frontend setup

Install the frontend dependencies after the initial clone and whenever
`package-lock.json` changes:

```powershell
cd nba-dashboard
npm ci
```

For normal frontend starts, including later terminals in the same checkout, use:

```powershell
cd nba-dashboard
npm run dev
```

Open <http://localhost:5173/hanson-hoops/>. The local frontend calls `http://localhost:8000`; production builds call `https://hanson-hoops.onrender.com`. Override either with `VITE_API_BASE` only when intentionally testing another backend.

`npm ci` removes and recreates `node_modules`, so stop any running Vite process
with `Ctrl+C` before invoking it. On Windows, an error such as `EPERM ... unlink
... esbuild.exe` means a Node/Vite process (or occasionally antivirus) still has
that executable open; it does not normally mean npm needs Administrator access.
Find processes belonging to this checkout without stopping unrelated Node apps:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -in @('node.exe', 'esbuild.exe') -and $_.CommandLine -like '*hanson-hoops*nba-dashboard*' } |
  Select-Object ProcessId, ParentProcessId, Name, CommandLine
```

Stop only the displayed Vite/esbuild process IDs with `Stop-Process -Id <id>`,
then retry `npm ci`. If no matching process remains, close terminals or editors
running the dev server and retry after antivirus finishes scanning the file.

Frontend checks:

```powershell
npm test
npm run lint
npm run build
```

The Vite base remains `/hanson-hoops/`, and the application continues to use `HashRouter` for GitHub Pages.

## NBA data reliability

User-facing comparison reads are cache-first. The compact files under `backend/app/cache/snapshots/` provide player and team profiles from 1946-47 through 2025-26, projected-fit inputs from 1996-97 through 2025-26, and shot locations for the packaged 2023-24 and 2025-26 seasons. Missing shot seasons retain a bounded live fallback. A successful response reports `data_source` so callers can distinguish `live`, `runtime_cache`, and `packaged_snapshot` data.

Every player and team card owns its season independently, so comparisons can mix player-seasons or team-seasons. Pair-fit requests send both player seasons and normalize each profile against its own season cohort. The same player may be compared across two seasons. Fit requests before 1996-97 return an explicit non-retryable availability error because the required tracking inputs are incomplete. Expected upstream failures return a structured HTTP 502; profile failures are never represented as zero-valued HTTP 200 responses. Shot charts return either real data, a truthful no-data result, or a structured upstream error.

Live fit snapshots are refreshed explicitly outside user requests:

```powershell
cd backend
python -m app.scripts.refresh_fit_snapshot --season 2025-26
```

Review the generated CSV and metadata before committing or deploying it. The startup league-shot warm is disabled by default because Gunicorn otherwise performs one large request per worker.

## Proxy behavior

The NBA HTTP client ignores inherited `HTTP_PROXY`/`HTTPS_PROXY` variables by default. Configure at most one NBA-specific proxy variable, in this precedence order:

1. `NBA_RUNTIME_PROXY`
2. `PROXY_URL`
3. `NBA_STATS_PROXY`

Set `NBA_TRUST_ENV_PROXY=1` only if inherited proxy behavior is intentional. Proxy values may contain secrets and must never be printed, pasted into issues, or committed. Rotate any credentials that have appeared in public logs.

See [docs/production-operations.md](docs/production-operations.md) for Render settings, snapshot refreshes, deployment steps, and validation commands.
