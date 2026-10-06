# PASS — Phase 3F-R2A prior-profile dependencies acquired and verified

## Repository and authorization state

- Branch: `research/pair-fit-v2`
- Committed HEAD: `200a60036d095bf6a90483f3cdcfa3dd86f86f7c`
- Upstream: `origin/research/pair-fit-v2`
- Preflight ahead/behind: `0/0`
- Preflight index and working tree: clean
- R1S `acquisition_plan.json`: 64,477 bytes; SHA-256 `fd0db91ad876df39d13829ac7e11b920a24e5b394c9f025115a7db46010056c4`
- R1S `artifact_hashes.json`: 447 bytes; SHA-256 `7f3ddbc31665797b0c0acb24c49b9c47c2ddd0b31d92a1c98e8b39921e2ac347`
- R1S `summary.json`: 446 bytes; SHA-256 `81f16d12563aa36d1770f172dea1c090e1ed37da5d4c15744f132a9f1352f19b`
- R2A authorization: 10,220 bytes; SHA-256 `474d6debd597469cccfa2c950536529f4b9c0f9c274be23acf63fbb28c236ab6`

The preflight found neither exact dependency in the legacy exact-name cache, the R1S non-protected dependency namespace, nor the new R2A namespace. It found no incomplete, failed, quarantined, or contradictory R2A state. Both dependencies therefore began as `not_started`; neither was reacquired from an existing verified body.

The authorization record fingerprints 15 committed R0/R0.1/R1S inputs and 17 audited generated R0/R0.1/R1S inputs. It is write-once and contains exactly two request identities in this order:

1. `leaguedashplayerstats:2024-25:base:per100possessions`; canonical identity SHA-256 `d339d1d212e8175d72ff94ff6f1e97e483e4a17a6bcdd4d6c852c70ea657b3bd`.
2. `leaguedashplayerstats:2024-25:base:totals`; canonical identity SHA-256 `c817846e866f1db105d00ec5e4377bece8d50ce47374741f776a876fa3b9cff3`.

Both identities use endpoint `leaguedashplayerstats`, season `2024-25`, season type `Regular Season`, measure `Base`, `LeagueID=00`, blank `TeamID`, blank full-season date bounds, and the complete R1S parameter dictionary. They differ only at `PerMode`. No identity contains the protected season.

## Official invocation and attempts

The import-only canary passed once. The official command ran once from `C:\Users\mehan\code\hanson-hoops\research\pair-fit-v2` with `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe` and `PYTHONPATH=src`. The immutable invocation record is `planning/phase3f-r2a/official_invocation.json`.

| Request | Attempt | Start/outcome | HTTP | Rows | Bytes | Raw SHA-256 | Canonical JSON SHA-256 | Redirects / retries / quarantine |
|---|---:|---|---:|---:|---:|---|---|---|
| Base / Per100Possessions | 1 | `2026-10-01T01:42:36.662170Z` / `completed_verified` | 200 | 569 | 175,793 | `047d8c16703647425c2fa23678667595a6b7843b213e7e0c5794562bd96fc9ff` | `3651e4096775d485562bf181e4c89b74064c5dca3cde623de25581b31ed316a1` | none / 0 / none |
| Base / Totals | 1 | `2026-10-01T01:42:38.683652Z` / `completed_verified` | 200 | 569 | 173,315 | `3bd21076a2fde4b75ce70023f4c07cc633d811cfe08fce65a1c75bb653dfccd5` | `69d1ae9b2f388c95bab72a35703b438cf8cb7bbd05d33189137ab8a414edf7df` | none / 0 / none |

The second attempt started 1.002702 seconds after the first attempt's recorded completion. Each exact attempt body and its promoted verified body are byte-identical. No failure or quarantine file exists.

## Response and contract verification

Each response is strict JSON with exactly one `LeagueDashPlayerStats` result set, 69 unique columns, 569 correctly sized rows, 569 unique positive canonical player IDs, zero duplicate IDs, and zero malformed or nonpositive IDs.

Per100 contains every established source field required for the prior-profile contract: `PLAYER_ID`, `AGE`, `GP`, `FGM`, `FGA`, `FG3M`, `FG3A`, `FTM`, `FTA`, `OREB`, `DREB`, `AST`, `TOV`, `STL`, `BLK`, `BLKA`, `PF`, `PFD`, `PTS`, `PLUS_MINUS`, and `TEAM_COUNT`. All 569 `GP` values are finite and nonnegative.

Totals contains `PLAYER_ID` and `MIN`; all 569 `MIN` values are finite and nonnegative. Accordingly, Totals `MIN` can populate established `TOTAL_MIN` reliability metadata. `GP` and `TOTAL_MIN` remain reliability metadata, not estimator inputs.

The Per100 direct fields and the already frozen formulas for effective field-goal percentage, true-shooting percentage, three-point attempt rate, free-throw rate, and traded-player count cover the exact ordered 45 no-shot feature contract in the pinned R0 feature manifest. R2A verified schema availability and derivability only; it did not calculate row-level model inputs.

## Cross-source reconciliation

- Per100 unique players: 569
- Totals unique players: 569
- Intersection: 569
- Per100-only IDs: none
- Totals-only IDs: none
- Duplicate IDs: 0 in each source
- Malformed/nonpositive IDs: 0 in each source
- Observed ID-set equality: yes
- Material schema or identity discrepancies: none

Equality was observed rather than assumed. No population filtering or pair eligibility decision was made.

## Generated evidence

Deterministic planning/reconciliation outputs:

| File | Bytes | SHA-256 |
|---|---:|---|
| `authorization.json` | 10,220 | `474d6debd597469cccfa2c950536529f4b9c0f9c274be23acf63fbb28c236ab6` |
| `reconciliation.json` | 7,345 | `b0450dd143a8fb78b824bc14f6b447cf077864660c40cc4777fc55def93604e9` |
| `summary.json` | 3,157 | `6602ade04750c75353af472b8bc29167dc883fd6c7037a7dedba9c5b25d41ee9` |
| `artifact_hashes.json` | 561 | `81263f9f909c3c2e390099e9a6aaba56711b572039ac69eff91e199b25d72413` |

Invocation provenance:

| File | Bytes | SHA-256 |
|---|---:|---|
| `official_invocation.json` | 637 | `650bd6719d73dfadd09508476acef8678f47cb66f9b2f7aa0a7a7d50f919addd` |

The raw bodies, start/outcome records, promoted bodies, and verification records remain ignored under `cache/phase3f-r2a/non-protected-prior-profiles/`. Their complete inventory and hashes are recorded in `summary.json`; raw body identities are the raw SHA-256 values in the attempt table above.

## Tests and separation findings

- Focused R2A synthetic suite: 28 passed.
- Applicable prior-profile, Phase 2A/2B, Phase 3A/3A.1, Phase 3B, Phase 3F-R0/R0.1, and Phase 3F-R1S historical regressions: 55 passed.
- `py_compile`: passed for the R2A module, CLI, and tests.
- `git diff --check`: passed.
- Ignore checks: the R2A evidence and planning namespaces are ignored.
- Static capability scan: no estimator library, fitting, prediction, metric, or model-serialization operation exists in R2A.
- Synthetic protected-path test: rejected before filesystem access.
- Disposable R2A test directories: removed before official execution.

The authorization and immutable attempt inventory prove that R2A created exactly two real attempt-start/outcome pairs, both for the two allowed 2024–25 identities. The implementation records and reconciliation assert that no protected-season evidence was accessed. No protected request was marked started, completed, failed, or quarantined. No final-test target, pair population, availability evidence, or protected payload was acquired or opened.

No final-test dataset was constructed. No profile was imputed. No median or preprocessing state was learned. No estimator was loaded or fitted, no prediction or metric was calculated, and no model artifact was created.

## Disposition and next step

The evidence proves byte identity, successful schema verification, reliability-field validity, and complete cross-source player-ID agreement for these two league-wide dependencies. It supports treating the 2024–25 prior-profile dependency checkpoint as complete. It does not prove readiness of any protected final-test target or authorize final-test construction or execution.

The narrowest next step is a separate read-only audit of this R2A checkpoint and its ignored evidence. Any later protected acquisition, readiness work, final-test construction, or model execution remains a user decision requiring its own authorization boundary.

Final Git state remains on the expected HEAD and upstream at `0/0`, with an empty index. The worktree contains only the intended `.gitignore` modification and the five untracked commit-eligible R2A policy, report, module, CLI, and test files. The ignored R2A state contains five planning/provenance files and ten evidence files. Both request states are `completed_verified`; no quarantine file exists. Raw responses and attempt records remain outside the proposed commit.

No commit or push was performed.
