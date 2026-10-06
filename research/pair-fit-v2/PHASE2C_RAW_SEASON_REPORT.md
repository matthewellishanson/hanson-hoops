# Phase 2C: 2022-23 raw-season acquisition and release audit

## Decision

Primary classification: **`2022-23 raw release supported with population caveats; next historical phase ready for separate authorization`**.

Phase 2C completed its exact 62-asset request set: two league-wide 2021-22 `LeagueDashPlayerStats` Base assets and Base/Advanced `TeamDashLineups` pair assets for all 30 teams in 2022-23. All assets verified against frozen schemas without coercion. The result is a complete request set, not proof that every observable pair was returned by the endpoint.

Starting repository state was clean branch `research/pair-fit-v2` at commit `7aa626c3d90d4b14d30e3a24cde820377c8d905c` (`Completed Phase 2B checkpoint with full 2023-24 raw request set verified and completed.`). No commit was created in this phase.

## Offline safety correction (2026-09-04)

A bounded post-acquisition review corrected three safety defects without changing acquisition evidence:

1. The acquisition runner now reconciles every gate implied by the verified asset prefix before selecting transport and after each cache promotion. It recreates or validates the player-source gate, audits and records each completed Base/Advanced team gate, and recreates or validates the canary gate. A cache failure or persisted/derived disagreement creates a restart-persistent integrity stop before session construction or another request.
2. Final analysis now recomputes the canary from verified caches through the same `_canary_audit` function and requires exact agreement with the persisted result, including its deterministic hash, team counts, player count, and coverage counts. Missing or stale certification produces the unresolved release classification rather than trusting `status="passed"`.
3. During normal operation, each returned body that is not promoted to verified raw cache is preserved at an immutable attempt-specific path with byte count and raw SHA-256 linked from the attempt event. This covers retryable and nonretryable HTTP responses, invalid JSON, validation failures, and schema rejection. The normal evidence path is checked before attempt recording or transport selection. If that path appears after the check, the returned body uses an immutable path derived from the request identity, attempt number, and body SHA-256; acquisition then persists an integrity stop without retrying or advancing. A contradictory pre-existing file at that content-addressed path is handled separately as terminal evidence-directory corruption, as described below.

The alternate-cache regression now changes to an unrelated working directory and invokes `run_acquisition(..., transport=None)` on a nondefault temporary `Phase2CStore`. Only `requests.Session` is stubbed. This exercises the real acquisition-to-`direct_transport` path and proves that the selected store's inventory and allowlist reach the adapter before a controlled response stops the run. Direct unauthorized identities continue to be rejected before session construction.

The corrected analysis replays the existing 62 assets twice with networking blocked. The persisted and recomputed canary results agree exactly at canary SHA-256 `912e2951407aca5114033cf2e860d7d0259ab164966fd175a110a8ba35a934d8`, so the reported 4,805-row release remains supported. The deterministic analysis hash changed from pre-correction `c0da5d2d16e1ae8f240f1f7ddf6e52797f63fe0d4fa12e07373b417eff086075` to corrected `a644c47dd6940ac3ab0ccc438ed9a93c852d325fb11484679d1e341d66708ad0` because the summary now includes persisted/recomputed canary evidence and certification status.

All original acquisition evidence remained byte-identical across the correction. Each raw asset remains individually reproducible from its manifest-recorded SHA-256 and byte count, and each metadata file records its asset identity and provenance. No raw-response or metadata aggregate digest is claimed because the project has no canonical, documented aggregation recipe.

| Protected evidence | Before and after SHA-256 |
|---|---|
| Manifest | `cce7150e0aa0a4c0278c34d8f20bed0b534bc02ef65c61031c65b03fd786ed0d` |
| Attempt ledger | `eb4d3fcbf9f0e00104c903ec6f2f8f80c9fb716724d7a469a66d81a0e45eb58e` |
| Initial plan | `34e83472985fa0cbc0ad97cbbad84807823913c42bb4229ff58338af02302bb1` |
| Live allowlist | `5dc463bca66df58cec746451f38567d72ec0ec40aca71bc80f3ac534c0bdd572` |

Focused correction tests: 30 passed. Complete offline research suite: 268 passed. Both runs emitted only the known warning that the optional pre-existing `.pytest_cache` is inaccessible; it was not altered. Mutable test state was confined to task-local temporary directories.

## Final failure-evidence correction (2026-09-05)

The failure-evidence collision guard now runs before the next attempt is recorded, before transport is selected, and before an HTTP session can be constructed. A pre-existing normal attempt-specific evidence path leaves the asset planned, consumes no attempt, preserves the existing bytes, and creates a restart-persistent `failure_evidence_preflight_collision` stop containing the asset ID, prospective attempt number, and relative conflicting path.

The create-once write remains in the response-preservation path as protection against a filesystem race after preflight. If the normal path appears after a response returns, normal immutable preservation uses a separate content-addressed collision path. An already-present content-addressed path is safely reused only when its bytes exactly match the returned body. In both cases, the attempt event links the actual preserved path, byte count, and raw SHA-256; a `failure_evidence_postcheck_collision` integrity stop prevents retry or progression. Failure evidence remains separate from verified raw assets.

If a pre-existing content-addressed path contains different bytes, its filename contradicts its content. The runner does not overwrite either existing file and does not create a tertiary fallback. Instead, the attempt event and restart-persistent `failure_evidence_content_address_mismatch` stop record the returned body's expected SHA-256 and byte count, its intended path, and the conflicting file's actual SHA-256. The stop states explicitly that the returned bytes could not be persisted because the existing evidence contradicted the content-addressed filename. No such collision or evidence-directory corruption occurred during the actual Phase 2C acquisition.

Regression coverage now includes the pre-transport collision, successful post-check content-addressed preservation, safe reuse of byte-identical content-addressed evidence, and the terminal contradictory-content case, alongside the existing retryable, nonretryable, invalid-JSON, validation, and schema-rejection preservation cases. Focused Phase 2C tests: 33 passed. Complete offline research suite: 271 passed. Two network-blocked cache-only analyses remained identical at deterministic SHA-256 `a644c47dd6940ac3ab0ccc438ed9a93c852d325fb11484679d1e341d66708ad0`; both certified the canary and reconciled 4,805 observations. All mutable regression state uses isolated task-local temporary directories.

## Prerequisite replay and plan

Networking was blocked while the completed Phase 2B release was replayed twice. Both analyses reproduced 60 verified pair assets, 5,207 matched observations, 5,190 positive-possession rows, 17 preserved zero-possession rows, and prior-history categories 3,514 complete / 1,490 one missing / 203 both missing.

| Protected Phase 2B artifact | SHA-256 |
|---|---|
| Completed manifest | `af8acbc10adf110f43c7c53a0ab2d6b402e3121fbe57e2d8b5dc3de7072e689e` |
| Completed ledger | `d298f15316dec37cfb3efe6fb9f1451cb3052ed7a1f0b603ce0a4d6057f62dcb` |
| Deterministic analysis | `00f4324311368184d1c184be89d23b866551678b3715c262e76b36f459e24b82` |

The read-only preview contained exactly 62 identities and zero network calls. Its order was: player Per100Possessions, player Totals, Golden State Base/Advanced, Boston Base/Advanced, Washington Base/Advanced, Brooklyn Base/Advanced, Charlotte Base/Advanced, then the other 25 teams in the frozen numeric team-directory order with Base before Advanced. The create-once initial-plan hash is `34e83472985fa0cbc0ad97cbbad84807823913c42bb4229ff58338af02302bb1`; the allowlist hash is `5dc463bca66df58cec746451f38567d72ec0ec40aca71bc80f3ac534c0bdd572`.

## Acquisition accounting and provenance

| Item | Result |
|---|---:|
| Planned identities | 62 |
| Existing exact assets reused | 0 |
| First attempts | 62 |
| Retry attempts | 0 of 6 authorized |
| Total attempts / ceiling | 62 / 68 |
| Actual HTTP responses | 62 |
| HTTP 200 and verified | 62 |
| Failed / quarantined / skipped | 0 / 0 / 0 |

Requests ran sequentially through the direct `requests.Session` path with `trust_env=False`, the existing research headers, 30-second timeout, redirects disabled, zero adapter retries, and at least one second between first attempts. Total reported request latency was 116.147 seconds (minimum 1.426, median 1.841, maximum 3.261). Raw response bytes totaled 2,916,034 (range 29,548–186,620). The Git-ignored manifest is the complete per-asset request ledger: it records each exact normalized identity, ordinal, attempt, latency, response/cache byte count, raw hash, canonical hash, schema fingerprints, metadata path, and transition history.

Current state hashes:

| Artifact | SHA-256 |
|---|---|
| Phase 2C manifest | `cce7150e0aa0a4c0278c34d8f20bed0b534bc02ef65c61031c65b03fd786ed0d` |
| Phase 2C attempt ledger | `eb4d3fcbf9f0e00104c903ec6f2f8f80c9fb716724d7a469a66d81a0e45eb58e` |
| Corrected deterministic release analysis | `a644c47dd6940ac3ab0ccc438ed9a93c852d325fb11484679d1e341d66708ad0` |

## Canary decision

The first 12 assets verified before continuation. Both player modes returned 605 unique positive canonical IDs, no duplicates, and exactly equal ID sets. The five team pairs reconciled 792 observations: Golden State 132, Boston 127, Washington 180, Brooklyn 209, and Charlotte 144. Prior-history categories were 535 complete, 232 one missing, and 25 both missing; complete-history rows represented 88.30% of summed canary pair possessions. No coverage percentage was used as an acceptance threshold. The persisted canary classification is `passed`, so acquisition continued automatically.

## Schemas, identities, and targets

All 60 pair responses matched approved schema contract `schema-contract:cf262e22edf0272f5fe53293` exactly. Both player responses matched reviewed 69-column schema `phase2a.player-base.v2` / `schema-contract:a39b5a33c328fd9c467ff8d6` exactly. There were zero malformed pair IDs, same-player IDs, duplicate full observation keys, Base-only keys, or Advanced-only keys. Seventy player IDs and nine unordered pair IDs appeared for multiple teams; these are legitimate distinct team-season observations and were not deduplicated across teams.

The release contains 4,805 Base rows and 4,805 Advanced rows, forming 4,805 one-to-one full observation keys. Direct standard and estimated net-rating identities had zero positive-possession failures under the established displayed-rounding tolerance. Of these rows, 4,785 have positive `POSS`; 20 `POSS=0` rows remain preserved and explicitly target-ineligible. No positive exposure threshold was applied.

## Team and population audit

| Team | Rows | Players | Theoretical / absent | Base MIN min | POSS min | Ineligible | Prior complete / one / both | Complete prior POSS share | Boundary |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Atlanta | 153 | 20 | 190 / 37 | 0.116667 | 0 | 2 | 119 / 32 / 2 | 85.2% | none |
| Boston | 127 | 18 | 153 / 26 | 0.316667 | 0 | 1 | 92 / 32 / 3 | 97.4% | none |
| Cleveland | 131 | 18 | 153 / 22 | 0.023333 | 1 | 0 | 118 / 13 / 0 | 99.2% | none |
| New Orleans | 124 | 17 | 136 / 12 | 0.533333 | 1 | 0 | 88 / 34 / 2 | 80.0% | none |
| Chicago | 120 | 18 | 153 / 33 | 0.033333 | 0 | 1 | 103 / 17 / 0 | 97.8% | none |
| Dallas | 200 | 23 | 253 / 53 | 0.111667 | 0 | 1 | 158 / 40 / 2 | 91.6% | none |
| Denver | 140 | 18 | 153 / 13 | 0.028333 | 0 | 1 | 85 / 50 / 5 | 65.4% | none |
| Golden State | 132 | 18 | 153 / 21 | 0.683333 | 2 | 0 | 88 / 40 / 4 | 94.5% | none |
| Houston | 131 | 18 | 153 / 22 | 0.015000 | 1 | 0 | 72 / 50 / 9 | 55.0% | none |
| LA Clippers | 165 | 21 | 210 / 45 | 1.450000 | 3 | 0 | 108 / 53 / 4 | 72.2% | none |
| LA Lakers | 196 | 24 | 276 / 80 | 0.100000 | 0 | 1 | 140 / 50 / 6 | 89.3% | none |
| Miami | 161 | 20 | 190 / 29 | 0.010000 | 0 | 1 | 98 / 57 / 6 | 90.2% | none |
| Milwaukee | 187 | 21 | 210 / 23 | 0.163333 | 0 | 2 | 136 / 48 / 3 | 88.8% | none |
| Minnesota | 162 | 20 | 190 / 28 | 0.016667 | 0 | 2 | 127 / 34 / 1 | 97.5% | none |
| Brooklyn | 209 | 25 | 300 / 91 | 0.000000 | 0 | 3 | 133 / 69 / 7 | 75.8% | none |
| New York | 113 | 17 | 136 / 23 | 0.481667 | 1 | 0 | 107 / 6 / 0 | 99.9% | none |
| Orlando | 162 | 20 | 190 / 28 | 1.216667 | 3 | 0 | 93 / 62 / 7 | 62.8% | none |
| Indiana | 159 | 20 | 190 / 31 | 1.550000 | 2 | 0 | 113 / 43 / 3 | 58.4% | none |
| Philadelphia | 146 | 21 | 210 / 64 | 0.073333 | 0 | 3 | 135 / 10 / 1 | 99.9% | none |
| Phoenix | 172 | 20 | 190 / 18 | 0.036667 | 1 | 0 | 142 / 30 / 0 | 92.6% | none |
| Portland | 186 | 24 | 276 / 90 | 0.038333 | 0 | 1 | 110 / 61 / 15 | 73.3% | none |
| Sacramento | 168 | 20 | 190 / 22 | 0.048333 | 1 | 0 | 99 / 60 / 9 | 73.5% | none |
| San Antonio | 215 | 23 | 253 / 38 | 1.500000 | 4 | 0 | 119 / 83 / 13 | 59.1% | none |
| Oklahoma City | 156 | 19 | 171 / 15 | 0.048333 | 1 | 0 | 95 / 55 / 6 | 62.4% | none |
| Toronto | 159 | 20 | 190 / 31 | 0.166667 | 0 | 1 | 131 / 27 / 1 | 91.4% | none |
| Utah | 189 | 23 | 253 / 64 | 0.100000 | 1 | 0 | 98 / 77 / 14 | 62.2% | none |
| Memphis | 142 | 19 | 171 / 29 | 1.498333 | 3 | 0 | 74 / 55 / 13 | 79.7% | none |
| Washington | 180 | 23 | 253 / 73 | 0.266667 | 1 | 0 | 119 / 53 / 8 | 89.6% | none |
| Detroit | 176 | 22 | 231 / 55 | 0.733333 | 2 | 0 | 99 / 66 / 11 | 55.7% | none |
| Charlotte | 144 | 19 | 171 / 27 | 0.933333 | 3 | 0 | 103 / 38 / 3 | 84.0% | none |

No team returned exactly 250 rows in 2022-23, so this release is classified `no_boundary_signal_observed`. The theoretical-pair differences do not establish omissions because theoretical combinations need not share the court. Prior Toronto/Memphis/Detroit 2023-24 boundary signals and the proven Charlotte 2024-25 omission remain relevant risk context, not evidence about this season. Global population exhaustiveness remains unproven.

League-wide Base minutes range from 0 to 2,235.623 (p25 29.717, median 107.650, p75 314.680, p90 680.930); summed overlapping pair minutes are 1,189,698.667. Possessions range from 0 to 4,637 (p25 64, median 232, p75 673, p90 1,447.6); summed overlapping pair possessions are 2,522,079.

| POSS at least | Rows | Row share | Summed-POSS share | `abs(NET)>=50` | `abs(NET)>=100` |
|---:|---:|---:|---:|---:|---:|
| 1 | 4,785 | 99.58% | 100.000% | 295 | 86 |
| 5 | 4,660 | 96.98% | 99.987% | 202 | 32 |
| 10 | 4,518 | 94.03% | 99.948% | 138 | 6 |
| 25 | 4,202 | 87.45% | 99.742% | 42 | 1 |
| 50 | 3,794 | 78.96% | 99.154% | 9 | 0 |
| 100 | 3,256 | 67.76% | 97.617% | 0 | 0 |
| 200 | 2,558 | 53.24% | 93.606% | 0 | 0 |
| 300 | 2,141 | 44.56% | 89.542% | 0 | 0 |

This is descriptive only. It does not select a target, threshold, weighting policy, or feature. Pair exposures overlap and are not independent NBA possession counts.

## Prior-player audit

The two 2021-22 player modes each returned 605 rows, 605 unique strict IDs, no missing/malformed IDs, no duplicates, and identical ID sets. `Totals MIN` ranges from 0.843 to 2,854.353 minutes (median 883.228); the leaders include Mikal Bridges (2,854.353), Miles Bridges (2,837.113), DeMar DeRozan (2,742.948), and Jayson Tatum (2,730.972). Per100Possessions `MIN` ranges from 33.1 to 64.0 and is therefore a rate-normalized field, not season-total playing time. The Totals distribution and high-minute records support the classification `consistent_with_season_total_minutes`; no eligibility threshold was selected.

Across 539 unique pair-population players, 433 have a 2021-22 player record and 106 do not. Absence is recorded factually as `no_2021-22_source_record`, without inferring rookie, retirement, inactivity, or error.

| Coverage category | Pair rows | Share | Summed Base MIN | MIN share | Summed POSS | POSS share |
|---|---:|---:|---:|---:|---:|---:|
| Complete | 3,302 | 68.72% | 962,685.932 | 80.92% | 2,036,355 | 80.74% |
| One missing | 1,345 | 27.99% | 212,459.670 | 17.86% | 454,337 | 18.01% |
| Both missing | 158 | 3.29% | 14,553.065 | 1.22% | 31,387 | 1.24% |

Compared descriptively with 2023-24, complete-pair coverage is slightly higher (68.72% versus 67.49%) while complete-history summed-possession share is lower (80.74% versus 82.22%). Season labels remain separate; one season does not repair another season's absences.

## Decision answers and limitations

1. The approved acquisition contract operated one season earlier without schema coercion.
2. All pair identities and Base/Advanced joins are structurally valid across 30 teams.
3. Direct standard and estimated rating fields are available and internally coherent for every positive-possession row.
4. Twenty zero-possession rows are preserved and target-ineligible; no missing, nonnumeric, or negative possessions were accepted.
5. No exact-250 boundary signal appears, but population exhaustiveness remains unproven.
6. The 2021-22 prior-player sources join strictly by ID with the required one-season lag and no same-season leakage.
7. Prior-history coverage is measured, variable by team, and descriptive; missing-history policy remains deferred.
8. Totals `MIN` behaves consistently with season-total minutes; Per100Possessions `MIN` has different units.
9. Create-once plans, allowlists, immutable raw writes, attempt-before-transport events, cache replay, persistent stops, and cumulative budgets operated successfully.
10. No schema or integrity anomaly blocks release. Population exhaustiveness and low-exposure reliability remain caveats.
11. The evidence supports the raw release and permits a separately authorized next historical phase; it does not itself authorize it.
12. Next work may acquire 2021-22 pair outcomes with 2020-21 prior-player inputs only under separate authorization. It should preserve this contract and avoid curation, threshold/feature selection, imputation, interaction design, and modeling. Formal learning checkpoints remain deferred. Organizational agentic-workflow standards are deferred until before NBA database work.

Maintainability note: the next separately authorized historical season should reuse a configurable acquisition state machine rather than copy the full Phase 2C module. That extraction is intentionally deferred; this correction did not introduce a generic framework or broad refactor.

No 2025-26 data, other target/prior seasons, date windows, alternate endpoints, databases, Parquet/Feather, curated datasets, thresholds, features, validation splits, models, production code, secrets, or environment configuration were accessed or created.
