# Phase 2A: 2023-24 historical raw-acquisition canary

## Bounded conclusion

Primary classification: **`historical pair acquisition supported; prior-season join unresolved`**.

The ten authorized `TeamDashLineups` requests succeeded, replayed, and matched the approved 2024-25 schemas without coercion. Across five teams, 880 Base keys and 880 Advanced keys reconcile one-to-one with no malformed, same-player, duplicate, Base-only, or Advanced-only observation. All 880 directly returned standard net ratings equal directly returned offense minus defense within the existing displayed-rounding tolerance. No row has missing, nonnumeric, zero, or negative `POSS`.

The queue then stopped correctly at request 11. The 2022-23 `LeagueDashPlayerStats` Base/Per100Possessions response returned HTTP 200 and valid row widths, but its 69-column schema is additive relative to the approved 67-column contract: `FP_HIGH_SCORE` and `FP_HIGH_SCORE_RANK` are additional. The response was quarantined, not promoted. Request 12 (Base/Totals) was skipped. Consequently the prior-season join, coverage comparison, and Totals `MIN` semantics remain unresolved, and complete 30-team 2023-24 acquisition is not yet authorized by this evidence.

## Starting state and immutable prerequisites

- Branch: `research/pair-fit-v2`
- HEAD: `d910e968886e1f0b9567dca84fc1828ee42bae1a`
- Latest commit: `2026-08-25T22:19:09-05:00 Add Phase 1F target audit module and corresponding tests`
- Initial `git status --short --untracked-files=all`: empty
- Phase 1F was committed and the tree was clean.
- Initial complete offline suite: 183 passed; the only warnings were the pre-existing inaccessible optional `.pytest_cache`.

Cache-only replay blocked socket creation and `requests.Session.request` and reproduced:

| Immutable evidence | SHA-256 / finding |
|---|---|
| Phase 1C manifest | `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c` |
| Phase 1D ledger | `f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9` |
| Phase 1E ledger | `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde` |
| Phase 1F deterministic analysis | `bbe5b0f3805e06ce553774779ad5210b5af8678f3cd84da4d0820ecf3a700d19` |
| Phase 1C rows | 60/60 assets; 5,297 Base; 5,297 Advanced; 5,297 matched; 8 nonpositive-possession ineligible |
| Phase 1D | Charlotte 2024-25 `proven_non_exhaustive`; three proving pairs |
| Phase 1E | Charlotte union 257; seven recovered-only; 23 recovered-only possessions |
| Phase 1F | `direct full-season target semantics supported; reliability threshold unresolved` |

No Phase 1 manifest, ledger, raw payload, metadata, status, or hash was changed.

## Authorization, dry run, and acquisition outcome

Authorization was 12 sequential requests, no retry. The deterministic dry run listed 12 unique identities and `phase2a/raw/` destinations in the required order and made zero network calls. No exact verified Phase 2A cache existed, so none was reused.

- Authorized: 12
- Attempted: 11
- Successful and verified: 10
- Transport/HTTP/JSON/identity failures: 0
- Quarantined: 1
- Skipped: 1
- Reused from verified cache: 0
- Retries: 0

All attempted requests used direct `requests.Session`, `trust_env=False`, fixed research headers, no proxy/retry adapter/header rotation/authentication workaround, an explicit 30-second timeout, sequential execution, and the existing one-second inter-request delay. Pair requests used season `2023-24`, Regular Season, league `00`, group quantity `2`, and the named measure. Player request 11 used season `2022-23`, Regular Season, league `00`, Base, Per100Possessions. The target and prior seasons are explicit in every identity.

## Complete request ledger

All hashes below are full SHA-256 values. “Canonical” uses `sha256-json-sort-keys.v1`; response and cache byte counts are recorded separately even where equal.

| # | Asset ID / request | Status | Latency s | Response / cache bytes | Raw-body SHA-256 | Canonical JSON SHA-256 |
|---:|---|---|---:|---:|---|---|
| 1 | `phase2a-raw-asset:1b5dd4a61d76b5dbf04ef3c2` GSW Base | verified | 2.248 | 34,964 / 34,964 | `a680ad5cf1b53d7957d66d7881f1429eb8db864ccedb37656fd29e634660996d` | `bf88bb86d501f1f9f7effc4cdf76612d186c956df5085bcb9becf333f423d04a` |
| 2 | `phase2a-raw-asset:f8e29e3226b86735e67e1669` GSW Advanced | verified | 2.182 | 35,905 / 35,905 | `5a7f164a3911d08b49d9ead34686a8eebf706ca15fccf35ed2241fce9996f60a` | `3c5aa50692ecb388aaa49694cdd31f8696ce09f9892a6ded4dc195da7490227d` |
| 3 | `phase2a-raw-asset:fbf9cfc93d17a87ba555059d` Boston Base | verified | 1.862 | 39,422 / 39,422 | `64ec87bccbd97f870d20d2d9403311b3bc504a24ef915ccc72cc33b4602f75ce` | `f176184e9a65c413406af0bb702a73894c58c66052adc2017ba1a0ed6b91d3a9` |
| 4 | `phase2a-raw-asset:26b73e49b380fb71686b4108` Boston Advanced | verified | 1.846 | 40,794 / 40,794 | `b30f19b9e7fddd17642a48fdcc26a5e9ea4e407d5817c0741b32e8b686716a10` | `59c2b56e5ceb75a5479dd16c0d077cbb0250131551daf3cef18ca48ea1632af8` |
| 5 | `phase2a-raw-asset:83264e78bc5d2a6a4d678f22` Washington Base | verified | 5.188 | 53,760 / 53,760 | `9671b33e9490196894bcf95e7f8cba4653ad893753e14c8b2f659d30c9c6128c` | `497e6e52e2ff9248f5cbd86d6dc5c2148bd1072b8847b499ac11541a4b639479` |
| 6 | `phase2a-raw-asset:d131d285eb891648dbd0318b` Washington Advanced | verified | 1.687 | 55,534 / 55,534 | `02b1ff5c4655a8106551698ea4e0caa5f2f2a94fb7dcdc29c3e1e444424a5f4a` | `66f7d41af2d7f908c7265599f02271fc79f775c85fa12ac342b5c64c37ae8ee8` |
| 7 | `phase2a-raw-asset:654533ee0737be0ac9661f3b` Brooklyn Base | verified | 2.062 | 44,725 / 44,725 | `54a5d2a33ff498d91f0ec4abce268bfecd2e8cee110f96f82c48629acb926e09` | `b79974e631350367f917a96728d5a5cbd2f04d9287a4cd28d19f00054f974cb1` |
| 8 | `phase2a-raw-asset:e15df5780c003e676ef9e18a` Brooklyn Advanced | verified | 1.700 | 46,103 / 46,103 | `73a15a36e04761e1fbab70461cf453affe1b08a723376c1234f6c6cff92bb0db` | `d88688b7ddde796a1861484f5fcfae72dba3857b2fce11606ad26ab257d1fd76` |
| 9 | `phase2a-raw-asset:3c82543e754d27b726375f4a` Charlotte Base | verified | 1.690 | 56,421 / 56,421 | `8c1260fe9b905a7cc729f5a6a9cdbde395a099695bf1b277401bfe83d5125407` | `87a9786a9652f491ffa854b5caa57bd9b8e60ea259ced5e9ce5a78d9772a4939` |
| 10 | `phase2a-raw-asset:c954419c3c0206a10959a4e6` Charlotte Advanced | verified | 1.709 | 58,045 / 58,045 | `b19dcddb81b6f3ee5a331204f2ad19ee247b6eec310f8c2f552531028d1f5d30` | `e96f8761dd817f23f66601328b368a90ce1eb073dd9c79d08c12e861171bab66` |
| 11 | `phase2a-raw-asset:ab061d6a5bba1d84a946134c` player Base/Per100 | quarantined: additive schema | 1.787 | 166,476 / not promoted | `98cfc280a6e6fe43c87a2d33b57fbbc279d7aebaf6090c25c7fb0624272900ef` | `b1416c32b67fa0652baaaf79fd05beaf31223fce485d515c01ab16a3e9e80585` |
| 12 | `phase2a-raw-asset:d5f038caee22019a748eed5c` player Base/Totals | skipped after #11 | — | — | — | — |

The quarantined body remains immutable under `cache/phase2a/quarantine/`; it is not a verified raw feature asset. Phase 2A manifest and attempt-ledger file hashes at report generation were `5910d5b75a671e0d1fac2e59e3676c1fcdc38506b50dd9c5c5799c298f2270ed` and `99c1e0b2ed6486ce8c232243074146849021eb0bc08625d51f9829124369b294` respectively.

## Schema findings

Every pair payload contains exactly one `Overall` and one `Lineups` result set, and every row width matches its header width. All five teams are identical to the approved 2024-25 contracts:

| Measure | Overall | Lineups | Drift |
|---|---:|---:|---|
| Base | 57 ordered columns | 56 ordered columns | `identical` |
| Advanced | 49 ordered columns | 48 ordered columns | `identical` |

The player response contains one `LeagueDashPlayerStats` result set, 539 rows, 69 ordered columns, and valid row widths. Relative to the approved 67-column Base schema it is `additive`, with only `FP_HIGH_SCORE` and `FP_HIGH_SCORE_RANK` additional. Nothing was reordered, missing, renamed, filled, dropped, or coerced. This is the exact unresolved contract change.

Diagnostic inspection of the quarantined rows found 539 non-null, unique stable player IDs, zero duplicate IDs, and zero missing/malformed IDs. Seventy aggregate rows report `TEAM_COUNT > 1`; one reports `GP > 82`. This is compatible with one aggregate row per stable player ID and visible multi-team history, but the payload is not approved for a join while quarantined.

## Pair identity, reconciliation, exposure, and population audit

| Team | Base / Advanced | Players | Theoretical / absent | Matched | Base-only / Advanced-only | Min Base MIN / POSS | Population classification |
|---|---:|---:|---:|---:|---:|---:|---|
| Golden State | 133 / 133 | 18 | 153 / 20 | 133 | 0 / 0 | 0.536667 / 2 | `no_boundary_signal_observed` |
| Boston | 153 / 153 | 19 | 171 / 18 | 153 | 0 / 0 | 0.420000 / 1 | `no_boundary_signal_observed` |
| Washington | 207 / 207 | 24 | 276 / 69 | 207 | 0 / 0 | 0.653333 / 1 | `no_boundary_signal_observed` |
| Brooklyn | 171 / 171 | 21 | 210 / 39 | 171 | 0 / 0 | 0.065000 / 1 | `no_boundary_signal_observed` |
| Charlotte | 216 / 216 | 26 | 325 / 109 | 216 | 0 / 0 | 0.268333 / 1 | `no_boundary_signal_observed` |

All 880 Base and 880 Advanced rows have exactly two distinct stable player IDs. There are zero duplicate full observation keys. The bounded five-team sample has zero cross-team players and zero cross-team pairs; rows would nevertheless remain distinct because team is part of identity. Rank maxima generally reach or nearly reach each team's returned row count and are preserved in the deterministic analysis. No response lands on 250 or another common repeated boundary. The absent theoretical combinations and 2024-25 Charlotte history are risk context, not proof of a 2023-24 omission; Phase 2A makes no population-exhaustiveness claim.

Possession quartiles (minimum / Q1 / median / Q3 / maximum) are:

| Team | Possession distribution | Base-minute distribution | `POSS < 10` |
|---|---|---|---:|
| Golden State | 2 / 74 / 350 / 1,028 / 3,112 | 0.537 / 33.9 / 165.48 / 481.305 / 1,457.09 | 6 |
| Boston | 1 / 34 / 120 / 490 / 3,867 | 0.420 / 15.95 / 59.347 / 244.697 / 1,865.245 | 11 |
| Washington | 1 / 41.5 / 177 / 458 / 3,795 | 0.653 / 19.45 / 80.672 / 208.824 / 1,746.343 | 22 |
| Brooklyn | 1 / 38 / 186 / 679.5 / 3,551 | 0.065 / 17.045 / 87.037 / 325.13 / 1,729.86 | 14 |
| Charlotte | 1 / 77.75 / 210.5 / 543.25 / 3,325 | 0.268 / 38.058 / 101.143 / 263.842 / 1,619.477 | 14 |

Extreme net ratings concentrate in sparse rows: among the 67 rows with 1–9 possessions, 33 have `|NET_RATING| >= 50` and 19 have `|NET_RATING| >= 100`; values range from -300.0 to 150.0. Among the 562 rows with at least 100 possessions, only three reach `|NET_RATING| >= 50` and none reaches 100. This is descriptive and does not select a threshold.

## Direct targets and eligibility

- Standard and estimated rating fields are numeric for all 880 rows.
- Standard `NET_RATING - (OFF_RATING - DEF_RATING)` has maximum absolute displayed discrepancy `0.1` for every team.
- Estimated identity is independently within `0.1` for every row; this does not document an estimated formula or select it as a target.
- `POSS`: 880 numeric positive values; zero missing, nonnumeric, zero, or negative values.
- Target-ineligible rows: 0.
- Base fractional `MIN`, Base `PLUS_MINUS`, Advanced `MIN`, `POSS`, and all returned rating fields remain unchanged in raw caches. No positive threshold was applied.
- A few Advanced `MIN` values display as zero at positive possessions (Boston 1 row, Brooklyn 3, Charlotte 2), reinforcing the existing rule to use Base fractional `MIN` for exposure and keep Advanced `MIN` audit-only.

## Prior-player join and Totals MIN

The join was not run. A quarantined prior source cannot satisfy the approved feature identity, and request 12 was correctly skipped. Therefore unique-player coverage, pair coverage (`complete` / `one_missing` / `both_missing`), exposure-weighted coverage, comparison with the earlier 2024-25 four-team evidence, and the 2022-23 Totals-versus-Per100 `MIN` test are all unresolved. No absent player was labeled a rookie, error, or inactive player. No value was imputed.

Season-shift tests enforce `prior_feature_season < target_season`, the exact `2023-24 -> 2022-23` mapping, rejection of same/future/non-adjacent sources, preservation of both seasons on joined rows, and season-separated manifest/cache identities. No 2023-24 complete player statistics enter the prior table, and no 2024-25 or 2025-26 asset can satisfy the 2022-23 prior identity.

## Decision questions

1. **Can the pair contract operate on 2023-24 without coercion?** Yes for all five canary teams and both measures; all ten schemas are identical.
2. **Do pair identities and joins remain structurally valid?** Yes: 880 canonical keys, 880 one-to-one matches, no structural violations.
3. **Are direct standard targets available and coherent?** Yes for all 880 rows, within `0.1` displayed-rounding tolerance.
4. **What target-ineligible anomalies appear?** None; all possessions are numeric and positive. Sparse exposure and zero-rounded Advanced minutes remain audit concerns.
5. **Do row-boundary/exhaustiveness signals appear?** No exact 250 boundary appears. This is `no_boundary_signal_observed`, not proof of exhaustiveness.
6. **Does 2022-23 join correctly without leakage?** Leakage protection is enforced, but the empirical join is unresolved because the source was quarantined.
7. **How does coverage compare with 2024-25 evidence?** It cannot yet be compared responsibly; coverage was not computed from a quarantined source.
8. **Does Totals `MIN` behave as season-total minutes?** Unresolved; request 12 was skipped.
9. **Are persistence, isolation, and resumability ready for 30 teams?** The pair path is ready: atomic state, immutable unique caches, replay, cache-skip, corruption detection, no-retry stop, and season isolation worked. The combined pair-plus-prior workflow is not ready until the player schema decision and remaining asset are resolved.
10. **What anomaly must be resolved?** The 2022-23 player response adds `FP_HIGH_SCORE` and `FP_HIGH_SCORE_RANK`. A separate decision must version or reject that schema; Phase 2A does not silently accept it.
11. **Is complete 2023-24 raw acquisition authorized by this evidence?** No. Pair acquisition is supported, but the required prior-player contract remains unresolved.
12. **What should Phase 2B do and avoid?** First perform a cache-only schema-decision phase for the two additive fields. If approved under a versioned contract and separately authorized, validate/promote the preserved Per100 response without refetching, acquire the still-unattempted Totals identity, audit Totals `MIN`, and complete coverage joins before deciding on 30-team acquisition. It should not refetch request 11, broaden seasons/endpoints/measures, curate data, select thresholds/features, or model.

## Secondary classifications and next phase

| Question | Classification |
|---|---|
| Pair schema compatibility | `identical` |
| Base/Advanced reconciliation | `clean` |
| Direct target availability | `available_and_internally_coherent` |
| Target eligibility behavior | `all_880_positive_possession` |
| Row-boundary risk | `no_boundary_signal_observed`; global exhaustiveness unproven |
| Prior-player schema compatibility | `additive_quarantined` |
| Prior-history coverage | `unresolved_not_joined` |
| Totals MIN semantics | `unresolved_not_acquired` |
| Season-shift leakage protection | `enforced` |
| Manifest/resume readiness | `pair_path_ready; combined_workflow_blocked_at_schema_gate` |
| Phase 2B readiness | `no-go pending prior-player schema decision and Totals audit` |

Recommended next phase: a bounded, cache-first **Phase 2A.1 prior-player schema decision and completion audit**, not 30-team acquisition. Global pair-population exhaustiveness, final target, exposure policy, features, missing-history fallback, and model design remain outside scope.

## Reproducibility and prohibited-work confirmation

Two independent cache-only analyses produced deterministic SHA-256 `886372aedc76bf5a59b683c08078dbc66a4f594f9c59ed9dcfcea2b37c16e526`; network-call count was zero during replay. The final verification section in the task handoff records focused/full test counts, Git checks, ignore checks, stale-language searches, and prohibited-artifact searches.

No 2025-26 data, extra season, sixth team, third measure, date window, `LastNGames`, `LeagueDashLineups`, model, curated table, Parquet, Feather, DuckDB, SQLite/database, threshold, feature selection, validation split, target reconstruction, production change, secret/proxy change, retry, commit, push, rebase, reset, branch switch, stash, or history rewrite occurred.
