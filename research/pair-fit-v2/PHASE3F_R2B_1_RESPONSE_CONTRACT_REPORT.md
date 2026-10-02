# Phase 3F-R2B.1 Protected Response-Contract Correction Report

## PASS — Phase 3F-R2B.1 corrected response contract frozen; ready for read-only audit

This PASS classifies only the correction specification. It does not repair or reclassify R2B, authorize an Atlanta retry, authorize any of the remaining 59 requests, promote protected evidence, or authorize final-test or model work.

## 1. Repository and preflight

- Branch: `research/pair-fit-v2`
- HEAD: `dd740e39cce03a3ab0f52f5be1067c47bb510db5`
- Upstream: `origin/research/pair-fit-v2`
- Ahead/behind: `0/0`
- Preflight index and working tree: clean
- Committed R2B checkpoint: present as six committed changes at HEAD
- All 43 R0/R0.1/R1S/R2A inputs pinned by the R2B authorization: byte and SHA-256 matches

No commit or push was performed.

## 2. Permanent R2B failure and preserved runtime

The original R2B status remains permanently **`FAILED — authorized protected acquisition attempt failed`**. Its original quarantine remains historically correct under the then-frozen verifier. R2B.1 did not modify the implementation, CLI, policy, report, tests, planning namespace, or failed evidence namespace.

The failed state remains exactly:

- one official invocation;
- one attempt-start record;
- one response;
- one outcome;
- one quarantine record;
- zero promoted responses and zero verification records;
- Atlanta Base `failed_or_quarantined`;
- original ordinals 2–60 `not_started` because the protected root contains only the Atlanta Base identity directory;
- zero automatic or manual retries;
- zero recovery requests.

| Preserved item | Bytes | SHA-256 |
|---|---:|---|
| R2B authorization | 71,656 | `12249e6acca554507501e887c9afeb4f3cad0079fb40ab2738bea3d308ade856` |
| Official invocation | 935 | `936708826bbfaf729a1ad8c9ed7dcbbf2e8bce13b11e3e9a08403fe665b524fe` |
| Atlanta attempt start | 281 | `90553e18945c075aa285207d01821266930d3e9fcb79b84b9386b82bf741f9c9` |
| Atlanta raw response | 51,905 | `e2134b18de903b79b1bcce8d628cf041ae18a50ccab00018d3b29b7daa63aff0` |
| Atlanta outcome | 594 | `c799c52fbb449c126edb669d5abcf003ae3703895f2734a7bd0d2a1c6db6d9cf` |
| Atlanta quarantine | 346 | `affc98a8a1cba3158764085cc5811977c31f4a088f9dda5a412b65004f97986f` |

Atlanta’s canonical JSON SHA-256 remains `bac19c1df5f1a25de0e558c62410457917bb25ffb9130833e346444ae8c30f8d`. Its request ID is `teamdashlineups:1610612737:base`; its canonical request identity is `9809de72e3a017b700ce2059a77b9ba31128cb467f2e9fde516119f6230bf64b`; and its attempt number remains 1.

## 3. Historical envelope and schema findings

The actual 60 verified 2024–25 full-season response bodies were compared, not merely their manifest descriptions. All 60 use exactly two sets in the order `Overall`, `Lineups`; all have unique names and consistent row widths; all have one `Overall` row. The 30 Base bodies share exact 57-column `Overall` and 56-column `Lineups` schemas. The 30 Advanced bodies share exact 49-column `Overall` and 48-column `Lineups` schemas.

The preserved Atlanta Base body’s 57-column `Overall` and 56-column `Lineups` schemas exactly match the historical Base contract. The evidence therefore supports exact ordered schema equality and established-order validation rather than a more permissive required-column or arbitrary-order contract. The human policy records the full ordered lists; the generated contract records those lists plus their hashes.

Base requires pair `GROUP_ID` and exposure/time fields `MIN` and `SUM_TIME_PLAYED`; it owns neither pair `POSS` nor the `NET_RATING` target. Advanced requires pair `GROUP_ID`, direct `POSS`, and direct `NET_RATING`. Advanced `POSS` is the future eligibility authority, and Advanced `NET_RATING` is the future target authority.

## 4. Four corrections frozen

1. The envelope contains exactly the unique `Overall` and `Lineups` sets, validates both exact schemas, rejects malformed sets/names/headers/widths, and requires one valid `Overall` row.
2. All semantic selection is by exact set name. Pair rows come only from named `Lineups`; positional `[0]` selection is prohibited. The independently supported order rule is `Overall`, then `Lineups`.
3. Base owns `MIN`/`SUM_TIME_PLAYED`, not `POSS` or target `NET_RATING`. Advanced owns validated direct `POSS` and `NET_RATING`.
4. Team ID is reconciled among the request, returned parameters when present, and singleton `Overall` row. Lineup-row `TEAM_ID` is neither required nor fabricated.

## 5. Atlanta offline compatibility

Offline parsing independently reproduced:

- strict JSON valid;
- `Overall`: 57 headers, 1 row;
- `Lineups`: 56 headers, 200 rows;
- row-width errors: 0;
- unique result-set names, ordered `Overall`, `Lineups`;
- canonical unordered pairs: 200;
- duplicate pairs: 0;
- malformed group identifiers: 0;
- same-player pairs: 0;
- invalid player IDs: 0;
- exact-250: false;
- Base `POSS` absent as expected;
- request, returned-parameter, and `Overall` team IDs all equal `1610612737`.

Result: the preserved response is compatible with the corrected specification and has no independent structural Atlanta defect. This result is only a deterministic compatibility assessment. Atlanta remains quarantined; its body was not copied, promoted, or written back into the failed namespace, and R2B remains failed.

## 6. Correction-only continuation inventory

The non-executable plan freezes Atlanta ordinal 1 for offline-only revalidation and forbids another Atlanta network attempt. It carries the required link to the original request identity, attempt, raw path and hashes, quarantine, and correction-contract identity. The 59 remaining identities retain exact original request IDs, ordinals 2–60, canonical identities, and parameters. They are not currently authorized; they may become transport-eligible only in a later separately authorized phase. Such a phase must use a new namespace, allow one attempt per remaining identity, allow zero retries, and stop on any failure.

## 7. Generated specification artifacts

Contract identity: `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `response_contract.json` | 11,940 | `ecc3ecf1d547401539af8f8f640002fc3887de3dd64f1e80af1d41d62d04c49e` |
| `continuation_plan.json` | 64,103 | `8b30afae8e1035144153ea96d2510cc78e3b4572b03b28558edd73a0c1a56f18` |
| `input_fingerprints.json` | 29,250 | `dfc1115d139e153ee7011b1eb934355a4403b72b26579bc0e41782bc25c78267` |
| `summary.json` | 1,055 | `d238fa41de8a15bc75e4d831c5498bdb2664f809af8b22335174c1dbe1a291da` |
| `artifact_hashes.json` | 698 | `3350bce351b7d64ea0d46a55d17d83024ea65c4ba008aa652a672ff25cd0d79f` |

Two disposable builds produced byte-identical copies of all five artifacts. Both disposable directories were removed. An import-only canary passed before the official build. The official `planning/phase3f-r2b.1/` build was invoked exactly once and only read-only checks followed.

## 8. Tests and checks

- `py_compile`: passed for implementation, CLI, and focused tests.
- Focused R2B.1 tests: 17 passed.
- Complete offline research suite: 689 passed; two pre-existing environment/checkpoint assertions failed independently of R2B.1:
  - the Phase 3E-R3 policy test requires the already-existing ignored `modeling/phase3e-r4/` directory to be absent;
  - the R0.1 Git-state test requires the obsolete R0.1 historical HEAD.
- Those two modules with only the state assertions deselected: 73 passed/1 deselected and 23 passed/1 deselected.
- Historical R2B.1 schema replay: all 60 actual 2024–25 bodies passed.
- Determinism: five of five artifacts byte-identical across two builds.
- Populated, empty-existing, and partial output namespaces: refused.
- Static capability scan: no network client, URL, estimator, prediction, metric, or serialization implementation; no positional `payload["resultSets"][0]` selection.
- `git diff --check`, ignore checks, credential scan, prohibited-artifact scan, and final `py_compile`: passed.

## 9. Explicit phase-boundary confirmations

- Network requests made: 0.
- Additional protected 2025–26 responses opened: 0.
- Atlanta Advanced opened, listed, statted, or hashed: no.
- Any other real 2025–26 response opened, listed, statted, or hashed: no.
- Recovery-window or later protected namespace opened: no.
- Atlanta copied or promoted: no.
- Failed namespace modified: no.
- Final-test dataset opened or constructed: no.
- Final-test rows constructed: 0.
- Prior profiles joined: no.
- Preprocessing applied: no.
- Estimator instantiated, loaded, fit, or run: no.
- Predictions or metrics generated: no.
- Model serialized: no.
- Commit or push: no.

## 10. Interpretation and next step

What the evidence proves: R2B attempted only Atlanta Base; the exact preserved response is intact; its `Overall` plus `Lineups` envelope and Base schemas match the verified historical contract; it has no independent pair-population structural defect; the remaining identities were not attempted; and the original records remain immutable.

What the specification freezes: all four contract corrections, exact schemas and result-set order, envelope-level team identity, Atlanta’s permanent no-reacquisition status, non-executable ordinals 2–60 continuation inventory, and future named-set reconciliation rules.

What remains a user decision: whether to authorize a separate read-only audit and, only after a successful audit, whether to authorize an implementation-repair checkpoint or a later continuation for ordinals 2–60.

What requires read-only audit: the five generated artifacts, their contract identity and hashes, the evidence-to-rule trace, the offline Atlanta compatibility result, and the preservation/no-transport boundary.

What remains unauthorized: implementation repair, any network request, Atlanta reacquisition, Atlanta promotion, recovery windows, final-test construction, profile joining, preprocessing, and every model operation.

The narrowest justified next step is a read-only audit of this R2B.1 checkpoint. Stop there.

## 11. Final state

HEAD remains `dd740e39cce03a3ab0f52f5be1067c47bb510db5`; upstream remains synchronized; the index remains clean. The working tree contains only the intended R2B.1 policy, report, implementation, CLI, focused tests, and narrow `.gitignore` change. The ignored official namespace contains exactly the five generated specification artifacts above. No temporary build remains.

