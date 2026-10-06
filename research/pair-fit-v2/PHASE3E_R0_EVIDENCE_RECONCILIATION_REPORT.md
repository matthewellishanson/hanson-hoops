# Phase 3E-R0 cache-only evidence-reconciliation checkpoint

## Conclusion

**Cache-only reconciliation completed; the 2023-24 player-Totals reliability dependency is verified, while full-season `NET_RATING` reconstruction validation is not feasible from the existing cache.**

The checkpoint did not construct a 2024-25 model dataset, generate predictions, calculate model or holdout metrics, or choose an aggregation method. The final-test season remained untouched. No network request, cache mutation, raw-evidence relocation, acquisition, commit, or push occurred.

The required start gate passed:

- branch: `research/pair-fit-v2`
- HEAD: `76972923c9e86dfc33f82b379010477293ca9fbc`
- initial working tree: clean

## Verified evidence

### 2023-24 player Base/Totals dependency

The missing dependency identified in the initial Phase 3E stop was already present in the original Phase 3A.1 namespace. It did not need to be acquired, copied, or moved.

Identity:

- endpoint: `LeagueDashPlayerStats`
- season: `2023-24` Regular Season
- league scope: `00`
- measure: Base
- mode: Totals
- league-wide player scope with the recorded empty filters

The dry run, allowlist, authorization, ledger, metadata, and body agree on that identity. The ledger contains one successful attempt, HTTP 200, with no retry.

| Immutable record | Bytes | Serialized-byte SHA-256 |
|---|---:|---|
| `phase3a1/dependency-dry-run.json` | 1,247 | `53403b597f6a34eacf94e14b4f60e0b644ad9a9486b97f9214a1c17e8cf3f522` |
| `phase3a1/dependency-allowlist.json` | 1,141 | `217da8244e9c7efabb1630c08d015baa3bbc8e0ab6caa3b90377d83c9fc8ebb6` |
| `phase3a1/dependency-authorization.json` | 200 | `580a4908f22bda7d6e5b81254ecca8708d9dac2b2ab31339a974e2f5a01ae657` |
| `phase3a1/dependency-ledger.json` | 3,109 | `ca23bba17ba340161a1d036451aa9be2f0d3fd223e877a61ffcbb57babdece87` |
| `phase3a1/metadata/league_dash_player_stats_2023-24_base_totals.attempt-1.json` | 2,529 | `608faf28873ffaa056e7e21d8d1bea9f3dd1995713a8b7412fa4c58fa0236b61` |
| `phase3a1/raw/league_dash_player_stats_2023-24_base_totals.attempt-1.json` | 173,713 | `0a856d37c33218362a0b88fc645b7d609a64a7da0773a1be1368d22d07b54774` |

The raw payload's canonical-JSON SHA-256 is `8d1efef313fbaf4a508a1e786e520feb1ad2161e0400e3f7003a1df062b6cd85`. Its sole `LeagueDashPlayerStats` result set has the approved 69-column Base v2 schema and 572 unique positive canonical player IDs, with no duplicates or malformed IDs. Its ID set exactly matches the existing 572-row 2023-24 Base/Per100Possessions cache. The Per100 payload has serialized-byte SHA-256 `da9ba4375be5522407e908e073a95d51b1a1ede41fe659ef75d07e178f8bbc0a` and canonical-JSON SHA-256 `46103a3e96e524f8c8f065a2aa747085a505f55e63ae361c308f07ada07ee09c`.

The Totals `MIN` field satisfies the Phase 3E reliability-metadata contract. All 572 values are finite, nonnegative, and present; they range from `0.6666666667` to `2988.5683333333`, with median `878.7333333333`. Phase 3B's established mapping materializes this field as `TOTAL_MIN`, and the feature manifest categorizes `player_slot.total_min` as reliability metadata rather than an estimator predictor. No path convention requires duplicating this evidence.

### Charlotte full-season and child-window evidence

The immutable anchors replayed exactly:

| Evidence | Bytes | Serialized-byte SHA-256 |
|---|---:|---|
| Phase 1C manifest | 426,578 | `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c` |
| Phase 1D ledger | 23,276 | `f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9` |
| Phase 1E ledger | 186,371 | `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde` |

Charlotte's direct full-season Base and Advanced responses each contain exactly 250 canonical keys. Base has 56 lineup columns and raw SHA-256 `15e35a888174db527ed93642b597c33f5f80ce671d737eb9ee7bc978128887f5`; Advanced has 48 lineup columns and raw SHA-256 `60e175c71798589772266318fbd54ecb59c892e004668d52c841747a24c778ff`.

All four Phase 1E child-window assets remain verified and below 250 rows:

| Window | Measure | Rows | Bytes | Raw SHA-256 | Canonical-JSON SHA-256 |
|---|---|---:|---:|---|---|
| 2024-10-22–2025-01-31 | Base | 163 | 42,275 | `1b13570aed856f37eaf636ac7dd0fa1c3a09c67800be3a0a0e8c56cf7be63a11` | `f2960e37aae02773b38c0078c391b6bd3cd7f88a466e1e62e34df744271333da` |
| 2024-10-22–2025-01-31 | Advanced | 163 | 43,568 | `c88d9941492bc9e9a450c15309fbac739728bd7d7593c5486bd2294100475658` | `466e5e32799f705e4554615ac5211203adf0ab6155a9641f4cb6cfad78d303cb` |
| 2025-02-01–2025-04-13 | Base | 177 | 45,139 | `5c8e0c67ac71faba5ed49e120a3146f13aa2fb0b658cc6c432d2cc5f06f14529` | `060fc419884405837dbda5d1ba38baf7f3ac2f2cbb50b0dee92d05dc51566cf7` |
| 2025-02-01–2025-04-13 | Advanced | 177 | 47,221 | `775ab226b75c430fb479bd94b39fbf3008debca7b52842c26a9e37c3ba16a58f` | `a609696d016d9982114b85e55209353906c4ccaf1d003471c952db7d87c791e1` |

Each window reconciles Base to Advanced one-to-one with no missing, duplicate, malformed, or same-player keys. The reproduced population identity is:

- early keys: 163
- late keys: 177
- both windows: 83
- early only: 80
- late only: 94
- window union: 257
- full-season keys found in the union: 250/250
- full-season-only keys: 0
- recovered-only keys: 7

The seven recovered-only pairs are:

| Player IDs | Pair | Window | POSS | Minutes |
|---|---|---|---:|---:|
| `203901`, `1630163` | Elfrid Payton–LaMelo Ball | late | 3 | 1.133333 |
| `1629006`, `1631111` | Josh Okogie–Wendell Moore Jr. | late | 6 | 2.316667 |
| `1629684`, `1641733` | Grant Williams–Nick Smith Jr. | early | 6 | 2.616667 |
| `1630163`, `1630585` | LaMelo Ball–Marcus Garrett | late | 4 | 1.516667 |
| `1630163`, `1631197` | LaMelo Ball–Jared Rhoden | early | 1 | 0.5 |
| `1630208`, `1631109` | Nick Richards–Mark Williams | early | 0 | 0.011667 |
| `1630544`, `1631197` | Tre Mann–Jared Rhoden | early | 3 | 1.233333 |

None has a directly returned full-season `NET_RATING` in the 250-row response.

## Earlier reconstruction analysis and why it remained unresolved

The earlier analysis is in `PHASE1E_RECOVERY_FEASIBILITY_REPORT.md`, `PHASE1F_TARGET_SEMANTICS_REPORT.md`, and `phase1e_recovery.audit_additive_reconstruction`. Phase 3E-R0 reproduced it directly from the immutable responses.

All supported additive Base fields and Advanced `POSS` sum exactly from the two windows to the full-season values for all 250 overlapping keys. This includes `PTS`, `PLUS_MINUS`, and `POSS`.

| Recomposition using returned team `POSS` | Comparable | MAE | Max AE | Errors >0.2 |
|---|---:|---:|---:|---:|
| `OFF_RATING` | 250 | 0.009408 | 0.078351 | 0 |
| `DEF_RATING` | 250 | 0.025377 | 0.710112 | 9 |
| `NET_RATING` | 250 | 0.027691 | 0.694382 | 10 |

Definition-based field availability explains the result:

- Team points are available as Base `PTS`.
- Opponent points can be derived as Base `PTS - PLUS_MINUS`.
- Team possessions are available as Advanced `POSS` and reproduce `OFF_RATING`.
- Opponent possessions at pair/window grain are absent.
- Base `MIN` and `SUM_TIME_PLAYED` are available, but neither is established as a rating denominator.
- Window ratings are published at one-decimal precision; internal full-precision numerators or rates are absent.

`DEF_RATING` is defined over opponent possessions, not returned team possessions. `NET_RATING` is the difference of offensive and defensive rates with those different denominators. Therefore team-possession-weighting window `DEF_RATING` or `NET_RATING` is not definition-based, and minutes-weighting has no evidentiary basis. The nine and ten errors cannot be dismissed as rounding because their team-possession-weighted intervals do not overlap, while the actual defensive denominator is missing. This is why the result was classified as unresolved rather than selecting a convenient exposure-weighted average.

## Cached partition inventory

The cache contains five verified window-style assets, all for Charlotte:

- the four Phase 1E Base/Advanced early/late assets above;
- one Phase 1D Charlotte Base-only `LastNGames=41` response: 181 rows, 46,408 bytes, raw SHA-256 `83a5e3d920eadca3e1bb4bdf0841271720459d884162ee2baa71ec1e6bd31f2c`, canonical-JSON SHA-256 `c30c2dcafda6b8d8253a966fdcebe1224c2b54d14cecf832f08dfdfd3bad1ca9`.

The `LastNGames=41` asset is overlapping rather than a complete complementary partition and has no Advanced counterpart. It cannot validate a full-season rating aggregation.

Phase 1C contains 30 directly returned full-season team responses: Philadelphia and Charlotte are exactly 250 rows; 28 teams are below 250. None of those 28 has a matched, exhaustive Base/Advanced window partition in the existing ledgers. The four Philadelphia Phase 1E assets remain planned and uncached, and Philadelphia is itself a 250-row parent rather than a noncapped validation case.

Thus the cache has no independent noncapped team-season on which a proposed window aggregation can be compared with directly returned full-season ratings.

## Possibilities, missing evidence, and minimum acquisition

Verified:

- The 2023-24 Totals dependency closes the reliability-metadata path gap without reacquisition.
- Charlotte windowing recovers a strictly larger observed pair population.
- Additive counts and team possessions aggregate exactly.
- Team-possession reconstruction is supported for standard `OFF_RATING` only.

Still hypotheses, with none selected here:

- weighting `DEF_RATING` or `NET_RATING` by team possessions;
- weighting any rating by minutes or `SUM_TIME_PLAYED`;
- treating observed agreement on one capped team as sufficient general validation.

Missing:

- an authoritative opponent-possession denominator at the same pair/window grain;
- a matched exhaustive window partition for a team whose direct full-season Base and Advanced responses are below 250 rows;
- direct full-season standard ratings for Charlotte's seven recovered-only keys.

Cache-only reconstruction validation is therefore **not feasible**.

The smallest additional package for empirical validation is exactly four new `TeamDashLineups` assets for one predeclared below-250 parent team: Base and Advanced for each of the same two exhaustive, nonoverlapping date windows. For example, Atlanta (`1610612737`; 169 cached full-season rows) would require:

1. 2024-10-22 through 2025-01-31, Base;
2. 2024-10-22 through 2025-01-31, Advanced;
3. 2025-02-01 through 2025-04-13, Base;
4. 2025-02-01 through 2025-04-13, Advanced.

Those four assets could test an explicitly predeclared hypothesis against Atlanta's existing direct full-season response, but they still could not make defensive/net aggregation definition-based because the same schema omits opponent possessions.

Definition-based validation additionally requires authoritative opponent-possession values for every pair in both windows at identical grain. If a separately reviewed source supplies one complete opponent-possession response per window, that is two further assets—six total in the package. If no authoritative source exposes that denominator, there is no finite acquisition through the current `TeamDashLineups` schema that can establish exact defensive/net reconstruction.

No acquisition is authorized or performed by this checkpoint.

## Deterministic output and verification

The ignored diagnostic is `modeling/phase3e-r0/evidence_reconciliation.json`:

- deterministic canonical-content SHA-256: `06eb118eb6c076343e96630a65b876e0a4764ca19ad271abcc2b09b331a92623`
- serialized-byte SHA-256: `5eb131c1f92ed91de4d7de4c406a92a2e99ca6e1932701b76d04ef5b734f5cf8`
- serialized bytes: 26,795

Two independent executions produced byte-identical output. Focused Phase 3E-R0 tests passed: 5 tests. The relevant Phase 1D, Phase 1E, Phase 1F, Phase 3A.1, and Phase 3E-R0 offline suite passed: 63 tests. Both executions and all integration tests ran inside the repository's network-prohibited guard.

Reproduction command:

```powershell
$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe -m pair_fit_v2.phase3e_r0_cli --cache-root cache --output-dir modeling\phase3e-r0
```

