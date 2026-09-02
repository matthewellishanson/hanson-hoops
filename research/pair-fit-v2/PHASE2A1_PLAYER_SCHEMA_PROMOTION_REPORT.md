# Phase 2A.1: reviewed player-schema promotion and canary completion

## Decision

Primary result: **`historical canary supported; complete 2023-24 raw acquisition ready`**.

Phase 2B decision: **GO for bounded complete 2023-24 raw acquisition under the existing immutable-raw, schema-validation, no-curation contract.** Phase 2B itself was not started. This decision does not authorize modeling, threshold or feature selection, curated materialization, another season, or any work beyond a separately specified Phase 2B acquisition plan.

## Starting state

- Branch: `research/pair-fit-v2`
- HEAD: `8407c244ff3d2ecc6ae72ba579aab58e0a7ffa7d`
- Working tree: clean
- Phase 2A committed
- Existing offline suite before Phase 2A.1: 198 passed
- Request 11: one quarantined attempt, preserved body present
- Request 12: planned, zero attempts
- No interrupted Python acquisition process was running

The preserved request-11 body revalidated cache-only as HTTP-identity-compatible, structurally valid, 539 rows by 69 columns, with exact additive drift relative to v1: `FP_HIGH_SCORE` and `FP_HIGH_SCORE_RANK`. No network call occurred during review or promotion.

## Reviewed promotion

| Item | Value |
|---|---|
| Asset | `phase2a-raw-asset:ab061d6a5bba1d84a946134c` |
| Review event | `phase2a-schema-review:955bce1f09dfbe40b5c2ab06` |
| Previous schema | `phase2a.player-base.v1` (67 columns) |
| Approved schema | `phase2a.player-base.v2` (69 columns) |
| Approved contract ID | `schema-contract:a39b5a33c328fd9c467ff8d6` |
| Rows | 539 |
| Raw SHA-256 before/after | `98cfc280a6e6fe43c87a2d33b57fbbc279d7aebaf6090c25c7fb0624272900ef` |
| Canonical SHA-256 before/after | `b1416c32b67fa0652baaaf79fd05beaf31223fce485d515c01ab16a3e9e80585` |
| Byte equality | exact |
| Network calls | 0 |

The quarantine body remains at its original path. The same 166,476 bytes were atomically copied into the verified cache. The promotion metadata points back to the quarantine path and review event. Request 11's original attempt remains unchanged: attempt count 1, one attempt-history entry, original status `quarantined`, original `schema_quarantine` category. Promotion is represented only by the separate schema-review record and `reviewed_schema_promotion` transition.

## Request-12-only authorization and acquisition

Authorization event: `phase2a1-totals-authorization:8d70c4b2847f23477f13cb70`.

It names only `phase2a-raw-asset:d5f038caee22019a748eed5c`, permits one new attempt, and explicitly records `request_11_retry_authorized: false`. The final dry run made zero network calls, replayed assets 1–11, and identified only asset 12 for acquisition.

Request 12 used:

- Endpoint: `LeagueDashPlayerStats`
- Season: `2022-23`
- Season type: Regular Season
- League: `00`
- Measure: Base
- PerMode: Totals
- Direct `requests.Session`, `trust_env=False`, fixed research headers
- No proxy, retry, header rotation, or authentication workaround
- Timeout: 30 seconds

| Status | Attempts | Latency | Response/cache bytes | Raw SHA-256 | Canonical SHA-256 |
|---|---:|---:|---:|---|---|
| verified | 1 | 1.993 s | 164,284 / 164,284 | `e39650585ac2b23cc607fda5695f58c58a92afb4dd9b59fae1a561865f70d4c7` | `c2f1ac4268344c9ba4f0a73978384431869fbaa13b93532341b2a1bf27c36899` |

The Totals response has the exact reviewed v2 fingerprint: one `LeagueDashPlayerStats` result set, 69 ordered columns, 539 valid-width rows. Request 11 and request 12 each finish with exactly one live attempt; request 11 was not retried.

## Player-table reconciliation and trade behavior

| Check | Per100 | Totals |
|---|---:|---:|
| Rows | 539 | 539 |
| Unique stable IDs | 539 | 539 |
| Missing/malformed IDs | 0 | 0 |
| Duplicate IDs | 0 | 0 |
| `TEAM_COUNT > 1` | 70 | 70 |
| `GP > 82` | 1 | 1 |

The player-ID sets match 539/539 with no Per100-only or Totals-only ID. Seventy one-row player aggregates expose multi-team history through `TEAM_COUNT > 1`; this supports the existing one-aggregate-row-per-stable-ID handling and does not require name joins or row deduplication.

## Totals `MIN` audit

| Statistic | Per100 `MIN` | Totals `MIN` |
|---|---:|---:|
| Minimum | 37.7 | 1.0333 |
| Q1 | 46.45 | 328.9933 |
| Median | 47.2 | 970.18 |
| Q3 | 48.2 | 1,845.8908 |
| P90 | 48.9 | 2,280.4093 |
| Maximum | 57.7 | 2,963.1767 |

Highest Totals-minute records include Mikal Bridges (2,963.1767), Anthony Edwards (2,841.455), Zach LaVine (2,767.95), Nikola Vučević (2,746.355), and Julius Randle (2,737.2517). The scale, distribution, and known high-minute records are consistent with season-total minutes. Per100 `MIN` is in a different normalized unit and is not interchangeable.

Classification: **`season_total_minutes_supported`**. Totals `MIN` is approved as a potential prior-player eligibility/reliability field, not selected as a model feature and not assigned a threshold.

## Prior-player joins

All joins use stable `PLAYER_ID`; target season remains `2023-24` and prior-feature season remains `2022-23`. No same-season statistics enter the prior table. Every pair row is retained; no missing history is zero-imputed or assigned a causal label.

| Team | Players matched | Pair complete / one missing / both missing | Complete pair rate | Complete minute share | Complete possession share |
|---|---:|---:|---:|---:|---:|
| Golden State | 13/18 | 69 / 55 / 9 | 51.9% | 67.9% | 68.1% |
| Boston | 17/19 | 126 / 26 / 1 | 82.4% | 98.9% | 98.9% |
| Washington | 19/24 | 139 / 63 / 5 | 67.1% | 76.4% | 76.4% |
| Brooklyn | 16/21 | 100 / 62 / 9 | 58.5% | 88.4% | 88.5% |
| Charlotte | 18/26 | 92 / 101 / 23 | 42.6% | 38.0% | 38.3% |
| **Combined** | **83/108** | **526 / 307 / 47** | **59.8%** | **74.0%** | **74.1%** |

Phase 1A's 2024-25 four-team evidence had 82.6% player coverage and 68.9% complete-pair coverage. The Phase 2A five-team canary has 76.9% player and 59.8% complete-pair coverage; Charlotte materially lowers the combined result. These season/sample differences show that missing-history coverage must remain an explicit audited dimension. They do not establish that roster type causes coverage.

The provisional policy remains unchanged: complete-history rows are the future primary-baseline population; incomplete rows remain for coverage and later universal-fallback evaluation; no imputation or fallback was implemented.

## Phase 2B decision basis

The canary now demonstrates:

1. Ten 2023-24 pair assets with schemas identical to the approved pair contract.
2. 880 Base/Advanced observations reconciled one-to-one with no identity or target-eligibility failures.
3. Direct standard targets available and internally coherent.
4. A reviewed, versioned 69-column 2022-23 player contract shared identically by Per100 and Totals.
5. Exact 539/539 player-ID reconciliation.
6. Season-shift leakage guards and season-isolated cache identities.
7. Totals `MIN` behavior consistent with season-total minutes.
8. Atomic promotion/acquisition metadata, immutable quarantine retention, cache replay, corruption detection, and one-asset resumability.

Therefore complete 2023-24 raw acquisition is supported. Phase 2B should acquire only the remaining 25 teams' 2023-24 Base/Advanced raw assets under a new bounded manifest and explicit request budget, reusing the two verified 2022-23 player assets. It should preserve schema quarantine, stop-on-first-failure, cache replay, endpoint-boundary audit, and the provisional missing-history statuses.

Phase 2B must not refetch the two player assets, access another season or 2025-26, create curated/Parquet/database assets, select targets/thresholds/features, implement fallback policy, or train/evaluate a model.

## Reproducibility

- Phase 2A.1 focused tests: 17 passed before live acquisition
- Complete offline suite before live acquisition: 200 passed
- Final deterministic cache-only analysis SHA-256: `a2af422b8e912396aa7eb2ec39089ece52113711ebf7476f05a994fdc1a26340`
- Final Phase 2A manifest SHA-256: `55406bb879d2fb93edd490b11b39bbcdb3a4de85a17a9bd0672444d9680ec6e0`
- Final Phase 2A ledger SHA-256: `78b4242de669c3a22d88d4cac3b7d26c671c579e1aa1cb474da1f81939fcc1bd`

Final verification repeats the cache-only analysis twice with networking disabled and records repository checks in the task handoff.

No work beyond the eight user-authorized Phase 2A.1 steps occurred. No commit or push was made.
