# Phase 3A.1: bounded prior-player shooting-zone acquisition and feasibility audit

Primary classification: **`shot-zone acquisition incomplete; continuation blocked`**.

## Result

The first required canary, 2023-24, reached the official `LeagueDashPlayerShotLocations` endpoint successfully (HTTP 200), but it was not accepted and the acquisition stopped before the oldest-season canary or any other identity. The immutable quarantined response has an actual nested `ShotLocations` result structure rather than a `resultSets` list: six identity columns followed by three labeled fields (`FGM`, `FGA`, `FG_PCT`) for each source category. It includes all seven requested categories plus the source-provided aggregate `Corner 3`.

Cache-only inspection of that response also found null source `FGM` and `FGA` pairs in several requested zones. The Phase 3A.1 canary contract requires numeric, nonnegative `FGM` and `FGA`, so this is an applicable validation-gate failure. It must not be silently coerced to zero or treated as a zero-attempt percentage. The original validator first stopped on its overly narrow outer-result-set assumption; the subsequent read-only inspection made the more specific source-value issue explicit. No retry or further request was made.

## Starting state and immutable prerequisites

- Repository root: `C:\Users\mehan\code\hanson-hoops`
- Branch: `research/pair-fit-v2`
- HEAD: `d8befcad3e12234cd11c80fb9fd6a1af674a6316`
- Latest commit: `Phase 3A completed and population audit completed.`
- Initial tree: clean (`git status --short --untracked-files=all` produced no entries).
- Phase 3A deterministic cache-only SHA-256 reproduced: `dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f`.
- All committed Phase 2 state anchors (20 manifest/ledger hashes), Phase 1 anchors, and Phase 2E combined analysis (`d57840f80172df49ea7350520fbf1961499c6f558c70c40ced2bab38c7b5379f`) reproduced unchanged before live work.

No 2024-25 or 2025-26 endpoint request was made. The already-acquired local 2023-24 Base cache was read only for the requested player-ID reconciliation.

## Authorization and request accounting

The read-only dry run and exact allowlist contain 11 identities in this deterministic order: 2023-24, 2013-14, then 2014-15 through 2022-23. All identities specify Regular Season, league-wide scope, Base, Totals, By Zone, `PaceAdjust=N`, `PlusMinus=N`, `Rank=N`, `LastNGames=0`, and blank/no date or other filters. The cache paths are isolated under ignored `cache/phase3a1/{raw,metadata,manifest,ledger,quarantine}`.

| Item | Count |
|---|---:|
| Authorized first attempts | 11 |
| Authorized additional transient retries | 3 |
| Authorized total transport attempts | 14 |
| Actual transport attempts | 1 |
| Verified assets | 0 |
| Quarantined returned bodies | 1 |
| Retries | 0 |
| Further requests after failure | 0 |

The one body is immutable at the ignored quarantine path recorded by the ledger. Its byte count is 81,376; raw SHA-256 is `98108b58276756f2afc53ddd87c8287e1627fc740b5c5cfbafe2d48f98c8f444`; canonical JSON SHA-256 is `29c6cb48f6cb87935539a52bf8c4eed152a5c7d15963673958a5bf5ada38d4d5`.

## Canary and schema findings

| Classification | Result |
|---|---|
| Recent-season canary (2023-24) | HTTP/JSON/identity response received; **failed validation and quarantined** |
| Oldest-season canary (2013-14) | Not requested; correctly blocked by first-canary failure |
| Cross-season schema compatibility | Not assessed; only one unaccepted body exists |
| Player-season grain | Unresolved across the authorized window |
| Traded-player aggregation | Not assessed; no aggregation policy selected |
| Player-ID reconciliation | 572/572 matched to the acquired 2023-24 Base source for the one body; not a full-window finding |
| Zone-feature derivability | Blocked pending an explicit policy for null source makes/attempts and fresh authorization |
| Supplemental-source necessity | Unresolved; no team-by-team fallback requested |
| Phase 3B readiness | Blocked for shot-zone features |

The response’s `ShotLocations` nested header declares `columnsToSkip=6`, `columnSpan=3`, and these categories: Restricted Area, In The Paint (Non-RA), Mid-Range, Left Corner 3, Right Corner 3, Above the Break 3, Backcourt, and Corner 3. Thus FGM/FGA/FG_PCT association is visible and does not depend on guessing flattened positions. It is nevertheless not promoted because numeric field validation failed.

The 572 returned player IDs reconcile completely with the 572 IDs in the local 2023-24 Base source (no shot-only or Base-only IDs). There are no observed `FGM > FGA` pairs where both values are numeric. But the returned null `FGM`/`FGA` pair counts are: Restricted Area 2, non-restricted paint 1, Mid-Range 2, Left Corner 3 6, Right Corner 3 7, Above the Break 3 0, Backcourt 14, and Corner 3 3. These are source missing values, not verified zero attempts. No share, percentage, corner combination, or player-season profile was produced from them.

The deterministic single-body cache-inspection SHA-256 is `c6e4bc0ecc2e87d264342b3006020979674671c32f957afa9f03f7254c7a662d`. It describes only the unaccepted 2023-24 canary inspection and is not a feasibility certification.

## Required user decision

A separate authorization is required before any continuation: decide whether a documented, evidence-backed treatment of returned null zone FGM/FGA is acceptable, and authorize a new canary/acquisition plan if so. This phase intentionally made no such assumption, did not retry the failed code/schema gate, and did not request a team-by-team or supplemental fallback.

## Verification and scope

Focused offline tests passed (9 tests) using a short ignored test base directory, then that directory was removed. They cover exact identities/order/allowlist/protected seasons, nested headers, strict IDs, duplicate detection, safe denominators, immutable failure storage, attempt ceiling/network blocking, schema drift, and reconciliation fixtures. The full research suite is not applicable as a final successful-acquisition check because acquisition deliberately stopped before a complete cache exists.

No raw Phase 1/2 evidence changed; no curated dataset, pace acquisition, player event data, team-by-team data, model, fit score, database, production-code change, commit, or push was created.

---

## Continuation checkpoint: cache-only null-semantics review (stopped)

The separately authorized continuation began from the expected checkpoint: branch `research/pair-fit-v2`, HEAD `d8befcad3e12234cd11c80fb9fd6a1af674a6316`, the same latest Phase 3A commit, and exactly the four untracked Phase 3A.1 artifacts listed in this report. Phase 3A's deterministic hash again reproduced as `dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f`; the Phase 1 anchors, all 20 Phase 2 state anchors, and the Phase 2E combined analysis anchor again reproduced unchanged.

The stopped Phase 3A.1 event also reproduced unchanged. Its sole identity remains the authorized 2023-24 league-wide Regular Season Base/Totals/By Zone request; the manifest still marks it quarantined and the ledger still has exactly one attempt. The preserved quarantine path, 81,376-byte size, raw SHA-256 `98108b58276756f2afc53ddd87c8287e1627fc740b5c5cfbafe2d48f98c8f444`, and canonical JSON SHA-256 `29c6cb48f6cb87935539a52bf8c4eed152a5c7d15963673958a5bf5ada38d4d5` all match the continuation authorization.

No network call was made during this replay. The continuation must stop before the paired-null policy can be tested because the required already-cached 2023-24 `LeagueDashPlayerStats` Base/**Totals** player source is not present. The only matching local 2023-24 player response is Base/**Per100Possessions** (572 rows); the available historical Totals asset is for 2022-23, not 2023-24. Per-100 rates cannot establish the required exact player FGM/FGA reconciliation with season-total zone counts. Treating them as totals would be an unsupported conversion.

Therefore there is no cache-only reviewed promotion, no verified raw-cache copy, no review event, no oldest-season canary request, no further request, and no changed raw/ledger/quarantine evidence. This is a missing required input, not evidence that paired nulls are structural zeros or that source semantics are unsupported.

Primary classification remains: **`shot-zone acquisition incomplete; continuation blocked`**.

---

## Supplemented continuation: 2023-24 player-Totals dependency and oldest-canary stop

The separately authorized dependency checkpoint matched the prior stopped state. Phase 3A and all required Phase 2 anchors reproduced, and the original 2023-24 shot-zone quarantine body/event remained byte-identical: 81,376 bytes, raw SHA-256 `98108b58276756f2afc53ddd87c8287e1627fc740b5c5cfbafe2d48f98c8f444`, canonical JSON SHA-256 `29c6cb48f6cb87935539a52bf8c4eed152a5c7d15963673958a5bf5ada38d4d5`.

One new identity was authorized and requested exactly once: 2023-24 Regular Season, league-wide `LeagueDashPlayerStats`, Base/Totals. It returned HTTP 200 and the established 69-column player Base schema. Its 572 positive canonical, unique IDs exactly match the cached 2023-24 Base/Per100 ID set; all season-total FGM/FGA values are numeric, nonnegative, integral, and satisfy `FGM <= FGA`. The immutable verified body is 173,713 bytes, with raw SHA-256 `0a856d37c33218362a0b88fc645b7d609a64a7da0773a1be1368d22d07b54774` and canonical JSON SHA-256 `8d1efef313fbaf4a508a1e786e520feb1ad2161e0400e3f7003a1df062b6cd85`. No dependency retry was used.

### Reviewed 2023-24 promotion

The cache-only semantic review then passed for every one of the 572 2023-24 players. Paired null FGM/FGA was present in 35 player-zone cells affecting 15 players: Restricted Area 2, non-restricted paint 1, Mid-Range 2, Left Corner 3 6, Right Corner 3 7, Above the Break 3 0, Backcourt 14, and source aggregate Corner 3 3. There were no one-sided nulls, impossible counts, percentage contradictions, seven-zone totals discrepancies, or Corner 3 discrepancies.

The interpretation is narrowly documented: paired source null counts with null-or-zero source percentage normalize to `FGM=0` and `FGA=0`, preserve an undefined efficiency, and must retain source-null and attempted-zone indicators in any later representation. It is not statistical imputation and does not make a zero-attempt percentage a 0% result. The promoted raw copy is byte-identical to the retained quarantine body. The separate deterministic review event is `phase3a1.reviewed-promotion-2023-24.v1`; the original attempt event remains unchanged. The response has one aggregate zone vector per player ID; 78 corresponding totals players have `TEAM_COUNT > 1`, while the shot response itself emits only one row per player rather than team stints.

### Oldest 2013-14 canary

The next authorized request was the oldest canary, 2013-14. It was made once, returned HTTP 200, and was preserved immutably in quarantine. Its original validation event records a local lookup `KeyError` before the corrected cache-only review; it was not retried. The body is 67,696 bytes, raw SHA-256 `3528826a43d891b76f01c864cb746143fdbce07d97feec7ace0ee8550db2106a`, canonical JSON SHA-256 `1badf338fd029ccad2d7710792eedcee34ca55fc021dcd128da3356fa5591686`.

After the local cache lookup was corrected, the cache-only audit found: 482 unique shot-location IDs; paired-null cells 33 affecting 15 players (Backcourt 15, non-restricted paint 2, Left Corner 3 4, Right Corner 3 8, Corner 3 4); no one-sided/contradictory nulls; no Corner 3 mismatch; no percentage inconsistency; and a one-row-per-player aggregate grain with 63 corresponding `TEAM_COUNT > 1` totals players. However, **41 players have nonzero seven-zone FGM/FGA disagreement with their cached overall Base/Totals counts after approved normalization**. Exact totals reconciliation is a mandatory canary gate, so the oldest canary is not accepted. No 2014-15 through 2022-23 request was made.

### Final accounting and classification

| Kind | First attempts | Retries | Verified | Quarantined |
|---|---:|---:|---:|---:|
| Preserved 2023-24 shot-zone canary | 1 | 0 | reviewed cache-only | original retained |
| 2023-24 player-Totals dependency | 1 | 0 | 1 | 0 |
| Remaining shot-zone requests | 1 (2013-14 only) | 0 | 0 | 1 |
| **Cumulative Phase 3A.1 transport attempts** | **3** | **0** | **1 dependency** | **2 shot responses** |

No 2023-24 shot-zone retry, 2024-25/2025-26 access, team-by-team request, raw-event request, supplemental feature source, curation, model work, or policy selection occurred. The 2023-24 result demonstrates that normalized zone counts/shares/attempt indicators and later efficiency candidates may be derivable only under the documented interpretation; it does not establish window-wide support, predictive value, smoothing parameters, or a curated feature definition. The 2013-14 exact-total disagreement blocks that conclusion for Phase 3B.

Primary classification: **`shot-zone source semantics unsupported; Phase 3B zone features blocked`**.

---

## Historical diagnosis under amended repository baseline

The amended baseline is valid. HEAD `354556d1eac3ee3c04cee300167f8ff5b74bdec5` is clean; the four originally untracked Phase 3A.1 artifacts are now tracked. The commit itself contains the specified EDA files and no Phase 3A.1 files. All Phase 1/2 anchors and the Phase 3A deterministic SHA-256 `dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f` reproduced. The preserved 2023-24 quarantine, reviewed byte-identical raw copy, reviewed-promotion event, player-Totals dependency, and 2013-14 quarantine/attempt hashes remained unchanged. No network request was made during this diagnosis.

### 2013-14 exact-discrepancy ledger

The cache-only deterministic ledger has SHA-256 `be0434834c22f0a315c2f8372288154e7d706184635cf8053871488bec80a14f`; a second independent replay produced the same result. It records all 41 mismatched player IDs, names, team identities, team counts, games, minutes, totals, seven-zone counts, signed/absolute differences, coverage, null-normalized cells, Corner 3, and percentage checks in memory.

| Finding | Result |
|---|---:|
| Shot-location / Base-Totals player rows | 482 / 482, one row per canonical ID |
| Exact player matches | 441 (91.49%) |
| Affected players | 41 (8.51%) |
| Aggregate zone-minus-overall FGM / FGA | -13 / -46 |
| Absolute FGM / FGA disagreement | 13 / 46 |
| Maximum player absolute difference | 3 |
| Difference magnitude 1 / 2 / 3–5 / 6–10 / >10 | 37 / 3 / 1 / 0 / 0 |
| Affected multi-team / single-team players | 3 / 38 |

Every mismatch has seven-zone totals below (never above) the overall values. The median and 90th-percentile maximum absolute player difference are 1; the 95th percentile is 2. This numerical size is reported, not accepted as a tolerance.

The audit rejects all proposed deterministic parsing/grain corrections: the required nested-header offsets and seven-zone order are correct; Backcourt is included; the overlapping Corner 3 aggregate is excluded from the overall sum and exactly equals left plus right; paired-null normalization is valid; IDs are unique; player/team identities match the Base/Totals source for every affected player; and 38 of 41 affected players are not multi-team cases. Zone percentages reconcile at source precision. Thus no general, evidence-supported correction restores exact reconciliation without inventing attempts. The remaining disagreement is irreducible cross-endpoint disagreement under the current evidence, so 2013-14 remains quarantined and the nine later-season identities were not requested.

### Future ablation contract (specified only)

After—not during—curation and temporal modeling, compare a primary model with the approved shot-profile family against a no-shot diagnostic baseline. Hold curated observations, target, possession and missing-history policies, temporal folds, estimator, preprocessing, hyperparameters, random seed, and metrics constant. The sole difference is the shot-profile family. Report MAE, RMSE, R², calibration, error by season, unseen-pair error, missing-history subgroup error, and pandemic-season sensitivity. No ablation, curation, or model was run here.

Primary classification: **`2013-14 shot discrepancy unresolved; acquisition remains blocked`**.

---

## Amended residual-policy continuation (complete)

This section supersedes the preceding current-status conclusion under the
explicitly authorized residual policy. Earlier strict-validation failures,
quarantine bodies, original attempt events, and the 2013-14 diagnostic remain
historical evidence; none was edited or overwritten.

### Policy and reviewed 2013-14 promotion

The cache-only 2013-14 diagnosis reproduced with SHA-256
`be0434834c22f0a315c2f8372288154e7d706184635cf8053871488bec80a14f`.
It establishes a structurally valid one-aggregate-row-per-player response with
482 exactly reconciled player IDs, 441 exact count matches, and 41 nonnegative
cross-endpoint residuals. The aggregate difference is 13 FGM and 46 FGA, with
the classified seven-zone values never greater than the matching Base/Totals
value and a maximum player-level residual of 3. Headers, zone order, Backcourt,
Corner 3, paired source-null treatment, IDs, player/team identities, and source
percentages all pass. This is not a numerical tolerance.

Under residual policy `phase3a1.residual-v1`, the response was revalidated
cache-only and promoted through a byte-identical verified raw copy. The new
separate review event is
`phase3a1.reviewed-promotion-2013-14.residual-v1`. It defines only
`UNCLASSIFIED_FGM = overall FGM - seven-zone FGM` and
`UNCLASSIFIED_FGA = overall FGA - seven-zone FGA`; neither field is assigned
to a named shot zone. The original 2013-14 quarantine response and attempt
event remain unchanged, and no second 2013-14 request was made.

Paired source-null FGM/FGA remains a narrowly validated structural-zero
normalization: the derived counts are zero, the source nulls are retained, the
normalization and attempted-zone flags are retained, and efficiency remains
undefined for zero attempts. It is not statistical imputation and is not a
claim of 0% shooting.

### Acquisition accounting and shared schema

After that reviewed promotion, all nine remaining authorized shot-location
identities, in order from 2014-15 through 2022-23, returned HTTP 200 and
verified on their first attempt. No retry was used. The shot-zone ledger now
has exactly 11 attempts: the original 2023-24 and 2013-14 responses plus the
nine newly verified seasons. The separately authorized 2023-24
`LeagueDashPlayerStats` Base/Totals dependency has one verified HTTP-200
attempt. Thus Phase 3A.1 has 12 total transport attempts, below every
authorized ceiling.

Every accepted body has the same `ShotLocations` nested-header schema: six
identity columns (`PLAYER_ID`, `PLAYER_NAME`, `TEAM_ID`, `TEAM_ABBREVIATION`,
`AGE`, `NICKNAME`), `columnsToSkip=6`, `columnSpan=3`, and the zone labels
Restricted Area, In The Paint (Non-RA), Mid-Range, Left Corner 3, Right Corner
3, Above the Break 3, Backcourt, and the overlapping Corner 3 aggregate.
The seven mutually exclusive zones are used for classified totals; Corner 3 is
used only for its left-plus-right identity check. Each response has one
aggregate row per canonical player-season ID. Traded players are represented by
that one aggregate row; no team-stint aggregation or percentage averaging was
performed.

| Season | Players / exact IDs | Exact counts | Residual players | Classified FGM/FGA | Unclassified FGM/FGA | Classified FGA coverage | Max residual |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2013-14 | 482 / 482 | 441 (91.49%) | 41 | 92,766 / 204,126 | 13 / 46 | 99.9775% | 3 |
| 2014-15 | 492 / 492 | 473 (96.14%) | 19 | 92,279 / 205,550 | 8 / 20 | 99.9903% | 2 |
| 2015-16 | 476 / 476 | 380 (79.83%) | 96 | 94,017 / 207,893 | 48 / 156 | 99.9250% | 8 |
| 2016-17 | 486 / 486 | 373 (76.75%) | 113 | 95,990 / 209,929 | 71 / 185 | 99.9120% | 10 |
| 2017-18 | 540 / 540 | 540 (100%) | 0 | 97,435 / 211,707 | 0 / 0 | 100% | 0 |
| 2018-19 | 530 / 530 | 530 (100%) | 0 | 101,062 / 219,458 | 0 / 0 | 100% | 0 |
| 2019-20 | 529 / 529 | 529 (100%) | 0 | 86,550 / 188,116 | 0 / 0 | 100% | 0 |
| 2020-21 | 540 / 540 | 540 (100%) | 0 | 89,020 / 190,983 | 0 / 0 | 100% | 0 |
| 2021-22 | 605 / 605 | 605 (100%) | 0 | 99,930 / 216,722 | 0 / 0 | 100% | 0 |
| 2022-23 | 539 / 539 | 539 (100%) | 0 | 103,260 / 217,220 | 0 / 0 | 100% | 0 |
| 2023-24 | 572 / 572 | 572 (100%) | 0 | 103,739 / 218,700 | 0 / 0 | 100% | 0 |

Across the 5,791 player-seasons, 5,522 have exact counts and 269 have an
explicit residual. Aggregate classified coverage is 2,290,404 of 2,290,811
overall FGA (99.9822%); aggregate unclassified counts are 140 FGM and 407 FGA.
Residuals occur only in 2013-14 through 2016-17, peak in 2016-17, and are not
treated as a known-zone observation. Every season has exact ID reconciliation,
valid Corner 3 identities, valid source-percentage checks, approved paired-null
patterns, and no negative or otherwise impossible residual. The residual-player
counts by multi-team status are respectively 3/38, 7/12, 8/88, and 9/104
(multi-team/single-team) for those four affected seasons; this does not support
a traded-player explanation.

### Cache-only replay and future feature contract

Two independent, process-wide network-blocked replays produced the same
residual-window SHA-256:
`74aef283a8e9404239e1eeb6173beb645fc1ca27e6d845da378756ab66cb8fe8`.
The replay verifies immutable raw-body hashes and its required Phase 1/2
prerequisites. Phase 3A was independently replayed at the checkpoint and
produced SHA-256
`dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f`;
the Phase 3A.1 replay does not itself execute or certify the larger Phase 3A
population analysis.

For later Phase 3B policy evaluation only, the evidence supports candidate
representations of: known-zone FGA divided by overall FGA together with
`UNCLASSIFIED_FGA_SHARE`; known-zone FGA divided by classified-zone FGA as a
sensitivity representation; zone-attempt and source-null-normalization
indicators; and zone-efficiency inputs subject to a later fold-safe smoothing
or reliability policy. No smoothing parameter, final transformation, curation,
or model has been selected. The previously specified primary-shot-model versus
no-shot diagnostic ablation remains future work with all observations, target,
policies, temporal folds, estimator, preprocessing, hyperparameters, seed, and
metrics held constant except for the shot-profile family.

Focused offline Phase 3A.1 tests pass (12 tests), including exact and positive
residual paths, negative-residual and residual-makes-greater-than-attempts
rejection, paired-null treatment, Corner 3 reconciliation, immutable replay,
request authorization, and network blocking. The final suite and repository
checks are recorded with this continuation's handoff.

Current primary classification: **`2013-14 through 2023-24 shot profiles acquired and verified; shot-enabled curation ready`**.

---

## Offline correction pass: explicit residual-policy version gate

Residual acceptance is now version-gated. Every semantic audit supplies an
explicit reconciliation policy: `phase3a1.strict-v1` requires exact totals,
and only `phase3a1.residual-v1` permits the documented nonnegative
`UNCLASSIFIED_FGM`/`UNCLASSIFIED_FGA` residual. Missing, blank, malformed, and
unknown values fail deterministically. Acquisition validates the configured
policy before planning state changes, transport selection, or HTTP-session
construction; reviewed promotion and full-window replay validate it before an
asset is accepted. There is no implicit residual-policy fallback.

The residual-window replay output and each semantic audit now record the active
identifier. This changes the deterministic replay SHA-256 from the prior
`74aef283a8e9404239e1eeb6173beb645fc1ca27e6d845da378756ab66cb8fe8` to
`54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47`.
Removing only those newly explicit policy-ID fields from the new replay object
reproduces the prior digest exactly, demonstrating that the evidence values and
all other replay fields are unchanged.

The Phase 3A wording above is corrected accordingly: Phase 3A independently
replayed during the checkpoint with SHA-256
`dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f`.
The Phase 3A.1 replay verifies its Phase 1/2 prerequisites and shot-zone
evidence, but does not independently execute or certify Phase 3A analysis.

Focused offline coverage includes recognized-policy acceptance, absent and
unknown-policy rejection, rejection before acquisition session construction,
strict exact reconciliation, paired-null preservation, and negative/impossible
residual rejection. No raw response, metadata, quarantine body, attempt event,
manifest, ledger, reviewed-promotion event, or substantive result changed.

The initial complete-suite result recorded here was superseded by the following
offline path-length diagnosis and clean verification pass.

---

## Offline diagnosis: Phase 2C failure-evidence race test

The initial failure in
`test_postcheck_failure_evidence_race_preserves_returned_body_and_stops` was
environmental, not a Phase 2C or Phase 3A.1 source defect. Its preserved
attempt ledger records the precise exception:

```text
FileNotFoundError: [Errno 2] No such file or directory:
...\\failure_evidence\\.collision-1e919449389fc60050079d63-a1-
137b6ad9759d3e4023d33f5519158d65941176de50a5a852e52194a615d31b69.body.
<pid>.tmp
```

The longest affected temporary path measured 263 characters. It occurs only
after the test deliberately makes the normal immutable evidence destination
collide, when the implementation correctly tries the content-addressed
collision path. Windows rejects the temporary create-once filename before that
path can be written, which is surfaced as the generic
`failure_evidence_collision` stop instead of the intended
`failure_evidence_postcheck_collision` stop. The failure reproduces with a
long nested pytest base path, regardless of whether the Phase 3A.1 test module
runs before or after it. The implicated test passed alone and in five clean
processes, and neither module leaked monkeypatch, environment, cache, working
directory, or network state.

The definitive offline command uses the short repository-local, Git-ignored
`.t` base path (outside `cache/`) and process-wide socket blocking. The
repository-local `.gitignore` now excludes `.t/`; it is test-only and prevents
the test base from contaminating copied cache fixtures. No Phase 2C production
or test code changed.

Final isolated verification results:

| Run | Result |
|---|---|
| Implicated Phase 2C test, five fresh runs | 5/5 passed, exit 0 each |
| Complete Phase 2C module | 34 passed, exit 0 |
| Phase 3A.1 then implicated test | 14 passed, exit 0 |
| Implicated test then Phase 3A.1 | 14 passed, exit 0 |
| Focused Phase 3A.1 module | 13 passed, exit 0 |
| Complete offline research suite | 324 passed, exit 0 |

Two independent process-wide network-blocked residual-window replays again
match SHA-256
`54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47`
under `phase3a1.residual-v1`. The supported shot-zone evidence remains 11
seasons, 5,791 player-seasons, 407 unclassified FGA, and 140 unclassified FGM;
no cache evidence, raw response, operational ledger, or reviewed-promotion
record changed.
