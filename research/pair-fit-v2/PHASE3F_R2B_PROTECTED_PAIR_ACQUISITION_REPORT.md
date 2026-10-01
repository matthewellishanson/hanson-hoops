# Phase 3F-R2B Protected Pair Acquisition Report

## FAILED — authorized protected acquisition attempt failed

Phase 3F-R2B stopped after the first authorized request. The request returned HTTP 200 without redirect, but the verifier required the response to contain exactly one result set. The preserved strict-JSON response contains the normal `Overall` result set and one `Lineups` result set, so the verifier quarantined the response before promotion. No retry occurred and none is authorized. The other 59 identities remain `not_started`.

This is a Phase 3F-R2B acquisition failure, not a scientific result for Pair Fit v2.

## 1. Repository checkpoint

- Branch: `research/pair-fit-v2`
- Committed HEAD: `8d8f7f5fc6de31b81506091dff00b3e617e13232`
- Upstream: `origin/research/pair-fit-v2`
- Ahead/behind before execution: `0/0`
- Index: clean; no staged changes
- Pre-execution worktree: only the intended R2B policy, implementation, CLI, tests, and narrow `.gitignore` additions
- Six R2A commit changes were present at HEAD: the `.gitignore` update plus the two human documents, two source files, and one test file.
- The audited R1S plan and R2A response identities matched the prompt exactly. All pinned R0/R0.1/R1S/R2A inputs also passed SHA-256 verification.

## 2. Authorization and invocation

- Authorization path: `planning/phase3f-r2b/authorization.json`
- Authorization bytes: `71,656`
- Authorization SHA-256: `12249e6acca554507501e887c9afeb4f3cad0079fb40ab2738bea3d308ade856`
- Authorized identities: 60 exactly
- Order: 30 numeric team IDs; Base then Advanced for each team
- Official invocation count: 1
- Python: `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe`
- Working directory: `C:\Users\mehan\code\hanson-hoops\research\pair-fit-v2`
- Resolved `PYTHONPATH`: `C:\Users\mehan\code\hanson-hoops\research\pair-fit-v2\src`
- Command: `python -m pair_fit_v2.phase3f_r2b_cli acquire --project-root . --planning-dir planning\phase3f-r2b --authorization-path planning\phase3f-r2b\authorization.json --evidence-root cache\phase3f-r2b\protected-final-target`
- Invocation-record SHA-256: `936708826bbfaf729a1ad8c9ed7dcbbf2e8bce13b11e3e9a08403fe665b524fe`

The invocation record was written once before transport. The import-only canary had passed, and the evidence namespace was absent before this invocation.

## 3. Complete request inventory and outcome

`—` means no transport attempt occurred because the first failure stopped the phase. Team is the official numeric NBA team ID from the frozen plan.

| # | Team | Measure | Attempt | HTTP | Lineups rows | Bytes | Raw SHA-256 | Canonical JSON SHA-256 | Retries | Redirect | Disposition |
|---:|---:|---|---:|---:|---:|---:|---|---|---:|---|---|
| 1 | 1610612737 | Base | 1 | 200 | 200 | 51,905 | `e2134b18de903b79b1bcce8d628cf041ae18a50ccab00018d3b29b7daa63aff0` | `bac19c1df5f1a25de0e558c62410457917bb25ffb9130833e346444ae8c30f8d` | 0 | false | `failed_or_quarantined` |
| 2 | 1610612737 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 3 | 1610612738 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 4 | 1610612738 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 5 | 1610612739 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 6 | 1610612739 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 7 | 1610612740 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 8 | 1610612740 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 9 | 1610612741 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 10 | 1610612741 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 11 | 1610612742 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 12 | 1610612742 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 13 | 1610612743 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 14 | 1610612743 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 15 | 1610612744 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 16 | 1610612744 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 17 | 1610612745 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 18 | 1610612745 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 19 | 1610612746 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 20 | 1610612746 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 21 | 1610612747 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 22 | 1610612747 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 23 | 1610612748 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 24 | 1610612748 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 25 | 1610612749 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 26 | 1610612749 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 27 | 1610612750 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 28 | 1610612750 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 29 | 1610612751 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 30 | 1610612751 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 31 | 1610612752 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 32 | 1610612752 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 33 | 1610612753 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 34 | 1610612753 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 35 | 1610612754 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 36 | 1610612754 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 37 | 1610612755 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 38 | 1610612755 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 39 | 1610612756 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 40 | 1610612756 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 41 | 1610612757 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 42 | 1610612757 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 43 | 1610612758 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 44 | 1610612758 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 45 | 1610612759 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 46 | 1610612759 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 47 | 1610612760 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 48 | 1610612760 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 49 | 1610612761 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 50 | 1610612761 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 51 | 1610612762 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 52 | 1610612762 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 53 | 1610612763 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 54 | 1610612763 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 55 | 1610612764 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 56 | 1610612764 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 57 | 1610612765 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 58 | 1610612765 | Advanced | — | — | — | — | — | — | — | — | `not_started` |
| 59 | 1610612766 | Base | — | — | — | — | — | — | — | — | `not_started` |
| 60 | 1610612766 | Advanced | — | — | — | — | — | — | — | — | `not_started` |

## 4. Timing and spacing

- Attempt start: `2026-10-01T03:17:19.136288Z` (`2026-09-30 22:17:19` America/Chicago)
- Attempt completion: `2026-10-01T03:17:21.055158Z` (`2026-09-30 22:17:21` America/Chicago)
- Recorded transport elapsed time: `1.9220000000022992` seconds
- Inter-attempt spacing: not applicable; only one transport attempt occurred

## 5. Preserved evidence inventory

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `planning/phase3f-r2b/authorization.json` | 71,656 | `12249e6acca554507501e887c9afeb4f3cad0079fb40ab2738bea3d308ade856` |
| `planning/phase3f-r2b/official_invocation.json` | 935 | `936708826bbfaf729a1ad8c9ed7dcbbf2e8bce13b11e3e9a08403fe665b524fe` |
| `cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-start.json` | 281 | `90553e18945c075aa285207d01821266930d3e9fcb79b84b9386b82bf741f9c9` |
| `cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-response.bin` | 51,905 | `e2134b18de903b79b1bcce8d628cf041ae18a50ccab00018d3b29b7daa63aff0` |
| `cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-outcome.json` | 594 | `c799c52fbb449c126edb669d5abcf003ae3703895f2734a7bd0d2a1c6db6d9cf` |
| `cache/phase3f-r2b/protected-final-target/1610612737-01-base/quarantine.json` | 346 | `affc98a8a1cba3158764085cc5811977c31f4a088f9dda5a412b65004f97986f` |

No promoted response, verification record, reconciliation artifact, summary, or R2B artifact-hash manifest was created because the phase stopped on the failed response-envelope gate.

## 6. Read-only failure verification

The preserved body is strict valid JSON. Its canonical JSON SHA-256 is `bac19c1df5f1a25de0e558c62410457917bb25ffb9130833e346444ae8c30f8d`.

The response envelope contains:

- `Overall`: 57 headers and 1 row
- `Lineups`: 56 headers and 200 rows

The implementation expected the entire response to contain exactly one result set, rather than requiring exactly one named `Lineups` result set while allowing the endpoint's `Overall` set. This made the verifier reject a structurally recognizable TeamDashLineups envelope. That diagnosis is based only on read-only inspection of the quarantined bytes; the implementation was not repaired and the request was not rerun.

The frozen restart-state replay is deterministic:

- `failed_or_quarantined`: 1 identity
- `not_started`: 59 identities
- `started_without_outcome`: 0 identities
- `completed_verified`: 0 identities
- `conflicting_state`: 0 identities

## 7. Structural reconciliation status

No Base/Advanced team reconciliation is possible. Atlanta Base has quarantined evidence, Atlanta Advanced is not started, and all other team responses are not started.

- Teams fully acquired: 0
- Base responses completed and verified: 0
- Advanced responses completed and verified: 0
- All 60 completed and verified: no
- Global pair observation count: not calculated
- Zero-possession findings: not evaluated
- Invalid-field findings: not evaluated
- Exact-250 unresolved teams: not evaluated; the quarantined `Lineups` set has 200 rows, but it was not promoted
- Other structurally unresolved teams: all 30, because acquisition is incomplete

No partial subset is labeled final-test ready.

## 8. Tests and checks

- `py_compile`: passed for the R2B implementation, CLI, and tests
- Focused R2B synthetic tests: 28 passed
- Broad applicable historical run: 274 passed; one R0.1 test failed only because it intentionally requires the historical R0.1 committed HEAD rather than the current required R2A HEAD
- R0.1 rerun excluding only that immutable historical-HEAD assertion: 23 passed, 1 deselected
- `git diff --check`: passed
- Ignore checks: passed for both R2B namespaces
- Credential scan: no credential-like assignment found
- Prohibited-operation scan: no estimator, prediction, metric, residual, baseline, or model-serialization operation found
- Import-only canary: passed

The synthetic coverage included the 60-request allowlist and ordering, request drift and recovery-window rejection, transport settings, one-attempt and restart states, HTTP/timeout/redirect/JSON/result-set/row-width failures, pair canonicalization and defects, required fields, zero possessions, Base/Advanced equality and mismatch, exact-250 handling, deterministic reconciliation, write-once destinations, and absence of model operations.

## 9. Explicit phase-boundary confirmations

- Recovery requests made: 0
- Automatic retries: 0
- Manual retries: 0
- Unauthorized requests: 0
- Final-test table constructed: no
- Individual eligible model rows selected: no
- Predictor profiles joined: no
- Imputation or scaling applied: no
- Estimator loaded or fit: no
- Predictions created: no
- Metrics, calibration, residuals, or subgroup errors calculated: no
- Scientific model classification made: no
- Model artifact serialized: no
- Production packaging, API, or frontend work performed: no

## 10. Evidence interpretation and next step

What the evidence proves: the first frozen request was attempted once; transport returned HTTP 200 without redirect; the exact response bytes were preserved; verification failed on the result-set-count rule; failure/quarantine records were written; and the remaining 59 requests were not attempted.

What it suggests: the verifier's response-envelope rule is narrower than the established TeamDashLineups payload shape. The body itself contains one named `Lineups` result set plus `Overall`, but R2B did not complete the row-level verification needed to promote it.

What remains a user decision: whether to authorize a new checkpoint after a read-only audit. The failed identity cannot be retried or repaired under this authorization.

What belongs to the next production checkpoint: audit the preserved failure, specify the allowed TeamDashLineups envelope exactly, correct and retest the verifier, freeze a new authorization that explicitly accounts for the spent first identity and its quarantined bytes, and decide whether a new request for that identity is permissible. No such work is authorized here.

What requires read-only audit: the six preserved R2B records and their hashes, the one-failed/59-not-started ledger classification, the implementation defect diagnosis, and the rule for handling the already-opened Atlanta Base evidence in any future checkpoint.

## 11. Final Git and cache state

HEAD remains `8d8f7f5fc6de31b81506091dff00b3e617e13232`; nothing was committed or pushed. The index remains clean. The working tree contains only intended R2B source/documentation/test/ignore changes. The ignored R2B planning namespace contains the authorization and official invocation record. The ignored protected cache contains one request directory with the immutable start, raw response, outcome, and quarantine records. No other cache namespace was inventoried or opened.
