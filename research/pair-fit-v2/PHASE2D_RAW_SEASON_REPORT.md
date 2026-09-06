# Phase 2D: 2021-22 raw-season acquisition and release audit

## Decision

Primary classification: **`2021-22 raw release supported with population caveats; older historical expansion ready for separate planning`**.

The configured historical acquisition state machine completed the exact 62-asset Phase 2D request set: two league-wide 2020-21 player sources and Base/Advanced pair responses for all 30 teams in 2021-22. All 62 assets verified on their first attempt against the approved schemas. The release contains 5,745 one-to-one Base/Advanced observations. This is complete request-set evidence, not proof that the endpoint returned every observable pair.

Successful Phase 2D completion means three training target seasons have been acquired: 2021-22, 2022-23, and 2023-24. It does not mean the amended 2014-15 through 2023-24 training window is complete.

## Starting state and immutable replay

The repository started clean on branch `research/pair-fit-v2` at `09df63e18dd7678bbc26ef4956c083336e2ca706` (`Phase 2C completed and audited, with full acquisition and verification of assets for the 2022-23 season.`). The complete baseline research suite passed with 271 tests. Networking was blocked while prerequisites replayed.

Phase 2C reproduced 62 verified assets, 4,805 matched observations, a certified canary, and deterministic analysis SHA-256 `a644c47dd6940ac3ab0ccc438ed9a93c852d325fb11484679d1e341d66708ad0`. Its manifest, ledger, plan, and allowlist hashes remained respectively `cce7150e0aa0a4c0278c34d8f20bed0b534bc02ef65c61031c65b03fd786ed0d`, `eb4d3fcbf9f0e00104c903ec6f2f8f80c9fb716724d7a469a66d81a0e45eb58e`, `34e83472985fa0cbc0ad97cbbad84807823913c42bb4229ff58338af02302bb1`, and `5dc463bca66df58cec746451f38567d72ec0ec40aca71bc80f3ac534c0bdd572`. Phase 2B reproduced 5,207 matched observations and deterministic analysis SHA-256 `00f4324311368184d1c184be89d23b866551678b3715c262e76b36f459e24b82`; its existing prerequisite checks also protect the Phase 1 anchors.

## Configured reuse and plan

The existing Phase 2C state machine now accepts an immutable `HistoricalSeasonSpec`. Phase 2C remains its unchanged default configuration and reproduces its existing manifest, ledger, plan, allowlist, CLI behavior, and analysis hash. Phase 2D supplies only its target/prior seasons, release namespace, evidence paths and versions, classification labels, canary boundary, and unchanged 62/6/68 authorization.

The Phase 2D preview was read-only and showed exactly 62 unique identities in deterministic order: 2020-21 player Per100Possessions and Totals, followed by Base/Advanced for the five established canary teams, followed by Base/Advanced for the remaining 25 teams in the approved directory order. It created no older-season identity. The persisted plan and allowlist are create-once and release-isolated under `phase2d/`.

| Implementation artifact | Bytes | Lines | Role |
|---|---:|---:|---|
| `phase2c_raw_season.py` | 82,772 | 1,718 | Shared configured engine; Phase 2C-compatible default |
| `phase2c_cli.py` | 1,565 | 47 | Existing Phase 2C CLI wrapper |
| `phase2d_raw_season.py` | 1,989 | 64 | Immutable Phase 2D specification and thin API |
| `phase2d_cli.py` | 1,586 | 49 | Thin Phase 2D CLI |

No acquisition runner, transport, store, gate, cache, failure-evidence, or analysis implementation was copied into Phase 2D. The only structural duplication is the 49-line CLI argument/dispatch surface. The legacy engine filename remains a maintainability blemish, but is not a safety obstacle: its state and behavior are specification-driven. Before a seven-season Phase 2E, the safest bounded follow-up is to move this already-configured engine to a neutral module name with behavior-preservation tests, not copy it seven times.

## Acquisition accounting

| Item | Result |
|---|---:|
| Planned identities | 62 |
| Existing exact assets reused | 0 |
| First attempts | 62 |
| Retry attempts | 0 of 6 authorized |
| Total attempts / ceiling | 62 / 68 |
| Actual HTTP responses | 62 |
| HTTP 200 and verified | 62 |
| Failed / quarantined / unattempted | 0 / 0 / 0 |

Requests were sequential through the existing direct `requests.Session` path with `trust_env=False`, established research headers, 30-second timeout, redirects disabled, no adapter retries, and at least one second between ordinary requests. Total response latency was 108.505 seconds (minimum 1.380, median 1.712, maximum 3.049). Response and verified-cache bytes were both 3,350,394 because unchanged response bytes were promoted (range 33,591 to 166,720). The ignored manifest is the complete per-asset identity, status, latency, byte-count, hash, schema, provenance, and attempt ledger.

### Provenance-label correction

All 62 persisted Phase 2D attempt events contain the incorrect `request_kind="phase2c_live"` label. The defect came from a Phase 2C label hardcoded in the shared acquisition runner. The completed manifest and attempt ledger are preserved byte-for-byte as historical evidence; no request was repeated and no acquisition evidence was rewritten.

Independent evidence establishes that these were Phase 2D requests: each normalized request identity names the approved 2021-22 target or 2020-21 prior-player season, each cache destination is in the Phase 2D namespace, the bounded Phase 2D authorization covers the exact identities, response metadata repeats those identities, source provenance uses `phase2d-live-v1`, and the accepted schemas and raw/canonical hashes validate against the Phase 2D contract. The incorrect attempt-event label therefore does not invalidate the 62 verified responses or the 5,745-row release.

The shared runner now obtains `request_kind` from an explicit, validated immutable season specification. Phase 2C supplies `phase2c_live`; Phase 2D supplies `phase2d_live`. This source correction applies to future configured attempts only and does not imply that the preserved Phase 2D events originally contained the corrected value.

## Canary

The first 12 assets passed and continuation proceeded automatically. Both player modes returned the same 540 unique positive player IDs with no malformed or duplicate IDs. The five canary teams reconciled 895 observations: Golden State 126, Boston 200, Washington 231, Brooklyn 201, and Charlotte 137. The canary preserved three zero-possession observations.

| Prior-history category | Rows | Share | Summed pair possessions | Possession share |
|---|---:|---:|---:|---:|
| Complete | 579 | 64.69% | 350,428 | 84.11% |
| One missing | 274 | 30.61% | 61,024 | 14.65% |
| Both missing | 42 | 4.69% | 5,176 | 1.24% |

The persisted and cache-recomputed canary agree exactly at SHA-256 `2b26c6ec26dce7a727b944c2819476521e9cb641b2909f036f0a49ffe97e5835`.

## Schemas, identities, and targets

All pair responses matched `schema-contract:cf262e22edf0272f5fe53293` exactly. Both player responses matched reviewed 69-column schema `phase2a.player-base.v2` / `schema-contract:a39b5a33c328fd9c467ff8d6`. There were zero malformed pair identifiers, duplicate canonical keys, Base-only keys, Advanced-only keys, standard-rating identity failures, or estimated-rating identity failures.

The release has 5,745 Base rows and 5,745 Advanced rows forming 5,745 matched observation keys. Of those, 5,723 have positive possessions and 22 valid zero-possession rows are preserved as target-ineligible. The 605 observed pair players form 5,725 globally unique unordered player pairs; 97 players and 20 pair identities appear for multiple teams and remain distinct team-season observations.

Base minutes range from 0 to 2,001.3483 (quartiles 15.6667 / 78.7833 / 258.9050; total summed pair minutes 1,187,486). Possessions range from 0 to 4,220 (quartiles 34 / 167 / 544; total summed pair possessions 2,496,940). These overlapping pair exposures are not independent NBA minute or possession counts.

## Team and endpoint-population audit

| Team | Rows | Players | Theoretical / absent | Zero POSS | Base MIN min | POSS min |
|---|---:|---:|---:|---:|---:|---:|
| Atlanta | 205 | 24 | 276 / 71 | 0 | 0.436667 | 1 |
| Boston | 200 | 28 | 378 / 178 | 1 | 0.083333 | 0 |
| Cleveland | 220 | 26 | 325 / 105 | 1 | 0.016667 | 0 |
| New Orleans | 179 | 22 | 231 / 52 | 0 | 0.550000 | 2 |
| Chicago | 179 | 22 | 231 / 52 | 1 | 0.005000 | 0 |
| Dallas | 234 | 27 | 351 / 117 | 0 | 0.183333 | 1 |
| Denver | 172 | 22 | 231 / 59 | 1 | 0.233333 | 0 |
| Golden State | 126 | 17 | 136 / 10 | 0 | 2.100000 | 3 |
| Houston | 150 | 19 | 171 / 21 | 0 | 1.366667 | 3 |
| LA Clippers | 184 | 23 | 253 / 69 | 1 | 0.033333 | 0 |
| Los Angeles Lakers | 207 | 25 | 300 / 93 | 0 | 0.923333 | 2 |
| Miami | 175 | 22 | 231 / 56 | 1 | 0.000000 | 0 |
| Milwaukee | 249 | 29 | 406 / 157 | 1 | 0.033333 | 0 |
| Minnesota | 130 | 18 | 153 / 23 | 0 | 0.616667 | 2 |
| Brooklyn | 201 | 24 | 276 / 75 | 0 | 0.035000 | 2 |
| New York | 162 | 23 | 253 / 91 | 0 | 0.973333 | 2 |
| Orlando | 189 | 22 | 231 / 42 | 0 | 1.150000 | 2 |
| Indiana | 233 | 28 | 378 / 145 | 0 | 0.843333 | 2 |
| Philadelphia | 171 | 23 | 253 / 82 | 1 | 0.013333 | 0 |
| Phoenix | 177 | 23 | 253 / 76 | 0 | 0.010000 | 1 |
| Portland | 226 | 27 | 351 / 125 | 0 | 0.283333 | 1 |
| Sacramento | 214 | 26 | 325 / 111 | 2 | 0.003333 | 0 |
| San Antonio | 196 | 24 | 276 / 80 | 0 | 0.090000 | 1 |
| Oklahoma City | 224 | 26 | 325 / 101 | 1 | 0.015000 | 0 |
| Toronto | 169 | 23 | 253 / 84 | 0 | 0.438333 | 1 |
| Utah | 196 | 24 | 276 / 80 | 5 | 0.028333 | 0 |
| Memphis | 176 | 23 | 253 / 77 | 4 | 0.066667 | 0 |
| Washington | 231 | 29 | 406 / 175 | 2 | 0.006667 | 0 |
| Detroit | 233 | 27 | 351 / 118 | 0 | 0.483333 | 2 |
| Charlotte | 137 | 19 | 171 / 34 | 0 | 0.066667 | 1 |

No team returned exactly 250 rows, so no exact-250 boundary signal was observed in this release. Milwaukee returned 249. Theoretical combinations include pairs that may never have shared the court and do not establish omissions. Population exhaustiveness remains `not_proven_exhaustive`; earlier boundary and omission evidence remains separate season-specific risk context.

## Prior-player sources and coverage

Both 2020-21 player modes contain 540 unique positive IDs, no missing/malformed/duplicate IDs, and exactly equal ID sets. Totals `MIN` is numeric and nonnegative, ranges from 2.6717 to 2,666.7367, and has median 925.5825; high-minute records include Julius Randle (2,666.7367), RJ Barrett (2,510.8817), and Nikola Jokic (2,487.7817). Per100Possessions `MIN` ranges from 38.7 to 49.9 with median 47.4. This remains consistent with season-total minutes versus rate-normalized minutes; no threshold or feature use was selected.

| Coverage category | Rows | Row share | Summed Base minutes | Minute share | Summed POSS | POSS share |
|---|---:|---:|---:|---:|---:|---:|
| Complete | 3,592 | 62.52% | 942,389.6833 | 79.36% | 1,979,045 | 79.26% |
| One missing | 1,865 | 32.46% | 223,251.9467 | 18.80% | 471,477 | 18.88% |
| Both missing | 288 | 5.01% | 21,844.3700 | 1.84% | 46,418 | 1.86% |

The pair population contains 605 unique player IDs, of which 450 have a 2020-21 source row and 155 do not (74.38% player-level coverage). Absence is reported factually and is not interpreted as rookie, retirement, inactivity, or error. All rows remain preserved; no imputation or missing-history policy was applied.

Deduplicated absent-ID ledger (names, affected teams, pair counts, and overlapping exposure remain in the deterministic audit): `101139, 1626144, 1626147, 1626155, 1626208, 1627760, 1627767, 1627782, 1627820, 1627822, 1628221, 1628238, 1628380, 1628432, 1628476, 1628537, 1628591, 1628982, 1628994, 1629005, 1629083, 1629111, 1629150, 1629168, 1629203, 1629309, 1629312, 1629597, 1629600, 1629602, 1629619, 1629623, 1629646, 1629656, 1629674, 1629678, 1629755, 1629760, 1629783, 1629788, 1629873, 1629875, 1629958, 1630195, 1630209, 1630215, 1630224, 1630225, 1630227, 1630228, 1630243, 1630245, 1630249, 1630250, 1630257, 1630270, 1630278, 1630285, 1630286, 1630288, 1630296, 1630306, 1630314, 1630322, 1630346, 1630525, 1630526, 1630527, 1630528, 1630529, 1630530, 1630531, 1630532, 1630533, 1630535, 1630536, 1630537, 1630538, 1630539, 1630540, 1630541, 1630543, 1630544, 1630547, 1630549, 1630550, 1630551, 1630552, 1630553, 1630555, 1630556, 1630557, 1630558, 1630559, 1630560, 1630561, 1630563, 1630565, 1630567, 1630568, 1630570, 1630572, 1630573, 1630575, 1630578, 1630579, 1630580, 1630581, 1630582, 1630583, 1630585, 1630586, 1630587, 1630589, 1630591, 1630593, 1630595, 1630596, 1630598, 1630602, 1630605, 1630606, 1630610, 1630612, 1630613, 1630624, 1630625, 1630631, 1630637, 1630640, 1630643, 1630644, 1630647, 1630648, 1630678, 1630686, 1630688, 1630691, 1630692, 1630693, 1630695, 1630698, 1630758, 1630787, 1630792, 1630846, 1630994, 201954, 202328, 202362, 202688, 202691, 203816, 203917, 2207`.

## Exposure description

| POSS at least | Rows | Row share | Summed pair POSS share | |NET| >= 50 | |NET| >= 100 |
|---:|---:|---:|---:|---:|---:|
| 1 | 5,723 | 99.62% | 100.00% | 559 | 160 |
| 5 | 5,517 | 96.03% | 99.98% | 429 | 79 |
| 10 | 5,192 | 90.37% | 99.89% | 257 | 12 |
| 25 | 4,575 | 79.63% | 99.48% | 90 | 0 |
| 50 | 4,000 | 69.63% | 98.67% | 18 | 0 |
| 100 | 3,406 | 59.29% | 96.98% | 1 | 0 |
| 200 | 2,651 | 46.14% | 92.52% | 0 | 0 |
| 300 | 2,185 | 38.03% | 87.88% | 0 | 0 |

This is descriptive reliability context only. No exposure threshold was selected and no row was filtered.

## Reproducibility and next phase

Two independently constructed cache-only analyses with `requests.Session` blocked were exactly identical. Deterministic analysis SHA-256 is `6b231f4d413d87d8e31bc92fa442ebf9e05587ea8dec9e876dba7cb21fed566f`. Current manifest SHA-256 is `0280fcccd8ddb57cfa1f0c2feeccefb815136a576dc672a28c2141bdb27f5015`; ledger SHA-256 is `19549243c95bfb00e7ac30a111cc8486909a078d7941ad4267609bbdc1a89266`; plan SHA-256 is `525f872009283d6a7b11ca31d392a8a84ec5f718cdbddb43b4182e91619b9906`; allowlist SHA-256 is `8ee84a9dc1d600e68326937595a08da584ca0b1941216a88e741ee612a4fef0a`. Every one of the 62 raw payloads retains its individual byte count, raw SHA-256, and canonical JSON hash, and every corresponding metadata record retains its identity and provenance validation evidence.

Phase 2E requires separate authorization and planning. The amended future target/prior pairs are 2020-21/2019-20, 2019-20/2018-19, 2018-19/2017-18, 2017-18/2016-17, 2016-17/2015-16, 2015-16/2014-15, and 2014-15/2013-14. A safe Phase 2E should keep one manifest/ledger and canary boundary per season, continue automatically only after each successful season gate, and stop on the first substantive schema or integrity anomaly. This is a future plan, not current acquisition authority.

The main risk before a seven-season run is not duplicated acquisition logic—the runner is configured—but the possibility of older endpoint/schema behavior changing at a season boundary. Phase 2E should therefore retain frozen-schema quarantine, immutable response evidence, cumulative per-season budgets, and explicit restart gates. Curation, threshold selection, missing-history policy, database work, and modeling remain separate and unauthorized.

## Verification

After the provenance correction, Phase 2C behavior preservation and focused Phase 2D tests passed together: 43 passed. The complete offline research suite passed: 281 passed. The only warnings were the known inaccessible optional `.pytest_cache`, which was not modified. Two cache-only analyses for each of Phase 2C and Phase 2D, with the HTTP session boundary blocked, were identical. `git diff --check`, Git-ignore verification, protected-season searches, and prohibited-artifact searches passed. Only task-local pytest temporary directories were removed.
