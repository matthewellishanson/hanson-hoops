# Phase 3F-R1S — Simplified Final-Test Acquisition Policy

## Purpose and authority boundary

This checkpoint creates a deterministic plan for a later, separately authorized acquisition. It makes no request, opens no protected 2025–26 evidence, constructs no holdout, and performs no model operation. Git review, audit, and the future committed checkpoint are the practical authority boundary.

SHA-256 hashes are mutation and identity checks. They are not proof of who created or authorized the bytes. The plan does not try to defeat a person who can rewrite the repository and execute arbitrary code.

## Threat model

The checkpoint protects against:

- accidental request drift;
- an agent using an unapproved endpoint, season, team, measure, or parameter;
- accidental duplicate requests;
- accidental retries;
- partial or contradictory acquisition state;
- corrupted or changed response bytes;
- silent omission of required requests;
- mixing protected acquisition with model execution;
- accidental access to protected evidence before authorization.

The checkpoint does not attempt to protect against:

- a malicious repository owner;
- a caller who can arbitrarily rewrite source code and all evidence files;
- a compromised operating system;
- forged evidence created by an actor with unrestricted local write and execution access.

The controls serve four distinct purposes. Scientific-validity controls freeze the population, direct target, eligibility, and reconciliation rules. Operational-safety controls limit attempts and stop on ambiguous or failed state. Reproducibility controls pin identities, ordering, source hashes, and serialization. Adversarial security is out of scope.

## Frozen request plan

The future protected package contains exactly 60 `teamdashlineups` requests for the 2025–26 Regular Season: the 30 official numeric team IDs in ascending numeric order, with one full-season `Base` request followed immediately by one full-season `Advanced` request for each team. `GroupQuantity=2`, `PerMode=Totals`, and all date bounds are blank. The complete parameter dictionary and established research headers are recorded in `acquisition_plan.json`.

Two non-protected dependencies remain missing and are recorded separately: 2024–25 Regular Season `leaguedashplayerstats` `Base/Per100Possessions` and `Base/Totals`. R1S does not acquire them. Future protected responses and non-protected dependencies have distinct namespaces.

## Later transport and records

A later acquisition must be sequential, wait at least one second between attempts, use a 30-second timeout, disable redirects, set `trust_env=False`, perform zero automatic retries, and allow one authorized attempt per request identity. It must use the established research headers, verify before promotion, and quarantine and stop on failure.

The minimal future record set is an authorization record, attempt-start record, attempt-outcome record, verified raw response body, and a quarantine record when applicable. Together these record only the approved identity, attempt times, completion, HTTP status, byte length, raw SHA-256, canonical JSON SHA-256 when JSON is valid, and verified/failed/quarantined state. Records are append-only or write-once during acquisition; their hashes do not authenticate an author.

Restart states are:

- `not_started`: eligible for its one authorized attempt;
- `completed_verified`: re-hash, verify, and skip;
- `started_without_outcome`: stop for read-only investigation;
- `failed_or_quarantined`: preserve evidence and stop;
- `conflicting_state`: refuse progress and stop.

## Population and exact-250 rules

Player pairs use numeric canonical unordered keys. Base and Advanced keys must match. Zero-possession rows remain visible. Eligibility is direct full-season `POSS >= 150`, and targets are direct full-season Advanced `NET_RATING`. Approximate window-rating aggregation and selective removal of only omitted pairs are prohibited. If non-exhaustiveness is proved and no definition-supported direct recovery exists, exclude the whole team.

Exactly 250 returned rows is an unresolved warning requiring investigation, not proof of incompleteness. R1S contains no executable recovery request. A later authorization must name the affected team, triggering full-season response hash, exact complementary date windows, four Base/Advanced request identities, and approving checkpoint.

## Stage separation

R1S planning does not authorize acquisition. Acquisition completion does not authorize final-test construction. Reconciliation does not authorize fitting or prediction. Readiness assessment does not itself authorize execution. Any failed or unresolved readiness gate blocks execution. Final execution remains a later, separate phase. No result from an unresolved or excluded team-season may silently enter the final test. No model execution may occur merely because evidence acquisition completed. The 2025–26 season may be opened only by the later bounded acquisition checkpoint.

The six frozen Phase 3F final-test readiness gates remain predictor evidence completeness, target evidence completeness, team-population exhaustiveness, row eligibility, row alignment, and protected final-result reveal. Their identities and number do not change.

Final model execution requires all three of the following:

1. every frozen Phase 3F final-test readiness gate passes;
2. the completed readiness checkpoint receives read-only audit clearance;
3. the user separately authorizes the one-time final model execution.
