# Phase 1C raw-season completion report

## Status

**Complete raw request set; clean raw-season release passes with an endpoint-exhaustiveness caveat.** Phase 1C reconciled all eight pilot assets and acquired the other 52 assets. All 60 assets are verified; none is planned, failed, acquired-but-unverified, or quarantined. The complete-season manifest gate and clean raw-season release gate both pass.

The 30-team/60-asset request set is complete and every returned row is validated. Four responses contain exactly 250 rows, however, and cached evidence cannot establish whether 250 is a server-side limit. Exhaustiveness of the endpoint-returned pair population therefore remains an explicit data-source uncertainty for Philadelphia and Charlotte.

**Phase 1D follow-up (superseding only the unresolved Charlotte population conclusion):** A later authorized Charlotte `LastNGames=41` Base diagnostic found three valid pair keys outside Charlotte's full-season 250-row Base set. Charlotte's full-season returned population is therefore `proven_non_exhaustive`, although the evidence does not establish a hard top-250 implementation. Phase 1C's 30-team/60-asset request-set completeness, asset hashes, schemas, 5,297 returned-row integrity, and one-to-one Base/Advanced reconciliation remain unchanged. See `PHASE1D_ENDPOINT_EXHAUSTIVENESS_REPORT.md`.

## Starting state and authorization

- Branch: `research/pair-fit-v2`
- Starting HEAD: `2dbbfcdbe29c59a3d77a575afbf0c0d17d1c5c1c`
- Initial working tree: clean (`git status --short --untracked-files=all` returned no entries)
- Phase 1B baseline: 121 offline tests passed
- Continuation branch/HEAD: `research/pair-fit-v2` at `2dbbfcdbe29c59a3d77a575afbf0c0d17d1c5c1c`; the expected dirty Phase 1C implementation/report tree was preserved without reset, discard, branch change, or history rewrite
- Continuation pre-request suite after the one-request guards and boundary diagnostic: 138 offline tests passed
- Authorized scope: at most 52 new live attempts, covering only the 26 non-pilot teams, Base and Advanced, 2024-25 Regular Season, `TeamDashLineups`, `GroupQuantity=2`, NBA league ID `00`
- Continuation authorization: after the safe 59/60 checkpoint exhausted those 52 attempts, the user authorized exactly one additional attempt for Charlotte Advanced asset `raw-asset:fba20fd528e8c626f2e343ee`; no retry or other request was authorized
- Persisted manifest ID: `season-manifest:3caa17ef8d9d465ab3e803f2`
- Deterministic manifest path: `cache/phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json` (Git-ignored)

The cached 2024-25 `LeagueStandingsV3` response supplied the authoritative 30 team IDs. Its canonical JSON hash recomputed to the recorded `b44b1f751bba84da`, with exactly 30 distinct teams and the expected league, season, and season-type context.

## What was designed and fixture-tested

The Phase 1C implementation adds:

- atomic persisted-manifest creation, load, validation, and transition writes;
- deterministic team-major, Base-then-Advanced asset order;
- immutable asset-ID-derived raw cache destinations;
- explicit legacy pilot-metadata reconciliation without inventing unavailable acquisition time, HTTP status, response-body size, or raw-body hash;
- dry-run and explicit live-acquisition entry points;
- sequential direct HTTP with fixed headers, no proxy, no concurrency, no retry, a 30-second timeout, and a fixed delay;
- immediate-stop behavior with persisted categorized failure information;
- schema/result-set/row-width validation before verification;
- cache replay before each asset advances to `verified`;
- complete-season manifest, pair identity, Base/Advanced join, target, and exposure auditing.
- an auditable one-request authorization extension tied to one sole planned asset, plus per-run asset-ID and attempt-count guards;
- an exact-250-row review signal that does not automatically classify a response as truncated.

Constructed fixtures and mocked transport cover deterministic persistence/reload, atomic replacement, dry-run behavior, 8/52 reconciliation, verified-cache skipping, first-missing resume, failure persistence, immediate stop, no automatic retry, explicit retry, schema quarantine, replay-before-advance, per-stage persistence, accidental-network prevention, a successful 60-asset simulation, incomplete/quarantined release failure, the hardened Phase 1B identity checks, the one-asset live guard/authorization extension, and neutral exact-boundary reporting.

## Existing pilot reconciliation

Before any live attempt, all eight pilot payloads matched their recorded canonical hashes, complete core request context, required result sets, row widths, and approved schemas:

| Team | ID | Base hash prefix | Advanced hash prefix | Rows per measure |
|---|---|---|---|---:|
| Boston Celtics | `1610612738` | `2d02052655469872` | `b8174589a6727ee3` | 141 |
| Golden State Warriors | `1610612744` | `71e194d4338e09b0` | `58b62bbde00ba68a` | 183 |
| Brooklyn Nets | `1610612751` | `f17163909cbfae2b` | `68c1916f0ac6edda` | 204 |
| Washington Wizards | `1610612764` | `31c70fcac7c8e03a` | `05e9e403129391d9` | 208 |

Historical metadata does not record every fixed query parameter or modern provenance field. The manifest explicitly identifies those fields as unavailable and records the versioned historical direct-fetch contract used for reconciliation. It does not fabricate values.

The post-reconciliation state was exactly 8 verified, 52 planned, and 60 unique asset IDs. The hardened complete-season gate correctly returned false with 52 unverified assets.

## Live acquisition outcome

- Transport invocations: **53**
- Invocations receiving HTTP 200 JSON: **52**
- Locally blocked before an HTTP response: **1**
- Newly verified assets: **52**
- Existing verified assets skipped: **8**
- Current failed assets: **0** (Atlanta Base succeeded on its explicit retry)
- Quarantined assets: **0**
- Current planned assets: **0**
- Total verified assets: **60**

The first Atlanta Base invocation failed locally with `WinError 10013` before any HTTP response. The queue stopped and persisted that failure. After request-parameter correction and an explicit retry flag, Atlanta Base succeeded and the runner continued sequentially. It then stopped safely at 59/60 before Charlotte Advanced because the original 52-attempt authorization was exhausted.

Before the continuation request, two offline replays verified all 59 caches, the manifest reported exactly 59 verified and 1 planned, and dry-run skipped those 59 and proposed exactly one action: Charlotte Advanced. The user-authorized extension raised the manifest limit to 53 and named only `raw-asset:fba20fd528e8c626f2e343ee`. The runner made exactly one request and no retry: HTTP 200 in `1.9702203000197187` seconds, 67,223 response/cache bytes, 250 `Lineups` rows, canonical JSON hash `17d6894350748b824635e394e4f723fa8491b6352fe29bdaff5d0a43fcf39a23`. Both Advanced fingerprints were identical to contract and cached replay promoted the asset to verified.

## Per-team raw rows and Base/Advanced reconciliation

| Team | ID | Base | Advanced | Matched | Base-only | Advanced-only |
|---|---:|---:|---:|---:|---:|---:|
| Atlanta Hawks | `1610612737` | 169 | 169 | 169 | 0 | 0 |
| Boston Celtics | `1610612738` | 141 | 141 | 141 | 0 | 0 |
| Cleveland Cavaliers | `1610612739` | 164 | 164 | 164 | 0 | 0 |
| New Orleans Pelicans | `1610612740` | 222 | 222 | 222 | 0 | 0 |
| Chicago Bulls | `1610612741` | 190 | 190 | 190 | 0 | 0 |
| Dallas Mavericks | `1610612742` | 216 | 216 | 216 | 0 | 0 |
| Denver Nuggets | `1610612743` | 125 | 125 | 125 | 0 | 0 |
| Golden State Warriors | `1610612744` | 183 | 183 | 183 | 0 | 0 |
| Houston Rockets | `1610612745` | 131 | 131 | 131 | 0 | 0 |
| LA Clippers | `1610612746` | 188 | 188 | 188 | 0 | 0 |
| Los Angeles Lakers | `1610612747` | 208 | 208 | 208 | 0 | 0 |
| Miami Heat | `1610612748` | 167 | 167 | 167 | 0 | 0 |
| Milwaukee Bucks | `1610612749` | 192 | 192 | 192 | 0 | 0 |
| Minnesota Timberwolves | `1610612750` | 125 | 125 | 125 | 0 | 0 |
| Brooklyn Nets | `1610612751` | 204 | 204 | 204 | 0 | 0 |
| New York Knicks | `1610612752` | 164 | 164 | 164 | 0 | 0 |
| Orlando Magic | `1610612753` | 127 | 127 | 127 | 0 | 0 |
| Indiana Pacers | `1610612754` | 162 | 162 | 162 | 0 | 0 |
| Philadelphia 76ers | `1610612755` | 250 | 250 | 250 | 0 | 0 |
| Phoenix Suns | `1610612756` | 161 | 161 | 161 | 0 | 0 |
| Portland Trail Blazers | `1610612757` | 140 | 140 | 140 | 0 | 0 |
| Sacramento Kings | `1610612758` | 218 | 218 | 218 | 0 | 0 |
| San Antonio Spurs | `1610612759` | 152 | 152 | 152 | 0 | 0 |
| Oklahoma City Thunder | `1610612760` | 143 | 143 | 143 | 0 | 0 |
| Toronto Raptors | `1610612761` | 206 | 206 | 206 | 0 | 0 |
| Utah Jazz | `1610612762` | 172 | 172 | 172 | 0 | 0 |
| Memphis Grizzlies | `1610612763` | 181 | 181 | 181 | 0 | 0 |
| Washington Wizards | `1610612764` | 208 | 208 | 208 | 0 | 0 |
| Detroit Pistons | `1610612765` | 138 | 138 | 138 | 0 | 0 |
| Charlotte Hornets | `1610612766` | 250 | 250 | 250 | 0 | 0 |
| **Total** |  | **5,297** | **5,297** | **5,297** | **0** | **0** |

All 30 teams have 100% one-to-one Base/Advanced matches, zero unmatched keys, and zero duplicate-key violations. The full outer union is 5,297 observations.

Across the partial season:

- Base: 5,297 rows, 5,297 unique full observation keys, 0 duplicate keys, 81 players and 13 pairs observed for more than one team.
- Advanced: 5,297 rows, 5,297 unique full observation keys, 0 duplicate keys, 81 players and 13 pairs observed for more than one team.
- Malformed group identifiers, same-player rows, and within-measure duplicate canonical pairs: 0.

Cross-team players and pairs are reported, not deduplicated: team ID is part of full observation identity.

## Schema findings

Every verified asset contains exactly one `Overall` and one `Lineups` result set; every row width matches its header width. All fingerprints classify as identical to the approved measure-specific contracts:

| Measure | Overall columns | Lineups columns | Verified assets | Classification |
|---|---:|---:|---:|---|
| Base | 57 | 56 | 30 | identical |
| Advanced | 49 | 48 | 30 | identical |

Row counts are recorded separately as data volume and are not part of schema identity. No field was reordered, renamed, added, removed, coerced, or filled.

## Targets and exposure

The 5,297 verified Advanced rows have no missing or nonnumeric `OFF_RATING`, `DEF_RATING`, `NET_RATING`, `POSS`, or Advanced `MIN` values. `NET_RATING` agrees with `OFF_RATING - DEF_RATING` within the documented 0.2 displayed-rounding tolerance on all 5,297 rows; maximum absolute difference is `0.10000000000002274`.

| Field | Minimum | Median | P25 | P75 | Maximum | Mean where reported |
|---|---:|---:|---:|---:|---:|---:|
| Base `MIN` | 0.0 | 98.21 | 24.616667 | 283.631667 | 2354.463333 | — |
| Advanced `POSS` | 0.0 | 211.0 | 54.0 | 603.0 | 4817.0 | 475.19898055503114 |
| Advanced `MIN` | 0.0 | 98.0 | 25.0 | 284.0 | 2354.0 | 224.10458750235983 |
| `OFF_RATING` | 0.0 | — | — | — | 300.0 | 105.86543326411176 |
| `DEF_RATING` | 0.0 | — | — | — | 266.7 | 109.03007362658109 |
| `NET_RATING` | -250.0 | — | — | — | 300.0 | -3.1649424202378706 |

Sparse-exposure counts are descriptive only; no positive threshold was selected:

| Exposure | `<10` | `<25` | `<50` | `<100` | `<200` |
|---|---:|---:|---:|---:|---:|
| Base `MIN` | 670 | 1,331 | 1,957 | 2,665 | 3,528 |
| Advanced `POSS` | 321 | 736 | 1,270 | 1,885 | 2,595 |
| Advanced `MIN` | 652 | 1,321 | 1,949 | 2,659 | 3,521 |

Target eligibility is 5,289 eligible and 8 ineligible. All eight reason codes are `nonpositive_possessions`. No row was filtered, imputed, or altered.

## Exact zero/missing-possession findings

There are eight zero-possession rows, no missing/nonnumeric/negative possession rows, and every returned rating is retained unchanged:

| Team ID | Pair | Canonical IDs | Base MIN | Advanced MIN | POSS | OFF | DEF | NET | Eligible |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `1610612747` | A. Davis - C. Koloko | `1631132`, `203076` | 0.035 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |
| `1610612749` | B. Lopez - C. Livingston | `1641753`, `201572` | 0.15 | 0.0 | 0 | 0.0 | 200.0 | -200.0 | no |
| `1610612749` | G. Antetokounmpo - T. Smith | `1641890`, `203507` | 0.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |
| `1610612757` | D. Ayton - D. Clingan | `1629028`, `1642270` | 0.008333 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |
| `1610612760` | J. Williams - A. Ducas | `1631114`, `1642505` | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |
| `1610612761` | G. Temple - D. Carton | `1630618`, `202066` | 0.22 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |
| `1610612764` | K. Middleton - J. McDaniels | `1629667`, `203114` | 0.143333 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |
| `1610612765` | A. Thompson - D. Jenkins | `1641709`, `1642450` | 0.363333 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | no |

The Washington Middleton–McDaniels row remains present and ineligible. It is not the only zero-possession case in the expanded evidence. These are the exact complete-season findings: 8 zero, 0 missing, 0 negative, and 0 nonnumeric possession values.

## Exact-250-row diagnostic

Four responses land exactly on 250 rows. The diagnostic records an exact boundary as a review signal only and never automatically classifies truncation.

| Team | Measure | Rows | Distinct players | Theoretical unordered pairs | Returned canonical pairs | Theoretical pairs absent | Minimum exposure | Lowest five exposures |
|---|---|---:|---:|---:|---:|---:|---|---|
| Philadelphia 76ers | Base | 250 | 30 | 435 | 250 | 185 | `MIN=6.333333` | `MIN=6.333333, 6.483333, 7.35, 7.358333, 7.366667` |
| Philadelphia 76ers | Advanced | 250 | 30 | 435 | 250 | 185 | `POSS=13`, `MIN=6` | `POSS=13, 15, 15, 15, 16`; `MIN=6, 6, 7, 7, 7` |
| Charlotte Hornets | Base | 250 | 27 | 351 | 250 | 101 | `MIN=2.833333` | `MIN=2.833333, 3.033333, 3.266667, 3.633333, 4.2` |
| Charlotte Hornets | Advanced | 250 | 27 | 351 | 250 | 101 | `POSS=5`, `MIN=3` | `POSS=5, 6, 7, 8, 8`; `MIN=3, 3, 3, 4, 4` |

The theoretical comparison is combinatorial, not a claim that every pair actually shared the court. For Philadelphia, `MIN_RANK` reaches 250 in both measures; the maximum returned rank is 271 and 20 Base/15 Advanced rank fields exceed 250. For Charlotte, `MIN_RANK` reaches 250 in both measures (`FTA_RANK` also reaches 250 in Base); the maximum returned rank is 257 and 13 Base/14 Advanced rank fields exceed 250. Those ranks and the materially higher exposure floors than nearby sub-250 teams are consistent with a possible returned-row boundary. The three closest lower-count teams are New Orleans (222; Base minimum `MIN=0.026667`, Advanced minima `POSS=1`, `MIN=0`), Sacramento (218; `MIN=0.01`, `POSS=1`, Advanced `MIN=0`), and Dallas (216; `MIN=0.19`, `POSS=2`, Advanced `MIN=0`).

All 250 rows in each boundary response have distinct valid canonical pair identities, and their minimum returned exposures are positive. That is consistent with 250 genuinely observed returned pairs, but it does not establish that no additional observed pairs were omitted. The lowest Philadelphia Base row is C. Okeke–A. Bona (`MIN=6.333333`); its Advanced minimum-possession row is G. Yabusele–P. Nance (`POSS=13`). Charlotte's lowest Base row is N. Richards–M. Diabate (`MIN=2.833333`), and the same pair is the lowest Advanced-possession row (`POSS=5`).

The raw envelopes contain only top-level `parameters`, `resource`, and `resultSets`; each result set contains only `name`, `headers`, and `rowSet`. No pagination, total-count, limit, continuation, or truncation metadata appears. This supports neither a definitive cap nor proven exhaustiveness. The 30-team/60-asset request set is complete and every returned row is validated, but exhaustiveness of the endpoint-returned pair population remains an explicit data-source uncertainty for teams returning exactly 250 rows.

## Manifest gate and cache-only replay

- Hardened complete-season manifest gate: **true**
- Clean raw-season release: **true**
- Manifest state: 60 verified; 0 planned, failed, acquired-but-unverified, or quarantined
- Current cache replay errors: 0
- Failed/quarantined/acquired-but-unverified assets: 0

Two cache-only validations made zero network requests and produced identical manifest IDs, asset IDs, canonical hashes, schema fingerprints, row counts, pair keys, joins, eligibility summaries, exposure summaries, and gate result. Canonical replay-summary hash:

`9a0d94396fe0de5826b7bafc3f16bfd527722de51695b92862510316f88ea68b`

## How persistence prevents duplicate work

The manifest fixes the season/request identity and deterministic asset order. On every load it recomputes the manifest ID, every asset ID, and every asset-to-manifest identity. Each successful transition is atomically persisted. A verified asset is skipped only after its immutable cache file, canonical hash, byte size, metadata, result sets, row widths, team identity, and schema replay successfully. A failed or quarantined asset stops the queue, and later assets remain planned. This makes interruption recoverable without overwriting verified evidence or repeating completed requests.

## Remaining work and recommendation

Phase 1C is complete at the validated raw-cache and manifest layer. At this checkpoint, a next phase could proceed only after accepting or resolving the exact-250 endpoint-exhaustiveness uncertainty. Phase 1D later proved non-exhaustiveness for Charlotte, so the superseding recommendation is a separate recovery-feasibility phase before curated materialization, historical expansion, or model training. The exposure policy, missing-history treatment, and time-ordered validation design remain additional prerequisites.

No Parquet, DuckDB, Feather, database, curated analytical table, model, validation split, higher-order lineup ingestion, prior-player fetch, or other-season access occurred.

## Appendix: live attempt ledger

The first row has no latency, response bytes, or canonical hash because the local socket was blocked before an HTTP response. All following rows received HTTP 200 and passed cached replay.

| # | Team | Measure | Outcome | Latency (s) | Response bytes | Asset ID | Canonical JSON hash |
|---:|---|---|---|---:|---:|---|---|
| 1 | Atlanta Hawks | Base | local connection failure | — | — | `raw-asset:ebd8c0eecc46a033917b8380` | — |
| 2 | Atlanta Hawks | Base | verified | 2.174745 | 44,396 | `raw-asset:ebd8c0eecc46a033917b8380` | `81b7b607b412c3b983a76eb8d8535b9cc23b3d6bffd36edb19a5a88324d88244` |
| 3 | Atlanta Hawks | Advanced | verified | 1.609741 | 45,523 | `raw-asset:f834cc0a393e4a4d1226dea0` | `57a9278f22ffd6511c6a0a86abc5e8e3ad27bd37e7dcf239e72062c40ebd993b` |
| 4 | Cleveland Cavaliers | Base | verified | 1.533438 | 42,579 | `raw-asset:e74f66093a7bf4dd0ec232d4` | `9cc2b8bd07d9224598ec08be23ca3c72d732cacf06ae69011ce3525fe44ea706` |
| 5 | Cleveland Cavaliers | Advanced | verified | 1.467765 | 43,839 | `raw-asset:138df0f15eb52c7015276f7a` | `a02f8951707aac9351573a27edbeb0a91f09cd7acf41942d7c1fc06c32868d87` |
| 6 | New Orleans Pelicans | Base | verified | 1.636819 | 58,653 | `raw-asset:9d4c0aea1e7d4bc3a0295b88` | `2b85e5b2840c4dc1093031fc1f148a6efcb9bcc94cab94a4fdd78bc593f78db1` |
| 7 | New Orleans Pelicans | Advanced | verified | 1.762775 | 60,082 | `raw-asset:722bdc1d80f6d9a580af23e2` | `1707bd69db297fb34bc797590c4a333a80eb0c6496aef06b8b36abfc1fcacd5c` |
| 8 | Chicago Bulls | Base | verified | 1.641448 | 49,284 | `raw-asset:f76495b4a693f964a20b9a9a` | `de3ba9445dcb1d4ac4c448fe8c4f6610ab2ae750f3f497ebcd18dd8d28412d3a` |
| 9 | Chicago Bulls | Advanced | verified | 1.624497 | 50,946 | `raw-asset:1b55605fdcbfe523c60a181f` | `ebe91efb1ee5191a37af8fb056ae0c3acf0b8ff9f12bcef8778a16ed3487e92d` |
| 10 | Dallas Mavericks | Base | verified | 1.733631 | 56,501 | `raw-asset:8768bc2a3194df4500aab1a3` | `1ac2bc48575610a45cb84877f282d9bd28283066116d6685d1132209ccadf011` |
| 11 | Dallas Mavericks | Advanced | verified | 1.540899 | 58,150 | `raw-asset:9d8e5f95fee5836eca44d03d` | `2471dab4c46120c4f80aea219336bb33d9585056c7ac05953f600b4b9b47be2a` |
| 12 | Denver Nuggets | Base | verified | 1.676702 | 32,615 | `raw-asset:82405cce37ae0e6a9ea04a9d` | `f3b4cb299506879ddfa56038410ace6fe1692141c713b7a35fedbf50adc7737d` |
| 13 | Denver Nuggets | Advanced | verified | 1.601662 | 33,578 | `raw-asset:43fb2eb7b93c3fc3bf4f1b0a` | `625073d61a2d4ecd046eae99233d73c5a052991e99a66ab45f2befec3faa34ed` |
| 14 | Houston Rockets | Base | verified | 1.740021 | 34,287 | `raw-asset:635c5793140245243afa2e30` | `5c4689745eb3da8ff97ef9f9ee1d4835723d792497ae4765a40759a49b2041dd` |
| 15 | Houston Rockets | Advanced | verified | 1.431278 | 35,318 | `raw-asset:b4ef9658b6500c48f55a6d4c` | `3df463fc0c792fbbda8aa22aa98ec6f3bd75a2f0ce67cbd1a470d0d152bf80ae` |
| 16 | LA Clippers | Base | verified | 1.896593 | 48,308 | `raw-asset:08ca0d71b2286aa11f6ab4de` | `da5609562092abf2b40c44ffbe6f53cd6154d5bf2df509abbafa7f56daca91b5` |
| 17 | LA Clippers | Advanced | verified | 1.541122 | 49,870 | `raw-asset:771e820d437566b3b1dc389c` | `5a34dfb4da915c76e3206f92cb2c4dd3347b05c166b35c3feda248394745e087` |
| 18 | Los Angeles Lakers | Base | verified | 1.882129 | 53,825 | `raw-asset:5982fa0f7d4f5b1bd11c4e2b` | `cea8c178933bee1b281970e9e4fb2207b5914fa6c7fe7ca61b2c5c0f8d9696db` |
| 19 | Los Angeles Lakers | Advanced | verified | 1.467701 | 55,547 | `raw-asset:93f2a2f311fede9b2685c236` | `63021377bcbc8ac56ce1050b15fa76e515be6edaffdc70734989dc4de3219008` |
| 20 | Miami Heat | Base | verified | 1.829319 | 43,746 | `raw-asset:05642e3a7146eaa05cddba0e` | `8d8d6c3569a556bdb86cd36b08748ba4492ce6e4291185df20b0c1f94d824c5f` |
| 21 | Miami Heat | Advanced | verified | 1.471423 | 44,708 | `raw-asset:994968dbdbc828dc68ba0a62` | `225f0dbce35bf359c01f97093868a92804db54134cbb08053715ed89dac31b6a` |
| 22 | Milwaukee Bucks | Base | verified | 1.690821 | 49,734 | `raw-asset:65ef6ffe30df9565d3996177` | `3039bbbf648125701c6dad92dbe0a9356816d6ba32769d15348ec67fe5aa3274` |
| 23 | Milwaukee Bucks | Advanced | verified | 1.671869 | 51,478 | `raw-asset:5144e099632c46664be713bb` | `acae9c3ae811d98805500a8c434e9705f0ae5b0b0f88480792d37f3923e5f387` |
| 24 | Minnesota Timberwolves | Base | verified | 1.654525 | 32,255 | `raw-asset:8ceb8fac41f847a14d119fe2` | `98b94b3800baacc81255a95e79f8e6c9d346d0983f07ab8d0b9352d680d6577b` |
| 25 | Minnesota Timberwolves | Advanced | verified | 1.724489 | 33,497 | `raw-asset:90610b2a8089d3706d521160` | `69e450e6ba2cbd3a87a99366674e169dc73fb823e3d5221821b8cd0b2e9847a6` |
| 26 | New York Knicks | Base | verified | 1.798132 | 41,738 | `raw-asset:ff9a5b0cef097d16eafe2ba8` | `f8555541e8b3d784a6ca5d0af3c174d6ef91e8ccc369f3937687500d80ebdfa1` |
| 27 | New York Knicks | Advanced | verified | 1.508051 | 43,489 | `raw-asset:f432bb8753447ac7cceae279` | `8f5c18215aadae920874d63056749fa846c37094205abd4cdd66cc51873d123e` |
| 28 | Orlando Magic | Base | verified | 1.636688 | 33,957 | `raw-asset:050de785be38af03da7aac6a` | `4709df8bf40fb23351eff05e2490cc91ad8e88a99dec964da89ac89b4dcecce2` |
| 29 | Orlando Magic | Advanced | verified | 1.229840 | 34,382 | `raw-asset:c2d3a9acd90903f896dd4697` | `0ffd1b7f1885b1596057c7fa3b0426aaba45c2ce3f2ced120584874495a45f37` |
| 30 | Indiana Pacers | Base | verified | 1.907230 | 41,798 | `raw-asset:e4807077210e114a9826e1c7` | `730d2151334c6f32caedcd001ba3482ba9b912de01b5652654b4f23ce79abacd` |
| 31 | Indiana Pacers | Advanced | verified | 2.145198 | 43,421 | `raw-asset:e681d1a418b0d09e617bcf68` | `0016f91f0738e623d4275b82ecf4ca1b314e98e3e6c63ff2a6d440920f167779` |
| 32 | Philadelphia 76ers | Base | verified | 1.759594 | 65,799 | `raw-asset:6b803e656069159dcc749506` | `cedf359e12a07f9800bd7657915d0858cadb8b96c410731b16bd8dbadc16e07b` |
| 33 | Philadelphia 76ers | Advanced | verified | 2.020554 | 67,595 | `raw-asset:a84f29147cb44a05f57ba262` | `a3e4810bcf2d3f939b6e34eb2bf6bd70145eb6849abe22819dc1276d984cdff4` |
| 34 | Phoenix Suns | Base | verified | 1.647184 | 41,872 | `raw-asset:283213ac596fd97be830d1d3` | `63b4dbd3e1c6de3c12bfe798a1419d1de2ef9d46d398c0d0efcdb5929871d73c` |
| 35 | Phoenix Suns | Advanced | verified | 1.677645 | 43,040 | `raw-asset:2b93281b770416b1b8dfcb86` | `d3afe685ec646c65eed0e4b02737faeaf7cd69ef1080e1c8f753e43dd10fc91e` |
| 36 | Portland Trail Blazers | Base | verified | 1.757763 | 36,554 | `raw-asset:187b97cd4706cd01b2277a0c` | `9b6696651a967ae99c8451b7376e766a33d69286faa3baf43fcbc304ef7a1f16` |
| 37 | Portland Trail Blazers | Advanced | verified | 1.693242 | 37,553 | `raw-asset:433c8ca7021143d2c1b63895` | `df68691cbc2c2268f90d8d2ce74c556665651de3368eaaa20f43a98908fe1438` |
| 38 | Sacramento Kings | Base | verified | 2.092100 | 55,427 | `raw-asset:ac3fe0ba7241be3f28171187` | `9cc752e69e1b167b8ffaa857e067f850083909ca1ef374d0b841df651819db04` |
| 39 | Sacramento Kings | Advanced | verified | 2.359926 | 57,675 | `raw-asset:8df2922d5f2727a991a85cfa` | `ea401b8f57675f981660b9727678a6d294bbb269447b26239c7684e4535ad933` |
| 40 | San Antonio Spurs | Base | verified | 1.605398 | 39,977 | `raw-asset:6af4816de9ef1e7ceb199d3a` | `42562b457ce15c1210df4ce5870b2fbcf6894371490b85a22d27103494cc0e32` |
| 41 | San Antonio Spurs | Advanced | verified | 1.938472 | 41,110 | `raw-asset:65d79c66c2911a0c940ceb9f` | `f0245fdba92e9732010959eddd25bcd5fc1556e77c06086536ece49f1f06d234` |
| 42 | Oklahoma City Thunder | Base | verified | 1.760824 | 37,685 | `raw-asset:266916bc51660a7427628101` | `06dc69b584441d3787d8616f3ee2794288c363aea212f555e5d290cf4c57533a` |
| 43 | Oklahoma City Thunder | Advanced | verified | 1.514362 | 38,522 | `raw-asset:bcd26b936dac81cdbda10e99` | `5f995bf5b2b92a45f2680852d5de4cd97ff47851bffba586db5fd70da49bca7e` |
| 44 | Toronto Raptors | Base | verified | 2.070754 | 53,815 | `raw-asset:18c0e9d7db34a3a52dc22ebf` | `d4da74711b59b6eee3f92e1a1de9195c5fe90f19730a495f63b91277eca2e39c` |
| 45 | Toronto Raptors | Advanced | verified | 1.529486 | 55,380 | `raw-asset:dab021ef2f2654ff73ae5f4c` | `0d7f978b878b7e2bc0d5837e2298c8f94d82f55b5a33ca42f16df679c76d1982` |
| 46 | Utah Jazz | Base | verified | 1.787141 | 45,820 | `raw-asset:294aafc8ff7cf420bb3c59c2` | `13d012fa2472b8bc67be52d7519da365fe4812008b3e9888172dfa057aca3723` |
| 47 | Utah Jazz | Advanced | verified | 1.925986 | 46,883 | `raw-asset:2a167ce610b46835a94597b1` | `61cfaf7cb5351e093290ec008b58d0399e3768086de0500a962990f34ed595e6` |
| 48 | Memphis Grizzlies | Base | verified | 1.744474 | 47,583 | `raw-asset:7fb049896667998a9380d0f7` | `7a1c44ea9dad8e7bc278bd2b6a2900f76fda49fc6a791e877d0f3aa4a6721658` |
| 49 | Memphis Grizzlies | Advanced | verified | 1.516686 | 48,851 | `raw-asset:525d68d1e33a8db5de4fee21` | `c32f3dfe9373923d86fd3e2b7fa81042673c56cd45d2a2cacad09c522245b8b7` |
| 50 | Detroit Pistons | Base | verified | 1.697879 | 36,051 | `raw-asset:4c9c453bea62c58f956338c9` | `5817f56ea3e6f378d96ee25bd2562cd6936e5b2545d6941c13937acf55d03127` |
| 51 | Detroit Pistons | Advanced | verified | 1.504794 | 37,188 | `raw-asset:a3fdd32fb935cf3f9b1fac67` | `bb9ab6f33ac9b1e12f78776b653248185e445fc7d46d78e5ef9eb9d764f4bb06` |
| 52 | Charlotte Hornets | Base | verified | 1.864568 | 65,518 | `raw-asset:a72f18f99a00a85ca45e873c` | `8ec04094d5d1faed13de3c5969d8aa5add454cafd313af07941a9c3aadeebd80` |
| 53 | Charlotte Hornets | Advanced | verified | 1.970220 | 67,223 | `raw-asset:fba20fd528e8c626f2e343ee` | `17d6894350748b824635e394e4f723fa8491b6352fe29bdaff5d0a43fcf39a23` |
