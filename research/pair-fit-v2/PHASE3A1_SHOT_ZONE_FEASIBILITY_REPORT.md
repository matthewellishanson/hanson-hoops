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
