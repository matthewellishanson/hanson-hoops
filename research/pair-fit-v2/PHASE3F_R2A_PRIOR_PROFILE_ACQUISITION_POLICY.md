# Phase 3F-R2A — 2024–25 Prior-Profile Dependency Acquisition Policy

## Purpose and stop boundary

Phase 3F-R2A may acquire and verify exactly two non-protected predictor-history dependencies: 2024–25 Regular Season `LeagueDashPlayerStats` `Base/Per100Possessions`, followed by `Base/Totals`. The exact parameter dictionaries come from the audited Phase 3F-R1S `planning/phase3f-r1s/acquisition_plan.json`. This phase stops after acquisition, independent verification, cross-source reconciliation, and reporting.

R2A does not authorize any protected-season request or file access, `TeamDashLineups`, pair or lineup evidence, standings, recovery windows, controls, shot locations, substitute profile sources, final-test construction, preprocessing, fitting, prediction, metric calculation, or model serialization.

## Frozen authorization

Before transport, R2A writes `planning/phase3f-r2a/authorization.json` with exclusive-create semantics. It records the R1S plan path, audited byte count and SHA-256, all required R0/R0.1/R1S input fingerprints, the exact two canonical request identities and order, output namespace, one-attempt limit, transport contract, prohibited protected season, failure rules, restart rules, and phase stop boundary. Existing different bytes are a conflict and are never overwritten.

The request implementation accepts only identities canonically identical to one of those two records. The authorized order is:

1. 2024–25 Regular Season `LeagueDashPlayerStats` `Base/Per100Possessions`, league-wide.
2. 2024–25 Regular Season `LeagueDashPlayerStats` `Base/Totals`, league-wide.

Any identity containing the protected season, naming a team or lineup endpoint, selecting a nonblank team, or differing in any frozen parameter is rejected before transport.

## Evidence and transport

Evidence is isolated under `cache/phase3f-r2a/non-protected-prior-profiles/`. Each request has one fixed directory and one possible attempt. An immutable attempt-start record is created before transport. Transport is sequential, uses the established NBA research headers, a `requests.Session` with `trust_env=False`, explicit zero-retry adapters, redirects disabled, a 30-second timeout, and at least one second between real attempts.

The exact response bytes are written once as attempt evidence. HTTP 200, no redirect, strict UTF-8 JSON, exactly one valid `LeagueDashPlayerStats` result set, row widths, unique headers, required source fields, canonical positive player IDs, unique player IDs, and finite nonnegative reliability fields are required before the same bytes are promoted to verified evidence. Raw-byte and canonical-JSON SHA-256 values are recorded. Source precision is retained; acquisition does not rename, coerce, fill, or impute source fields.

There are no automatic or manual retries within this authorization. On timeout, connection error, redirect, non-200 status, invalid JSON, schema failure, identity failure, or other invalid response, R2A preserves available evidence, writes an immutable outcome and quarantine/failure record, stops the phase, and does not attempt the next request.

## Restart rules

The only recognized states are:

- `not_started`: eligible for the one authorized attempt;
- `completed_verified`: re-hash and re-validate all immutable evidence, then skip transport;
- `started_without_outcome`: stop for read-only investigation;
- `failed_or_quarantined`: preserve and stop;
- `conflicting_state`: refuse progress and stop.

A completed request is never requested again. No record or response is overwritten. A second attempt, a different body for the identity, mixed records, and partial state presented as verified are refused.

## Reconciliation

Only after both bodies independently reach `completed_verified`, R2A compares player-ID sets and reports both unique counts, intersection, side-only IDs, duplicate counts, and malformed/nonpositive counts. It verifies that Totals `MIN` supplies finite nonnegative `TOTAL_MIN` reliability metadata and that the frozen 45 no-shot estimator-feature names are source-available or derivable from the Per100 contract and already frozen formulas.

R2A does not learn medians, impute profiles, construct player pairs, build model rows, calculate model inputs, fit preprocessing, load or fit an estimator, predict, calculate a metric, or serialize a model. Material schema or identity discrepancies block the checkpoint for audit; they are not repaired here.

## Protected-season separation

The protected season is a fail-closed string and path prohibition. Candidate paths are checked lexically before any filesystem operation. R2A never enumerates, opens, hashes, stats, or otherwise inspects a protected-season path or protected `TeamDashLineups` namespace. It creates no status record for any future protected request.

SHA-256 provides byte identity and mutation detection, not author authentication. The threat model covers accidental drift, duplication, retries, incomplete or contradictory state, mutated bytes, stage mixing, and accidental protected access; it does not cover a malicious actor with unrestricted repository and execution control.
