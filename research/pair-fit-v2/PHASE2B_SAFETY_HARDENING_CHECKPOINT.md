# Phase 2B offline safety-hardening checkpoint

## Outcome

This bounded pass is complete as an uncommitted, offline checkpoint. It did not resume acquisition, authorize a retry, or change the original cumulative ceiling of 50 attempts. A later decision must separately authorize the Atlanta retry and decide whether a cumulative ceiling of 51 is appropriate.

Starting and final branch: `research/pair-fit-v2`. Starting and final HEAD: `edb4481239ff52abf6a97a097ce0d85562fa9382`. The initial working tree was clean. “Checkpoint” here means a reviewed and tested working-tree boundary; no Git commit was created.

## Preserved evidence

The real Phase 2B cache was used only for read-only validation. No raw response, failed attempt, manifest, ledger, quarantine body, dry-run, or allowlist file was written. The protected hashes before and after the pass are identical:

| Evidence | SHA-256 |
|---|---|
| Phase 2A manifest | `55406bb879d2fb93edd490b11b39bbcdb3a4de85a17a9bd0672444d9680ec6e0` |
| Phase 2A attempt ledger | `78b4242de669c3a22d88d4cac3b7d26c671c579e1aa1cb474da1f81939fcc1bd` |
| Phase 2B release manifest | `4a66c6dd9af49eb57beb794b7867d0d49606b90021b6ae69669d5e7435c1870e` |
| Phase 2B attempt ledger | `228424bb699cf7d3b72d78396f176e03eb41d3f66d985912e1c0761d9d16f177` |
| Original Phase 2B dry run | `e42e92ddddb6f1d877b8cf23a6941d7831797de85d3bb39cae1e4c9ee28ff4b2` |
| Original Phase 2B live allowlist | `bcbca56d29518ae2a98ba17a14271baa1b18cfe082147e561d9bda73a1ae4add` |

The read-only real-cache replay verified ten imported pair assets, two prior-player dependencies, 539 unique positive-decimal prior-player IDs in each dependency, exact Per100Possessions/Totals ID-set equality, the original 50 allowlisted identities, and zero network calls. Current state remains ten `reused_verified`, one `failed` Atlanta Base entry, and 49 `planned` entries. The preview reports that persisted stop and does not advance it.

Two independent network-blocked real-cache replays produced the identical semantic summary SHA-256 `64ffbc977526294357ec337513e30ab0838023d4c529b599da6e53e84f1326ba`; each reported zero network calls.

No newly added check rejects the preserved evidence. If one had done so, this pass would have reported the rejection rather than rewriting the evidence.

## Hardening changes

- A persisted `release_analysis_failure` is now a restart-stable stop checked before replay or transport selection. The existing failed-asset stop remains in force independently.
- Acquisition must validate the original persisted dry-run and exact 50-identity allowlist. Every new asset is checked against its approved ordinal, release asset ID, and full normalized identity before transport.
- The direct transport path now receives the selected `ReleaseStore.cache_root`; it no longer falls back to a repository-relative cache. It also requires the exact validated allowlist mapping.
- `--dry-run` is now explicitly a read-only preview and returns `side_effects: []`. It cannot be combined with initialization. The separate `--persist-initial-plan` operation creates evidence only from a pristine plan, uses create-once writes, and validates existing evidence without overwriting it.
- Pair boundaries now require exactly two distinct, positive, canonical decimal player IDs and reject duplicate canonical pairs. The check applies during response validation and team reconciliation.
- Prior-player boundaries now require the exact 2023-24 target/2022-23 prior mapping, Base Per100Possessions or Totals identity, positive canonical decimal `PLAYER_ID` values, uniqueness within each response, and exact equality of both source ID sets before joins.
- Final analysis independently repeats the prior-player season, ID, uniqueness, and cross-mode equality checks. The five-team canary comparison now derives expected counts from the immutable Phase 2A analysis rather than embedding its observed counts in executable logic.

The changes remain within the existing Phase 2B module, CLI, tests, and this checkpoint documentation. No broad file split, historical-experiment rewrite, or generic acquisition framework was introduced.

## Regression and synthetic evidence

The corrected focused Phase 2B suite passed 31 tests. New cases cover:

- default `run_acquisition(..., transport=None)` propagation of a genuinely nondefault selected cache root through the real direct adapter, with only the HTTP session boundary stubbed;
- direct rejection of an unauthorized request identity before HTTP session construction;
- persisted analysis-stop enforcement after a simulated restart with the affected team's Base and Advanced assets verified and the following team still planned;
- exact allowlist tamper rejection before transport;
- create-once plan evidence and read-only preview behavior;
- rejection of nondecimal, noncanonical, nonpositive, and same-player pair IDs;
- prior-player duplicate, invalid-ID, and same-season rejection;
- an analysis-focused synthetic completed 30-team/60-asset summary run twice with networking blocked, producing the same deterministic analysis hash. This exercises deterministic analysis behavior; it is not an end-to-end cache-integrity or acquisition test.

The complete offline research suite passed 231 tests. The only warnings were the known inability to write the pre-existing optional `.pytest_cache`; the isolated task basetemp worked and was safely removed. No test made a live NBA request.

## Review checkpoint

The reviewed diff is bounded to:

- `src/pair_fit_v2/phase2b_raw_season.py`
- `src/pair_fit_v2/phase2b_cli.py`
- `tests/test_phase2b_raw_season.py`
- `README.md`
- this checkpoint report

`git diff --check` passes. The safety controls are internally consistent: persisted stop state is checked first; plan and allowlist evidence are immutable and exact; store-root selection reaches transport; and response/player identity checks run before accepted evidence enters reconciliation or joins. All mutable test state is isolated in temporary directories. Part of the expected schema and prerequisite contract is derived read-only from the real research cache; those real files are never mutated by the tests.

No network request, retry, acquisition continuation, attempt-ceiling change, cache promotion, raw-evidence rewrite, data curation, model work, production change, commit, push, rebase, reset, stash, branch switch, or history rewrite occurred. Phase 2B remains stopped pending a separate authorization decision.
