# Phase 1E bounded pair-population recovery feasibility report

## Bounded conclusion

**`window recovery demonstrated; target recomposition unresolved`.** Two inclusive, non-overlapping Charlotte `TeamDashLineups` windows produced a larger observed union of 257 canonical pairs. The union contains all 250 immutable full-season Charlotte keys, all three Phase 1D proving keys, and four additional omitted keys. This demonstrates recovery of known full-season omissions; global population exhaustiveness remains unproven.

Every audited additive Base total and Advanced `POSS` reproduced the official full-season value for all 250 comparable pairs. Ordinary averaging of rating fields was never used. Possession-weighted `OFF_RATING` recomposition was within `0.1` for every pair, but `DEF_RATING` and `NET_RATING` had errors over `0.2` for 9 and 10 pairs respectively, with maxima of `0.710112` and `0.694382`. Those exceptions were not proven to be only documented rounding artifacts. The Charlotte continuation gate therefore failed and all four Philadelphia requests were skipped.

### Phase 1F follow-up

Phase 1F preserves this historical gate result but separates cross-window reconstruction from direct full-season validity. Cache-only analysis found all 5,297 directly returned standard `NET_RATING` values coherent with directly returned `OFF_RATING - DEF_RATING` within `0.1`. Returned `POSS` empirically supports offensive reconstruction, while the Advanced schema exposes no separate opponent-possession denominator required by defensive-rating semantics. The window failure therefore does not invalidate direct full-season `NET_RATING`. Phase 1F classification is `direct full-season target semantics supported; reliability threshold unresolved`; no target or threshold was selected, and Philadelphia was not requested.

## Starting state and immutable baselines

- Starting/final branch: `research/pair-fit-v2`
- Starting HEAD: `20ae381c9f71a3f5bbd3c3b018f675386541d094`
- Latest commit: `committing phase 1D with exhaustiveness audit completed.`
- Initial working tree: clean; `git status --short --untracked-files=all` returned no entries
- Phase 1C manifest ID: `season-manifest:3caa17ef8d9d465ab3e803f2`
- Phase 1C manifest file SHA-256 before and after acquisition: `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c`
- Phase 1C replay: 60/60 verified, 5,297 Base, 5,297 Advanced, 5,297 matched, 0 unmatched, 8 target-ineligible
- Phase 1D ledger SHA-256 before and after acquisition: `f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9`
- Phase 1D replay: `proven_non_exhaustive`, 178 `LastNGames=41`/full-season matches, three diagnostic-only proving keys

Phase 1C and Phase 1D payloads, metadata, manifests, and ledgers were read and replayed but not modified. Phase 1E uses the separate `phase1e-diagnostic-asset:` namespace and Git-ignored `cache/phase1e/windows/` storage.

The Phase 1D report prose now identifies player `1630585` as **Marcus Garrett**. Raw endpoint names and identifiers remain unchanged.

## Date-window contract

The official NBA Stats lineup interface labels both fields as `MM/DD/YYYY`, and the installed `TeamDashLineups` endpoint contract passes `DateFrom` and `DateTo` directly. Phase 1E fixed these inclusive ranges:

| Window | `DateFrom` | `DateTo` | ISO bounds |
|---|---|---|---|
| Early | `10/22/2024` | `01/31/2025` | 2024-10-22 through 2025-01-31 |
| Late | `02/01/2025` | `04/13/2025` | 2025-02-01 through 2025-04-13 |

The early end plus one day equals the late start. The ranges neither overlap nor leave a date gap and cover the authorized 2024-25 regular-season bounds. All four responses echoed the exact requested dates, `TeamID=1610612766`, the requested measure, `LastNGames=0`, `Season=2024-25`, `SeasonType=Regular Season`, and `GroupQuantity=2`; the date filters were not ignored.

## Authorization and complete request ledger

Authorization: at most eight sequential live requests, no retries. Four were attempted and succeeded; zero failed; four were skipped after the Charlotte gate failed.

All requests used one direct `requests.Session` per attempt, established research headers, `trust_env=False`, a 30-second timeout, no proxy, no `nba_api` transport wrapper, no concurrency, no authentication workaround, and no header rotation.

| # | Team | Window | Measure | Status/reason | HTTP | Latency (s) | Bytes | Diagnostic asset ID |
|---:|---|---|---|---|---:|---:|---:|---|
| 1 | Charlotte | Early | Base | verified | 200 | 2.1878214000 | 42,275 | `phase1e-diagnostic-asset:24185d9f5c0ed96b30b074cf` |
| 2 | Charlotte | Early | Advanced | verified | 200 | 1.5098790000 | 43,568 | `phase1e-diagnostic-asset:f56b8b1c06a02a5ca5be431f` |
| 3 | Charlotte | Late | Base | verified | 200 | 1.4046779000 | 45,139 | `phase1e-diagnostic-asset:adf756becec13438647f4736` |
| 4 | Charlotte | Late | Advanced | verified | 200 | 1.4412588001 | 47,221 | `phase1e-diagnostic-asset:bf03866fea21d84f0a1cdf61` |
| 5 | Philadelphia | Early | Base | skipped: Charlotte gate failed | — | — | — | `phase1e-diagnostic-asset:f5cc9920d2870d5073bad350` |
| 6 | Philadelphia | Early | Advanced | skipped: Charlotte gate failed | — | — | — | `phase1e-diagnostic-asset:9848687388ca75225611123d` |
| 7 | Philadelphia | Late | Base | skipped: Charlotte gate failed | — | — | — | `phase1e-diagnostic-asset:ed9784d9be0c10873e2d3e8d` |
| 8 | Philadelphia | Late | Advanced | skipped: Charlotte gate failed | — | — | — | `phase1e-diagnostic-asset:270cd879211faa2f580c8fc2` |

Final Phase 1E ledger SHA-256: `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde`.

### Payload hashes, schemas, and row counts

| # | Raw-body SHA-256 | Canonical JSON SHA-256 | `Overall` schema/rows | `Lineups` schema/rows |
|---:|---|---|---|---|
| 1 | `1b13570aed856f37eaf636ac7dd0fa1c3a09c67800be3a0a0e8c56cf7be63a11` | `f2960e37aae02773b38c0078c391b6bd3cd7f88a466e1e62e34df744271333da` | 57 columns / 1 | 56 columns / 163 |
| 2 | `c88d9941492bc9e9a450c15309fbac739728bd7d7593c5486bd2294100475658` | `466e5e32799f705e4554615ac5211203adf0ab6155a9641f4cb6cfad78d303cb` | 49 columns / 1 | 48 columns / 163 |
| 3 | `5c8e0c67ac71faba5ed49e120a3146f13aa2fb0b658cc6c432d2cc5f06f14529` | `060fc419884405837dbda5d1ba38baf7f3ac2f2cbb50b0dee92d05dc51566cf7` | 57 columns / 1 | 56 columns / 177 |
| 4 | `775ab226b75c430fb479bd94b39fbf3008debca7b52842c26a9e37c3ba16a58f` | `a609696d016d9982114b85e55209353906c4ccaf1d003471c952db7d87c791e1` | 49 columns / 1 | 48 columns / 177 |

Each schema was identical to the approved Phase 1C measure-specific schema. Both child windows were below 250 rows.

## Per-window Base/Advanced reconciliation

| Window | Base rows | Advanced rows | Matched | Base-only | Advanced-only | Malformed | Same-player | Duplicates | Zero POSS | Missing/nonnumeric/negative POSS | Target-eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Early | 163 | 163 | 163 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 162 |
| Late | 177 | 177 | 177 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 177 |

The early zero-possession pair (`1630208`, `1631109`) was preserved in the full outer population and excluded only from rate arithmetic.

## Two-window population union

- Unique observed window-union pairs: **257**
- Immutable full-season pairs: 250
- Full-season keys found in union: **250/250**
- Full-season-only keys: 0
- Window-union-only/recovered-only keys: **7**
- Increase over full-season response: **7**
- Early-only: 80
- Late-only: 94
- Present in both windows: 83
- All three Phase 1D proving keys present: yes

This answers the population question for Charlotte: deterministic non-overlapping windows recover a strictly larger observed population and recover every known full-season omission. It does not prove that 257 is globally exhaustive.

## Recovered-only pair exposure

Because rate recomposition did not validate, no reconstructed target ratings are reported for recovered-only pairs.

| Player IDs | Players | Window | GP | Base MIN | Advanced POSS |
|---|---|---|---:|---:|---:|
| `203901`, `1630163` | Elfrid Payton — LaMelo Ball | Late | 1 | 1.133333 | 3 |
| `1629006`, `1631111` | Josh Okogie — Wendell Moore Jr. | Late | 1 | 2.316667 | 6 |
| `1629684`, `1641733` | Grant Williams — Nick Smith Jr. | Early | 1 | 2.616667 | 6 |
| `1630163`, `1630585` | LaMelo Ball — Marcus Garrett | Late | 1 | 1.516667 | 4 |
| `1630163`, `1631197` | LaMelo Ball — Jared Rhoden | Early | 1 | 0.500000 | 1 |
| `1630208`, `1631109` | Nick Richards — Mark Williams | Early | 1 | 0.011667 | 0 |
| `1630544`, `1631197` | Tre Mann — Jared Rhoden | Early | 1 | 1.233333 | 3 |

| Exposure | Minimum | Q1 | Median | Q3 | Maximum | Total |
|---|---:|---:|---:|---:|---:|---:|
| Base MIN | 0.011667 | 0.8166665 | 1.233333 | 1.916667 | 2.616667 | 9.328334 |
| Advanced POSS | 0 | 2 | 3 | 5 | 6 | 23 |

The omissions are all one-game, very-low-exposure pairs in these windows. Minutes and possessions are used only for population/reliability auditing and threshold sensitivity, not as predictive player-quality features.

## Additive-total audit

The empirically supported additive Base fields were `GP`, `W`, `L`, `MIN`, `FGM`, `FGA`, `FG3M`, `FG3A`, `FTM`, `FTA`, `OREB`, `DREB`, `REB`, `AST`, `TOV`, `STL`, `BLK`, `BLKA`, `PF`, `PFD`, `PTS`, `PLUS_MINUS`, and `SUM_TIME_PLAYED`. Advanced `POSS` was also additive. Percentages, ranks, pace, and rate fields were not treated as additive; Advanced `MIN` remained audit-only.

For each of these 24 fields, all 250 full-season pairs were comparable. Summing early and late values produced **zero discrepancies** against the immutable full-season response. This validates additive reconstruction for Charlotte under these exact windows and contracts.

## Possession-weighted rate recomposition

Window ratings were weighted by their window `POSS`; they were never ordinarily averaged. `POSS=0` rows remained in the population but were excluded from rate arithmetic.

| Field | Comparable | MAE | Median AE | Max AE | Within 0.1 | Within 0.2 | Over 0.2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `OFF_RATING` | 250 | 0.009408 | 0 | 0.078351 | 250 (100.0%) | 250 (100.0%) | 0 |
| `DEF_RATING` | 250 | 0.025377 | 0 | 0.710112 | 232 (92.8%) | 241 (96.4%) | 9 |
| `NET_RATING` | 250 | 0.027691 | 0 | 0.694382 | 229 (91.6%) | 240 (96.0%) | 10 |

Every discrepancy above `0.2`:

| Field | Pair IDs | Official | Recomposed | Error | Window POSS |
|---|---|---:|---:|---:|---:|
| DEF | `201959`, `1629006` | 131.7 | 131.409524 | -0.290476 | 42 |
| DEF | `201959`, `1631217` | 117.8 | 118.510112 | 0.710112 | 89 |
| DEF | `203995`, `1642354` | 115.9 | 115.547059 | -0.352941 | 68 |
| DEF | `1629006`, `1629610` | 109.3 | 109.619786 | 0.319786 | 187 |
| DEF | `1629006`, `1641733` | 103.6 | 103.815979 | 0.215979 | 194 |
| DEF | `1629610`, `1631209` | 98.2 | 98.425185 | 0.225185 | 270 |
| DEF | `1631109`, `1631217` | 132.2 | 131.923214 | -0.276786 | 112 |
| DEF | `1631209`, `1641733` | 92.6 | 92.902222 | 0.302222 | 90 |
| DEF | `1631209`, `1642275` | 106.7 | 106.419502 | -0.280498 | 241 |
| NET | `201959`, `1629006` | -17.4 | -17.128571 | 0.271429 | 42 |
| NET | `201959`, `1631217` | -12.2 | -12.894382 | -0.694382 | 89 |
| NET | `203995`, `1642354` | -42.4 | -42.017647 | 0.382353 | 68 |
| NET | `1629006`, `1629610` | -8.8 | -9.070053 | -0.270053 | 187 |
| NET | `1629610`, `1631209` | 1.1 | 0.835556 | -0.264444 | 270 |
| NET | `1631109`, `1631217` | -24.2 | -23.921429 | 0.278571 | 112 |
| NET | `1631109`, `1642275` | -12.6 | -12.392562 | 0.207438 | 363 |
| NET | `1631209`, `1641733` | 15.1 | 14.831111 | -0.268889 | 90 |
| NET | `1631209`, `1642275` | -17.5 | -17.222407 | 0.277593 | 241 |
| NET | `1642275`, `1642354` | -12.6 | -12.364319 | 0.235681 | 639 |

The errors are consistent with information loss from rounded partial-window fields, but Phase 1E does not have a documented exact internal denominator/formula proving that explanation. The continuation exception therefore cannot be invoked.

### Independent Base scoring/plus-minus derivation

The audit also tested `100 × PTS / POSS`, `100 × (PTS - PLUS_MINUS) / POSS`, and `100 × PLUS_MINUS / POSS` against official offense, defense, and net ratings.

- Offense: MAE 0.023085, max 0.049275, 250/250 within 0.1
- Defense: MAE 2.379619, max 26.7, 35/250 within 0.2
- Net: MAE 2.380448, max 26.7, 32/250 within 0.2
- Classification: **unsupported**

Base team scoring plus/minus and returned integer possessions do not support exact defensive/net target derivation. Phase 1E does not force this method to pass.

## Possession-threshold sensitivity

This table is diagnostic only; no final threshold is selected.

| POSS threshold | Recovered-union rows | Recovered-only rows | Full-season rows | Any known omission eligible? | Omitted POSS / retained-union POSS | Omitted POSS share |
|---:|---:|---:|---:|---|---:|---:|
| 1 | 256 | 6 | 250 | yes | 23 / 82,555 | 0.027860% |
| 5 | 252 | 2 | 250 | yes | 12 / 82,544 | 0.014538% |
| 10 | 244 | 0 | 244 | no | 0 / 82,489 | 0% |
| 25 | 232 | 0 | 232 | no | 0 / 82,270 | 0% |
| 50 | 208 | 0 | 208 | no | 0 / 81,365 | 0% |
| 100 | 170 | 0 | 170 | no | 0 / 78,407 | 0% |

Known omissions cease to affect the threshold-eligible population at the evaluated `POSS >= 10` sensitivity point. This does not select `10` as the final reliability threshold and does not prove that unknown omissions are absent above it.

## Charlotte continuation gate and Philadelphia

| Charlotte condition | Result |
|---|---|
| Four responses validate | pass |
| Both child windows below 250 | pass |
| Union contains every full-season key | pass |
| Union contains all Phase 1D proving keys | pass |
| Base/Advanced reconciliation structurally sound | pass |
| Additive Base totals and possessions reproduce | pass |
| Every positive-possession rate recomposition within 0.2, or exception proven rounding-only | **fail** |

The gate failed solely on unproven target-rate recomposition exceptions. Per authorization, Philadelphia requests 5–8 remained planned with zero attempts. Phase 1E therefore makes no claim about whether this recovery method works for Philadelphia.

## Cache-only replay and implementation verification

- Two independent Phase 1E cache-only replays: identical
- Canonical replay SHA-256 for both: `8122497c32fc18dfc427011568cd58c32517372b811e4b9d790ce6366a38a0ba`
- Replay classification: `window recovery demonstrated; target recomposition unresolved`
- Replay transport surface: none
- Focused Phase 1E tests after acquisition: 15 passed
- Complete offline research suite after acquisition: 169 passed
- Both replay invocations left the Phase 1E ledger byte-for-byte unchanged at SHA-256 `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde`
- Phase 1C manifest remained `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c`; Phase 1D ledger remained `f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9`
- All nine Phase 1E payload, metadata, and ledger files were confirmed Git-ignored
- Prohibited-artifact search found no Parquet, DuckDB, Feather, SQLite/database, or 2025-26 research artifact
- Stale-language search found no incorrect Marcus Garrett first name or still-pending Phase 1E wording
- `git diff --check` passed
- Final working tree contains only the nine intended research documentation, implementation, and test paths; no production path changed

Pytest emitted two non-failing Windows warnings because its optional pre-existing `.pytest_cache` directory is not writable. The mandated `.pytest_tmp` basetemp worked and was safely removed after verification.

## Implication

Windowing is feasible for recovering Charlotte's omitted low-exposure pair population and exact additive totals. It is not yet a trustworthy general reconstruction of official defensive/net rating targets from rounded window rate fields. A later phase could investigate documented underlying possession/numerator contracts or an additive target formulation, but this phase does not expand requests, select a threshold, create a curated dataset, or train a model.
