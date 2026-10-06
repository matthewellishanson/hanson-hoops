# Phase 3F-R2B.2 Correction-Only Protected Acquisition Continuation Policy

## Classification boundary

Phase 3F-R2B.2 is a separate continuation in new immutable namespaces. It may revalidate the preserved Atlanta Base bytes offline, make exactly the original protected requests at ordinals 2–60 once each, and reconcile Base/Advanced pair structure. It may not construct a final-test dataset, join profiles, preprocess features, load or fit an estimator, predict, calculate metrics, serialize a model, or classify scientific performance.

The original Phase 3F-R2B remains permanently **`FAILED — authorized protected acquisition attempt failed`**. This continuation does not rewrite that classification, alter its policy, report, source, tests, authorization, invocation, response, outcome, or quarantine, or create promoted evidence in its namespace.

The corrected response contract is frozen as `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`.

## Exact authorization

The machine authorization is write-once and pins:

- committed HEAD `1d98c20f41fe550deafa7e68cba611d7d66bf519` on branch `research/pair-fit-v2`;
- all inherited R0/R0.1/R1S/R2A fingerprints;
- all failed-R2B committed and runtime evidence;
- all five R2B.1 artifacts and the corrected contract identity;
- Atlanta Base’s original request, canonical identity, attempt, raw path, byte count, raw and canonical hashes, and quarantine path;
- original ordinals 2–60, their request IDs, endpoint, complete parameter dictionaries, canonical identities, and deterministic order;
- transport settings, output namespaces, restart states, fail-stop behavior, and the phase boundary.

Atlanta Base remains original ordinal 1 with disposition `offline_revalidation_only` and `network_authorized=false`. Every transport entry point rejects ordinal 1 and request ID `teamdashlineups:1610612737:base`. No renumbering is allowed. No identity outside original ordinals 2–60 is authorized.

## Immutable namespaces and restart states

New ignored namespaces are:

- `planning/phase3f-r2b.2/`
- `cache/phase3f-r2b.2/protected-final-target/`

The continuation never writes into `planning/phase3f-r2b/`, `planning/phase3f-r2b.1/`, or `cache/phase3f-r2b/`.

Each transport identity is classified as `not_started`, `completed_verified`, `started_without_outcome`, `failed_or_quarantined`, or `conflicting_state`. Atlanta alone is classified as `offline_revalidated_reference`. A completed identity is fully re-hashed and revalidated, then skipped. Started, failed, altered, partial, mixed-authorization, or conflicting state stops progress. Records are write-once; no overwrite, reset, retry, or silent restart is permitted.

## Corrected response contract

Every response must be strict JSON with exactly two unique result sets in the frozen order `Overall`, then `Lineups`. Both are selected by exact name, never by array position. Each set must be a well-formed object with unique string headers, the exact frozen ordered measure-specific schema, and rows exactly matching header width. Missing, extra, duplicate, reordered, or malformed sets or columns are rejected.

`Overall` must have exactly one row. The authorized `TeamID`, returned response-parameter `TeamID` when present, and singleton `Overall.TEAM_ID` must agree. Returned season, season type, and measure must also agree when present, and the response resource must agree with `teamdashlineups`. Lineup rows do not contain or require `TEAM_ID`; team identity is never inferred from names or fabricated in raw rows.

Every `Lineups.GROUP_ID` must encode two distinct positive decimal player IDs. Canonical unordered identity sorts the numeric IDs. Malformed IDs, same-player pairs, and duplicate canonical pairs are rejected.

For Base, the exact schema owns canonical pair identity, `MIN`, `SUM_TIME_PLAYED`, and its other frozen fields. `MIN` and `SUM_TIME_PLAYED` must be numeric, finite, and nonnegative. Base does not own pair `POSS` or target `NET_RATING`, and absence of Base `POSS` is required by the frozen schema.

For Advanced, the exact schema owns canonical pair identity, direct full-season `POSS`, direct full-season `NET_RATING`, and its other frozen fields. `POSS` must be numeric, finite, and nonnegative. `NET_RATING` must be numeric and finite. Zero-possession rows remain visible. R2B.2 does not materialize a `POSS >= 150` population or summarize targets.

## Atlanta offline reference

Before any transport start record, R2B.2 reopens the original Atlanta Base body in place, checks all original identities and hashes, applies the corrected contract, and writes a new record containing only provenance and structural diagnostics. It does not copy or promote the body. Expected findings are 57 `Overall` headers and one row; 56 `Lineups` headers and 200 rows; 200 canonical pairs; zero width, duplicate, malformed, same-player, invalid-ID, or required-field errors; not exact-250; and Base `POSS` absent as expected.

Any identity or contract failure blocks the continuation before transport. Atlanta is never requested again.

## Transport and failure handling

Only after Atlanta offline revalidation succeeds may original ordinals 2–60 run sequentially. Each uses the exact endpoint and parameter dictionary, established research headers, `trust_env=False`, redirects disabled, a 30-second timeout, zero automatic retries, a single allowed attempt, and at least one second between completed attempts. A write-once start record precedes transport. Raw bytes are preserved. HTTP 200, no redirect, strict JSON, and the corrected response contract are required. Verification and promotion occur only after all checks; a write-once outcome completes the identity.

Any transport or verification failure preserves the start record and any received bytes, writes outcome and quarantine records, and stops immediately before the next ordinal. Neither automatic nor manual retry is allowed under this authorization.

Exactly 250 lineup rows is not a transport failure. The response remains verified, the team is marked unresolved, and the remaining authorized full-season requests continue. No recovery window, date split, control request, alternate endpoint, alternate season, standings, Four Factors, Usage, or player-profile request is authorized.

## Structural reconciliation

Atlanta Base comes only from the offline original reference; Atlanta Advanced comes from ordinal 2; all other Base and Advanced evidence comes from original ordinals 3–60. For each team, reconciliation reports source namespaces, row and canonical-key counts, intersection, Base-only and Advanced-only keys, pair defects, invalid fields, Advanced zero-possession rows, exact-250 diagnostics, and an explicit disposition.

Exact Base/Advanced canonical-key equality is required for structural completeness. A mismatch takes precedence as the disposition even when one side has 250 rows, while the exact-250 diagnostic remains recorded. Exact-250 proves neither completeness nor incompleteness and never causes selective pair deletion or automatic team exclusion. Any recovery requires a later, separate policy and authorization.

Allowed dispositions are `structurally_complete_non_250`, `exact_250_unresolved`, `base_advanced_mismatch`, `invalid_pair_identity`, `invalid_required_field`, `acquisition_incomplete`, and `failed_or_quarantined`.

## Completion classifications

- `PASS — correction-only protected acquisition completed and structurally reconciled`: Atlanta revalidates, all 59 requests verify, and no team is unresolved.
- `CONDITIONAL PASS — acquisition complete; unresolved team evidence requires a separate checkpoint`: acquisition completes, but exact-250 or another structural issue remains.
- `BLOCKED — offline revalidation or structural reconciliation incomplete`: execution cannot validly begin or reconciliation needs new authority.
- `FAILED — authorized continuation attempt failed`: a transport or verification attempt fails.

These classifications describe acquisition and structural evidence only. All six final-test readiness gates remain pending regardless of the R2B.2 result.
