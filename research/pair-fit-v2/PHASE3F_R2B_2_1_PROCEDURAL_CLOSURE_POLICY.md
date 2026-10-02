# Phase 3F-R2B.2.1 Protected-Acquisition Procedural Closure Policy

## Classification and boundary

**PASS — Phase 3F-R2B.2.1 procedural closure complete; ready for read-only audit**

This is a non-transport documentation-and-contract checkpoint. It verifies immutable records, describes four narrow R2B.2 procedural limitations, and freezes bounded controls for later protected acquisitions. It makes no network request, changes no historical authorization or evidence, creates no recovery identity, copies no response body or row-level data, constructs no final-test row, and performs no model operation.

Original R2B remains permanently **`FAILED — authorized protected acquisition attempt failed`**. R2B.1 remains the authoritative corrected response contract at `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`. R2B.2 acquired scientifically and structurally valid protected evidence but retains **`CONDITIONAL PASS — acquisition evidence valid; narrow procedural correction required`**. Its records are not rewritten, and none of its responses should be reacquired because of these procedural limitations.

## Existing evidence

All 60 response bodies remain intact and compatible with the R2B.1 contract. There are 30 Base and 30 Advanced responses, 5,403 rows per measure, and equal Base/Advanced canonical-pair sets for all teams. No recovery or modeling occurred. This evidence remains eligible for later scientific use only after approved dispositions for unresolved teams. Final-test readiness remains unestablished and model execution remains unauthorized.

Indiana (`1610612754`) remains exact-250 unresolved: Base ordinal 35 and Advanced ordinal 36 each contain 250 equal canonical keys. Memphis (`1610612763`) remains exact-250 unresolved: Base ordinal 53 and Advanced ordinal 54 each contain 250 equal canonical keys. Exact-250 establishes neither completeness nor incompleteness. Neither team is excluded, and no recovery dates, request identities, or authorization are selected here.

## Procedural issue 1: contradictory authorization flags

R2B.2’s top-level `network_authorized_requests` identifies 59 authorized identities at original ordinals 2–60. Each copied nested request nevertheless retains stale R2B.1 values `currently_network_authorized: false` and `may_become_eligible_only_in_later_separately_authorized_phase: true`. Those nested values contradict the R2B.2 top-level authorization. The actual identities, endpoints, parameters, and order did not drift. This is a machine-contract ambiguity, not evidence of an unauthorized endpoint or extra request. The historical authorization remains immutable.

Every future protected request entry must contain one phase-local authorization object with `authorization_phase`, `network_authorized`, `attempt_limit`, `ordinal`, `request_id`, and `canonical_request_identity`. Inherited authorization-status fields are prohibited unless isolated as clearly namespaced historical metadata. Validation must reject any disagreement among the top-level inventory, per-request authorization, attempt limit, ordinal, request ID, and canonical identity.

## Procedural issue 2: namespace binding

The historical R2B.2 CLI accepted caller-supplied planning and evidence directories and did not prove their equality to the authorization’s frozen namespace strings. This limitation does not establish that an alternate execution occurred.

Every future protected authorization must contain exact resolved canonical paths for the planning namespace, raw/attempt evidence namespace, and source-evidence references. The CLI must resolve supplied absolute paths and require exact equality. Detectable relative aliases, path-normalization ambiguity, alternate roots, and symlink or junction substitutions are rejected. A caller may not select a different namespace after authorization. Populated, partial, conflicting, failed, or quarantined official state applies the frozen restart rules. A second invocation in an alternate namespace is rejected before transport. Historical R2B.2 code is not modified.

## Procedural issue 3: executing source identity

R2B.2’s authorization and invocation did not pin the exact executing source bytes. Its invocation has no verified source inventory, and the current implementation file’s filesystem last-write time is after the recorded invocation. No historical executing hash is inferred or fabricated.

Before future protected transport authorization is finalized, byte count and SHA-256 must be recorded for the acquisition implementation, CLI, applicable policy or machine contract, and project-local modules directly controlling identity, transport, verification, promotion, restart, or pacing. Invocation must recompute and match the inventory, then persist that verified inventory with the exact command, Python executable, working directory, and `PYTHONPATH`. Post-execution reporting must state whether those bytes remained identical and must not claim more than the records prove. This is bounded to transport-controlling project source.

## Procedural issue 4: pacing provenance

Historical UTC completion-to-next-start intervals have minimum 0.986753 seconds, maximum 1.011286 seconds, average 1.002996 seconds, and three of 58 values below one second. Minimum start-to-next-start is 1.248367 seconds; minimum completion-to-next-completion is 1.247101 seconds. The current source uses monotonic-clock enforcement, but absolute monotonic values and sleep records were not persisted. No genuine spacing violation is established. Exact one-second completion-to-start compliance is strongly supported but not proved. Scientific materiality is nil. Historical records are not rewritten.

Future attempts must persist UTC start/completion for audit context, process-monotonic start/completion, prior monotonic completion, required gap, calculated pre-attempt gap, requested sleep, observed post-sleep gap, and disposition. Enforcement uses a process-monotonic clock, sleeps the remainder, recomputes after sleep, and refuses transport if the verified gap remains short. The pacing record is persisted before or atomically with the next start. Acquisition remains sequential; UTC alone never enforces pacing.

## Future recovery boundary

These controls apply to every later protected acquisition, including possible Indiana/Memphis recovery. A separate recovery specification must freeze affected teams and triggering hashes, exact season-boundary dates, complementary nonoverlapping windows, Base and Advanced identities for each window, the R2B.1 contract, authorization consistency, canonical namespaces, source hashes, monotonic pacing records, one attempt per identity, zero retries, fail-stop behavior, no rating aggregation, and population-set reconciliation only.

R2B.2.1 selects no dates, creates no recovery identities, and authorizes no recovery. The narrowest next step after this checkpoint is read-only audit.

