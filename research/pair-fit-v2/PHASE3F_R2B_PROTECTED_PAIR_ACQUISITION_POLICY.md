# Phase 3F-R2B Protected Pair Acquisition Policy

## Classification boundary

Phase 3F-R2B is a one-time acquisition and structural reconciliation checkpoint. It may open only the 60 protected 2025-26 Regular Season `TeamDashLineups` pair-lineup identities frozen in the audit-cleared Phase 3F-R1S plan. It does not construct a final-test table, join predictor profiles, apply preprocessing, load or fit an estimator, create predictions or metrics, classify the model scientifically, or serialize a model.

## Authorization

The machine authorization is written once to `planning/phase3f-r2b/authorization.json`. It pins committed HEAD `8d8f7f5fc6de31b81506091dff00b3e617e13232`, the audited R0/R0.1/R1S/R2A inputs, the exact 60 R1S endpoint/parameter identities, numeric team order, Base-before-Advanced order, the two R2B output namespaces, one attempt per identity, transport settings, failure and quarantine rules, restart states, exact-250 handling, and the phase stop boundary.

No identity is reconstructed as an acquisition authority. The implementation reads the 60 identities from the byte- and SHA-256-pinned R1S plan and rejects every request whose canonical endpoint/parameter document differs. Date windows, other seasons, other endpoints, control requests, Four Factors, Usage, player profiles, standings, and recovery requests are unauthorized.

## Transport and immutable evidence

Requests run sequentially with the established NBA research headers, `trust_env=False`, redirects disabled, a 30-second timeout, zero automatic retries, exactly one attempt per identity, and at least one second between completed transport attempts. An attempt-start record is written before transport. Exact response bytes are preserved. HTTP 200, no redirect, strict JSON, exactly one `Lineups` result set, unique string headers, and consistent row widths are required before promotion. Raw-byte and canonical-JSON SHA-256 values are recorded.

Any transport or response-envelope failure writes an outcome and quarantine record and stops the phase immediately. No retry is permitted under this authorization. A response with exactly 250 rows is not a transport failure: it is verified and preserved normally, marked unresolved, and acquisition continues through the remaining full-season allowlist.

## Restart states

- `not_started`: eligible for its only authorized attempt.
- `completed_verified`: re-hash, structurally verify, and skip without transport.
- `started_without_outcome`: stop for read-only investigation.
- `failed_or_quarantined`: preserve evidence and stop.
- `conflicting_state`: refuse progress and stop.

Files are created with exclusive write-once semantics. A completed identity is never reacquired. Altered records, differing bodies, unexpected files, mixed authorization identities, partial completed state, and unauthorized insertion are conflicting state.

## Structural verification and reconciliation

Every response records the exact headers, row count and width status, request and result-set identity, hashes, numeric canonical pair identities, malformed/same-player/duplicate pair counts, team-identity mismatches, required field validity, zero-possession visibility, and exact-250 status. Names never establish pair identity.

Each team is reconciled independently. Base and Advanced canonical pair sets and row counts must agree. Base `POSS` is recorded as the future eligibility source and Advanced `NET_RATING` as the future target source. Zero-possession rows stay visible. No possession threshold is applied, no target is imputed or reconstructed, no target distribution is summarized, and target magnitude cannot affect disposition.

The possible primary structural dispositions are `structurally_complete_non_250`, `exact_250_unresolved`, `base_advanced_mismatch`, `invalid_pair_identity`, `invalid_required_field`, and `acquisition_incomplete`. Transport failures use `failed_or_quarantined`. A team with a Base/Advanced row or key mismatch remains structurally unresolved even when one response has exactly 250 rows.

## Exact-250 boundary

Exactly 250 rows proves neither completeness nor incompleteness and does not automatically exclude a team. R2B creates no recovery request. Its evidence record identifies the affected team and triggering full-season hashes. Any later recovery checkpoint would have to freeze exact complementary 2025-26 date windows and four Base/Advanced identities per affected team and receive separate approval.

## Stop rule

R2B ends after deterministic evidence verification, 30 team reconciliations, global structural counts, artifact hashing, and a human report. All final-execution readiness gates remain pending. Acquisition success does not authorize final-test construction or model execution.
