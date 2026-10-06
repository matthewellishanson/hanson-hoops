# Phase 4C deployment-readiness report

Status: **PASS — Phase 4C static Render packaging correction complete; ready for narrow read-only audit**

Date: 2026-10-05

## Scope and checkpoint

The checkpoint began on `research/pair-fit-v2` at required committed HEAD
`29d36d1dcd6f26ec7b11383c1526a827cfd4542d`, with upstream divergence `0/0`,
an empty index, and exactly this initial worktree:

```text
 M backend/Dockerfile
?? .dockerignore
?? research/pair-fit-v2/PHASE4C_DEPLOYMENT_READINESS_REPORT.md
```

Phase 4A package files and Phase 4B backend/frontend integration files had no
worktree diff. This correction does not change application behavior. It keeps
the previously accepted Dockerfile layout: `/app/backend` is the working
directory, `app.main:app` resolves there, the checkout root resolves to `/app`,
and the Pair Fit source and package retain their repository-relative paths.
The existing `$PORT` and Gunicorn configuration are unchanged.

Files in the Phase 4C worktree remain limited to:

- `backend/Dockerfile`: accepted layout correction from the checkpoint;
- `.dockerignore`: compatibility-first root-context policy;
- `research/pair-fit-v2/PHASE4C_DEPLOYMENT_READINESS_REPORT.md`: this report.

## Focused dependency findings

The investigation covered exact names and paths, `read_csv`, ordinary file
opens, `Path`, glob/wildcard selection, script imports/invocation, FastAPI
lifespan and routes, frontend requests, and documented development workflows.
Retention is not presented as proof that every retained legacy file is needed.

| Category | Classification | Evidence | Docker decision |
|---|---|---|---|
| Draft classes CSV | workflow-required | `backend/app/scripts/build_rookie_snapshot.py` reads `app/cache/draft_classes.csv` to rebuild the canonical rookie snapshot | retain |
| Rookie snapshots | workflow-required for active `rookie_snapshot.csv` and `rookie_snapshot_partial.csv`; backup/temp for the two timestamped `.bak` files | Multiple maintenance/publication scripts read the active snapshots, and the partial file is resume state. Repository-wide exact-name, `glob`, `rglob`, wildcard, newest and latest selection checks found no consumer for either timestamped backup. | retain active and partial files; exclude the two `.bak` files |
| Backend scripts | workflow-required | The scripts implement snapshot refresh, multi-season snapshot construction, rookie story-data generation and maintenance. They directly read and write backend cache and `backend/docs/data` assets. No deployed startup hook imports or launches them. | retain precautionarily for historical maintenance/publication compatibility |
| Backend docs data | workflow-required with three unresolved legacy outputs | Scripts directly reference 22 of 25 files, including `BR_Origins_All_Raw.csv`; `rookie_points_scatter.csv`, `rookie_scatter_with_usage_v4.csv`, and `top_rookies_by_pp100.csv` have no conclusive repository reference. | retain all 25; the three unresolved files are retained precautionarily |
| Development requirements | development-only | The root README documents `backend/requirements.txt` as runtime dependencies and `backend/requirements-dev.txt` as the test/local-development install target; the latter adds only `pytest`. | exclude `requirements-dev.txt` |

Runtime route/startup inspection also confirms that packaged snapshot data,
`player_heights.csv`, `rookie_heights.csv`, `weights.json`, and Pair Fit v2's
six authorized files support deployed routes or startup behavior. No backend
startup code invokes a maintenance script. The manually invoked
`build_rookie_origins_timeline.py` contains a pre-existing user-specific default
path; it is not a credential and is retained unchanged as workflow technical
debt.

## Docker-context policy and inventory

The root `.dockerignore` starts closed, re-includes the historical `backend/`
tree, and then removes only conclusively development-only material, generated
junk, verified backups, and secret-bearing file classes. It opens the Pair Fit
research tree one directory level at a time, immediately re-excluding each
subtree before negating the next parent. This ordering prevents a parent
negation from leaking research caches, curated/modeling/planning evidence,
tests, reports or unrelated sources into the context.

The pattern simulation over the actual checkout selected **137 files**:

| Build-context category | Count | Decision basis |
|---|---:|---|
| Backend application source | 31 | runtime modules and `weights.json` |
| Backend runtime data | 38 | packaged route/startup snapshot and cache data |
| Backend workflow/maintenance material | 57 | 32 scripts, 22 referenced docs-data assets, and 3 active workflow cache files |
| Unresolved backend material intentionally retained | 3 | legacy docs-data outputs with no conclusive reference |
| Backend packaging files | 2 | `Dockerfile` and runtime `requirements.txt` |
| Pair Fit v2 runtime allowlist | 6 | explicitly authorized files only |
| **Total** | **137** | 131 backend + 6 Pair Fit |

Development-only source excluded: 5 files (four backend tests plus
`requirements-dev.txt`). Backup/temp excluded: 2 timestamped rookie snapshot
backups. Current generated backend junk excluded: 75 `__pycache__`/pytest-cache
files. Universal exclusions also cover `.git`, virtual environments,
`node_modules`, Python bytecode, test caches/temp areas, frontend build/cache
output, `.env` files, private-key formats, editor swap files and operating-system
metadata. All non-backend repository areas and unrelated research projects stay
excluded.

The exact Pair Fit allowlist is:

```text
research/pair-fit-v2/src/pair_fit_v2/__init__.py
research/pair-fit-v2/src/pair_fit_v2/inference.py
research/pair-fit-v2/production/pair-fit-v2.0.0/artifact_manifest.json
research/pair-fit-v2/production/pair-fit-v2.0.0/metadata.json
research/pair-fit-v2/production/pair-fit-v2.0.0/model.json
research/pair-fit-v2/production/pair-fit-v2.0.0/player_profiles.csv
```

The simulation selected all six and no other research file. Explicit negative
checks passed for raw Pair Fit cache, curated, modeling and planning evidence,
Pair Fit tests/reports, unrelated research, backend tests, dev requirements,
timestamped backups, `.env` files and Python caches.

## Secret and safety scan

All 137 selected files were scanned by filename and content for environment
files, API/access keys, bearer tokens, passwords, private keys, credential
assignments, key containers, and databases. No credible secret material,
`.env` file, private-key file, credential database, or raw/protected Pair Fit
evidence was selected. The only user-specific absolute path is the unchanged
manual-script default noted above; no secret value is present. Ordinary public
NBA data and published story data are intentionally not classified as secrets.

## Static and host-side verification

- Docker-ignore simulation: passed; 131 backend files plus the exact six-file
  Pair Fit allowlist, with no prohibited research file.
- Dockerfile `COPY` source checks: passed; all eight sources exist and are
  eligible under the context policy.
- Categorized context inventory: passed; category counts reconcile to 137.
- Context-only secret scan: passed with the one documented non-secret absolute
  path.
- Package SHA-256 verification: passed:

| File | SHA-256 |
|---|---|
| `model.json` | `55a1386abb1abaadd78b29e8addafe1912f419c01586d239c81325ffc3f69302` |
| `artifact_manifest.json` | `71c2859cc06525bec989575eaf438afa70ab6c6862aa72599e29b6944cae1140` |
| `metadata.json` | `ebfb87d38266dcc6099e8ea7019c60109aa39058ddea737ab89e18cd61eb92e3` |
| `player_profiles.csv` | `eb4534668fd3ddf57477e2989885d2dff5753506393463a4bedc6a31ad8c6265` |

- Focused Pair Fit backend tests: 14 passed; 12 existing `httpx`
  deprecation warnings.
- Complete backend tests: 44 passed; 40 existing `httpx` deprecation warnings.
- Host dependency check: passed; no broken requirements.
- Application import and local Uvicorn lifespan startup: passed with external
  league-shot warming disabled.
- Local HTTP smoke: `/health` returned 200; OpenAPI exposed both the v2 and
  legacy pair-fit routes; allowed-origin GET and OPTIONS returned 200 with the
  expected CORS origin and GET in allowed methods.
- Focused frontend tests: 26 passed.
- ESLint: passed.
- GitHub Pages-aware production build: passed; existing large-chunk warning
  only. The first sandboxed attempt could not access Vite's config path, and the
  same build passed when rerun with the existing narrow build permission.
- Python compilation: passed.
- Duplicate-model scan: no Pair Fit package artifact copy exists under
  `backend/`.
- Phase 4A and Phase 4B preservation checks: no diff.
- Whitespace checks for the tracked and two untracked files and
  `git diff --check`: passed; Git emitted only its existing LF/CRLF checkout
  warning for `backend/Dockerfile`.

No external NBA request was made.

## Container evidence and mandatory Render gates

The corrected Docker layout passed static and host-side verification. Local
Docker and Podman are unavailable, so no image or container was built locally
and **no in-container claim is being made**. Missing local Docker evidence is
explicitly deferred; it is not silently treated as passed and is not classified
as a local implementation failure.

Remote deployment remains unauthorized. The first authorized Render build must
verify all of the following before deployment acceptance:

1. image construction from repository-root context using `backend/Dockerfile`;
2. installed runtime dependencies and `pip check` inside the image;
3. exact package inventory and the four authoritative package hashes;
4. inference import and read-only package loading from the container layout;
5. Gunicorn startup and binding to Render's `$PORT`;
6. v2 endpoint parity, refusal behavior and swapped-player symmetry;
7. allowed/disallowed-origin CORS behavior and preflight;
8. `/health`, OpenAPI and all legacy-route availability.

## Deferred technical debt

- Audit the three unresolved legacy docs-data outputs and the broader retained
  backend data/script set only after Pair Fit deployment and the separate
  30-team preseason package are complete.
- Replace the user-specific default path in the rookie-origins maintenance
  script during that audit, with an explicit workflow/migration plan.
- Reassess whether maintenance scripts and publication data belong in a future
  runtime image only after their operational owners and invocation paths are
  documented.

No cleanup, repository reorganization, rename, move, deletion, story change,
model change, Render setting change, deployment, publication, commit or push
occurred. The narrowest next step after this PASS is one final static read-only
audit of these three worktree files; only after that audit should an authorized
Render build execute the mandatory gates above.
