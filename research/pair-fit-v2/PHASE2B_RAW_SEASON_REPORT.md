# Phase 2B: 2023-24 raw-season acquisition review gate

## Decision

Primary classification: **`2023-24 raw acquisition incomplete; historical expansion blocked`**.

All pre-request gates passed, but the live queue stopped on the first new asset. The Atlanta Base transport invocation failed before an HTTP request was sent because the Phase 2B transport adapter constructed its authorized-team set from `(team_id, team_name)` tuples instead of team IDs. The invocation is conservatively counted as the asset's one attempt. It was not retried, Atlanta Advanced was not requested, and no later team was requested.

The defect now has a no-network regression test and is corrected in the working tree for a future separately authorized continuation. The persisted failed attempt remains unchanged. Completion requires a separate decision explicitly authorizing the Atlanta Base retry and reconciling it with the original cumulative 50-attempt ceiling. Phase 2C and the next historical season remain blocked.

## Starting state and immutable replay

- Branch: `research/pair-fit-v2`
- Starting HEAD: `656d769c7a2e64a0539f45dd92d1dc179ba08877`
- Latest commit: `Phase 2A.1 completed, with dedicated reviewed-promotion operation and approved 69-column schema`
- Initial working tree: clean
- Existing offline suite: 200 passed using `.venv\Scripts\python.exe`. Bare `python.exe` resolved to a Python installation without pytest, so that first command ran no tests.

| Evidence | Reproduced SHA-256 |
|---|---|
| Phase 1C manifest | `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c` |
| Phase 1D ledger | `f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9` |
| Phase 1E ledger | `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde` |
| Phase 1F deterministic analysis | `bbe5b0f3805e06ce553774779ad5210b5af8678f3cd84da4d0820ecf3a700d19` |
| Phase 2A.1 deterministic analysis | `a2af422b8e912396aa7eb2ec39089ece52113711ebf7476f05a994fdc1a26340` |
| Phase 2A.1 manifest | `55406bb879d2fb93edd490b11b39bbcdb3a4de85a17a9bd0672444d9680ec6e0` |
| Phase 2A.1 ledger | `78b4242de669c3a22d88d4cac3b7d26c671c579e1aa1cb474da1f81939fcc1bd` |

The network-blocked replay reproduced 60/60 Phase 1C assets, 5,297 matched observations, eight nonpositive-possession rows, Charlotte's proven 2024-25 non-exhaustiveness, the Phase 1E 257-pair union with seven recovered-only pairs totaling 23 possessions, and Phase 1F's direct-target/reconstruction distinction.

Post-Phase-2A.1 replay reproduced all 12 verified assets with one original attempt each, review event `phase2a-schema-review:955bce1f09dfbe40b5c2ab06`, identical quarantine/promotion bytes, the 69-column `phase2a.player-base.v2` schema, 539/539 player IDs, 880 canary pair matches, zero target-ineligible canary rows, 83/108 player coverage, 526 complete / 307 one-missing / 47 both-missing pairs, and `season_total_minutes_supported`.

## Frozen plan and dry run

The Phase 1C inventory produced 60 unique pair identities in ascending numeric team-ID order, Base before Advanced: ten mandatory imports and 50 new identities. Both player assets are separate dependencies. All ten imports and both dependencies revalidated before transport.

| Artifact | SHA-256 |
|---|---|
| Initial deterministic dry run | `e42e92ddddb6f1d877b8cf23a6941d7831797de85d3bb39cae1e4c9ee28ff4b2` |
| Exact 50-identity live allowlist | `bcbca56d29518ae2a98ba17a14271baa1b18cfe082147e561d9bda73a1ae4add` |

Dry run: 30 teams; 60 entries; ten `reuse_verified_phase2a_source`; 50 `acquire`; zero continuation caches; two verified player dependencies; zero network calls.

## Attempt and stop record

| Field | Value |
|---|---|
| Ordinal | 1 |
| Team / measure | Atlanta Hawks (`1610612737`) / Base |
| Release asset | `phase2b-pair-release:b520622c9ac1bfc91fcf3a28` |
| Scope | `TeamDashLineups`; 2023-24; Regular Season; league 00; group 2; Base; `LastNGames=0`; empty dates |
| Started | `2026-09-02T03:57:59.898324Z` |
| Timeout contract | 30 seconds |
| Result | `failed` / `unexpected_exception` |
| Detail | `ValueError: Unauthorized Phase 2B pair request identity` |
| HTTP status / latency / response bytes | n/a; failure before HTTP |
| Raw/canonical hashes | n/a; no response body |
| Cache/schema/quarantine | none |
| Retry | not attempted and not authorized |

Accounting: 50 authorized cumulative attempts; one consumed transport invocation; zero HTTP requests sent; zero new successes; one failure; zero quarantines; ten imported pair reuses; 49 unattempted identities; 49 unused original attempts; zero player requests.

The stored Atlanta identity was valid and present in the persisted allowlist. The default adapter mistakenly compared the string ID against a set of inventory tuples. Planning tests had not exercised that concrete adapter. A dedicated no-network adapter regression test now does; no new live invocation followed the fix.

## Complete 60-entry ledger state

The Git-ignored `phase2b/release_manifest.json` is the authoritative complete provenance ledger, with normalized identities, release/source IDs, paths, hashes, schemas, source events, statuses, and transitions. `phase2b/attempt_ledger.json` records the same identities and attempt histories.

| # | Team ID | Team | Base release suffix/status | Advanced release suffix/status |
|---:|---|---|---|---|
| 1-2 | `1610612737` | Atlanta | `b520622c9ac1bfc91fcf3a28` failed | `010f2b5c9f4c3098efa7b96e` planned |
| 3-4 | `1610612738` | Boston | `d8f8c98fb1143f4b21d4749f` imported | `619b2a943396219c2693289c` imported |
| 5-6 | `1610612739` | Cleveland | `79b35cce0b7e249cdc10408a` planned | `87b1599fc90f27ad058030c2` planned |
| 7-8 | `1610612740` | New Orleans | `0d6c16f4dc6a325cfb8f7826` planned | `0f86be30752e31c23d0ac95b` planned |
| 9-10 | `1610612741` | Chicago | `393e02901bd5644de0191c78` planned | `d129b9468cdc2426777044c6` planned |
| 11-12 | `1610612742` | Dallas | `f23c609eaaf197ad387d5059` planned | `7b3364ed12196f57faeedae0` planned |
| 13-14 | `1610612743` | Denver | `547d266652c09c4788f950c9` planned | `74273fd32d009889f532d628` planned |
| 15-16 | `1610612744` | Golden State | `175027a041f66b8e0855e43c` imported | `2c657bc4bd7551d607d45267` imported |
| 17-18 | `1610612745` | Houston | `76e5cd66b92c0cf9892c9e86` planned | `0179b869e1911e9c81e345a9` planned |
| 19-20 | `1610612746` | LA Clippers | `ebab6fdb3fc6ea60a9fc246c` planned | `91765215644ce621539dcf85` planned |
| 21-22 | `1610612747` | LA Lakers | `ae200902240c6b336f85b3e6` planned | `2e2341230f1d2f6bd8b1502f` planned |
| 23-24 | `1610612748` | Miami | `d4f48cd945e0ba4cc42612d8` planned | `effaa04de93671354902d621` planned |
| 25-26 | `1610612749` | Milwaukee | `8d5692b699f33ad52741d5d6` planned | `50e6d5e9133fc19992283047` planned |
| 27-28 | `1610612750` | Minnesota | `0216f712a93600044e6179cc` planned | `29e95c3d65ce21b7de0171f9` planned |
| 29-30 | `1610612751` | Brooklyn | `09d13109e67bfafce684c3d5` imported | `48335f9911a39a92c33a0c4e` imported |
| 31-32 | `1610612752` | New York | `ae2977ae5d891cb128c2efe7` planned | `a485953d632da462d7cc4bf7` planned |
| 33-34 | `1610612753` | Orlando | `4d6e80118e8b3d5038f3fab0` planned | `3cf12b562a7bfe668d7c3b0a` planned |
| 35-36 | `1610612754` | Indiana | `2acac3536e31580936b5c247` planned | `431e8bf1f1ff50c68c7d2107` planned |
| 37-38 | `1610612755` | Philadelphia | `3dda98dbcf593c6c2b61234d` planned | `f5fc57c941b4516cd1322572` planned |
| 39-40 | `1610612756` | Phoenix | `7444576cd997f6c851fd75f9` planned | `7d9999549e1c657215b0d362` planned |
| 41-42 | `1610612757` | Portland | `f37e80899e81bfcce4294421` planned | `5d0574345a999a7106177d7e` planned |
| 43-44 | `1610612758` | Sacramento | `5e7f44479526012027f7abfb` planned | `a588c98dac1156c87fec2ae0` planned |
| 45-46 | `1610612759` | San Antonio | `831cded8df4899708bb185dc` planned | `057dd9933bba4969d4694eee` planned |
| 47-48 | `1610612760` | Oklahoma City | `75d2c40b4059fd91fcccea16` planned | `20dd1f7a1f24400890ac2c4b` planned |
| 49-50 | `1610612761` | Toronto | `002f8a9a5b872f4e75638628` planned | `d22b4aba1897d71296c188ee` planned |
| 51-52 | `1610612762` | Utah | `b9e830ca15c6efa7f0fdebb3` planned | `ed88fc5d7bcc480ac2d4ecfb` planned |
| 53-54 | `1610612763` | Memphis | `884765b00641cf84d4f7ac1d` planned | `9062ffe737b9df31fe0573db` planned |
| 55-56 | `1610612764` | Washington | `fbfc3280af9be809901832ba` imported | `039c61a1d5414ec842cdd5b0` imported |
| 57-58 | `1610612765` | Detroit | `226c9b4ca673c1ca2d8911a2` planned | `91dd3b841d5a5f3282800c01` planned |
| 59-60 | `1610612766` | Charlotte | `783ceb053ca20b22c2043dc8` imported | `f324f5c5db45d734753a0639` imported |

The ten imported raw/canonical hashes and byte counts remain exactly those in Phase 2A.1. The two dependency hashes remain Per100 `98cfc280...` / `b1416c32...` and Totals `e3965058...` / `c2f1ac42...`; both retain their full 64-character hashes in the manifest, exact 69-column fingerprint, and original provenance.

## Gates and unavailable audits

| Gate | Result |
|---|---|
| Request-set completeness | failed: ten imports, 0/50 new assets |
| Source integrity | passed for prerequisites, imports, and dependencies |
| Returned-row integrity | unresolved beyond the unchanged five-team canary |
| Population exhaustiveness | unproven; no new evidence |
| Prior-history coverage | unchanged five-team evidence only; policy unresolved |
| Next historical phase | blocked |

No new response exists, so no new row counts, schema fingerprints, joins, target identities, exposure distributions, boundary signals, unmatched players, or league-wide missing-history tables can be reported. Zero would mean “not observed,” not an empirical zero. The immutable canary remains 880 clean matches with its prior findings.

## Decision questions

1. **All 60 verified?** No: ten imported, zero newly acquired, one failed before HTTP, 49 unattempted.
2. **Both player dependencies unchanged with zero requests?** Yes.
3. **All pair schemas identical?** Known only for the ten imported assets; no new schema observed.
4. **All 30 teams reconciled?** No. The five imported teams retain 880 clean matches.
5. **Targets coherent and ineligible rows?** No new evidence; imported canary remains coherent with zero ineligible rows.
6. **Boundary signals or omissions?** No new 2023-24 evidence; 2024-25 Charlotte remains context only.
7. **Full coverage versus canary?** Unavailable because the full population was not acquired.
8. **Teams, bands, or IDs for later analysis?** Cannot be expanded beyond the documented canary.
9. **Immutable evidence unchanged?** Yes, all required hashes and review history replayed.
10. **Persistence/resume ready?** Conservative persistence and stopping worked; the adapter defect and failed identity block readiness.
11. **Next historical phase ready?** No; a separate Phase 2B continuation decision is required.
12. **Deferred decisions?** Target, exposure, missing-history, population, features, weights, curation, validation implementation, and modeling.

## Secondary classifications and next decision

| Question | Classification |
|---|---|
| Pair schema compatibility | `not_observed_beyond_verified_canary` |
| Base/Advanced reconciliation | `release_incomplete` |
| Direct target / eligibility | `not_observed_beyond_verified_canary` |
| Row-boundary risk | `unassessed_for_complete_2023-24_release` |
| Prior-player dependencies | `reused_verified_unchanged` |
| Prior-history coverage | `full_population_unresolved` |
| Season-shift leakage | `enforced` |
| Manifest/resume | `stop_state_preserved; continuation_requires_new_decision` |
| Next historical phase | `blocked` |

A future bounded continuation must preserve the failed ordinal-1 event, explicitly authorize exactly one Atlanta Base retry after the regression-tested fix, and state whether the cumulative ceiling becomes 51 so the retry plus 49 never-attempted identities can complete. Every other schema, reconciliation, cache, and no-retry gate should remain unchanged. No continuation or later phase occurred here.

## Reproducibility and verification

- Two independent network-blocked state replays produced identical semantic SHA-256 `3252d52b8746e9cff1f5bde3316411a403ec1bbafafb6f729758f0581f341b75`.
- The replays verified ten imports and two dependencies, made zero network calls, and did not mutate the manifest, ledger, original dry run, or allowlist.
- Stopped-state manifest SHA-256: `4a66c6dd9af49eb57beb794b7867d0d49606b90021b6ae69669d5e7435c1870e`.
- Stopped-state attempt-ledger SHA-256: `228424bb699cf7d3b72d78396f176e03eb41d3f66d985912e1c0761d9d16f177`.
- Focused Phase 2B suite: 20 passed on the final run.
- Complete offline research suite: 220 passed on the final run.
- One preceding focused run encountered a transient Windows file-lock during an atomic temporary-ledger replace; a fresh isolated basetemp passed without code changes.

No 2025-26 acquisition, other season, player request, canary refetch, alternate endpoint, date window, retry, curated dataset, Parquet/Feather/database, target/threshold/feature selection, model, production change, secret/proxy change, commit, push, stash, reset, rebase, branch switch, or history rewrite occurred.
