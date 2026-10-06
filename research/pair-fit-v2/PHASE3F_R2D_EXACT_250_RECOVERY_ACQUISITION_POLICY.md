# Phase 3F-R2D Exact-250 Recovery Acquisition Policy

## Status and boundary

Phase 3F-R2D is a production evidence checkpoint for the Indiana Pacers and Memphis Grizzlies only. It is limited to the eight protected 2025–26 TeamDashLineups requests frozen by the audit-cleared Phase 3F-R2C.1 corrected recovery plan.

The phase may acquire, authenticate, and structurally validate those eight responses; reauthenticate and parse the four specified Indiana/Memphis full-season Base/Advanced bodies; reconcile canonical pair-key populations; and apply the exact R2C.1 disposition classifier. It may not aggregate ratings, reconstruct targets, construct a final-test population, join prior profiles, preprocess data, run or evaluate a model, serialize a model, or change application or deployment systems.

R2C remains failed historical evidence. R2C.1 is the sole recovery specification used here.

## Frozen authority

The implementation refuses work unless all of the following match:

- branch `research/pair-fit-v2` at committed HEAD `f7f72eda75fecfeab044b6f0315f263b71af657d`;
- upstream ahead/behind `0/0`;
- `planning/phase3f-r2c.1/corrected_recovery_plan.json`, 131,714 bytes, SHA-256 `eeb762fa61608b7920ef418175c8c26d54bd7436f7fa5bbbca9982d089330c07`;
- the complete three-file R2C.1 namespace and its nonrecursive manifest;
- R2B.1 response-contract identity `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`;
- `planning/phase3f-r2b.2.1/future_protected_transport_contract.json`, 4,074 bytes, SHA-256 `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`;
- the already acquired public schedule evidence at 126,442 bytes and SHA-256 `8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3`, without reacquisition;
- Indiana and Memphis still classified `exact_250_unresolved`;
- absence of every earlier or R2D recovery namespace; and
- unchanged historical R2B, R2B.1, R2B.2, R2B.2.1, R2C, R2C.1, and public-source evidence.

Historical protected response bodies outside the four explicitly authorized full-season records are not opened or parsed. Their preservation is checked against the frozen inventory by path, regular-file status, byte count, and nanosecond modification time, carrying forward their already frozen content hashes. Metadata and committed source are rehashed. The four authorized full-season bodies are independently rehashed and structurally revalidated before parsing.

## Exact request inventory

The only transport order is:

1. Indiana early Base
2. Indiana early Advanced
3. Indiana late Base
4. Indiana late Advanced
5. Memphis early Base
6. Memphis early Advanced
7. Memphis late Base
8. Memphis late Advanced

Early is `2025-10-21` through `2026-01-31`. Late is `2026-02-01` through `2026-04-12`. Every request uses season `2025-26`, season type `Regular Season`, endpoint `TeamDashLineups`, `GroupQuantity=2`, and `PerMode=Totals`, with every other parameter copied exactly from the corrected plan. Any ninth or altered request is rejected before transport.

## Immutable authorization

Before transport, `planning/phase3f-r2d/recovery_authorization.json` pins the starting Git identity, corrected-plan identity, governing contracts, exact ordered requests, output namespaces, acquisition source and CLI bytes/hashes, Python executable identity, working directory, `PYTHONPATH=src`, official command, transport settings, historical preservation fingerprints, and prohibited operations.

The official process rehashes its source and CLI and refuses a mismatch. Planning evidence is bound to `planning/phase3f-r2d/`; protected recovery evidence is bound to `cache/phase3f-r2d/protected-recovery/`. Both are ignored, write-once namespaces. Alternate or aliased namespaces are rejected.

## Transport and pacing

Requests are sequential. Each identity has one attempt, zero automatic retries, no redirect following, a 30-second timeout, `trust_env=False`, no proxy substitution, no fallback endpoint, and the established non-secret research headers.

Each attempt-start record is persisted before transport. It contains UTC and process-monotonic timestamps, the preceding request's monotonic completion, the pre-sleep gap, requested sleep, observed post-sleep gap, threshold, clock identity, and pacing disposition. For requests 2–8, the persisted completion-to-next-start monotonic interval must be at least `1.000000` seconds. A short observed interval stops the phase before transport.

After receipt, the exact bytes are written once. Authentication and structural verification occur before promotion to the verified body. An HTTP, connection, timeout, redirect, identity, JSON, schema, row, pair-key, or exposure-field failure writes an immutable outcome and quarantine record and stops immediately. No later identity is attempted.

## Restart states

Every request directory is classified only from its records and body state:

- `not_started`: eligible for its single attempt;
- `completed_verified`: rehashed, revalidated, and skipped by cache-only logic;
- `started_without_outcome`: stop for audit;
- `failed_or_quarantined`: preserve and stop;
- `conflicting_state`: refuse progress.

The official launch itself is authorized once. Its immutable start record prevents a second launch. A failed or stopped launch is preserved and is not repaired or rerun.

## Response authentication

Each response must have the exact R2C.1 request identity, HTTP 200, no redirect, attempt 1, no retry or failure reason, strict JSON, the established `Overall` then `Lineups` envelope, the exact measure-specific schemas, valid row widths, numeric team and player identifiers, exactly two distinct positive player IDs ordered numerically as the canonical key, no duplicate key, and valid measure-specific exposure fields.

An individual recovery response with 250 rows remains structurally authentic but blocks operational resolution under the frozen classifier.

## Population reconciliation

Reconciliation starts only after all eight recovery responses are `completed_verified`. It then reauthenticates and parses only the four frozen full-season Indiana/Memphis bodies and the eight new bodies.

Base and Advanced canonical key equality is required independently for each team/window. Zero-possession Advanced rows remain explicit. Each team's early/late union is compared with its authenticated full-season population. Counts and exact set differences are recorded, including full-season and window counts, union and overlap, recovered-only and full-season-only keys, duplicate/malformed/same-player counts, and Base-only/Advanced-only counts.

For recovered-only keys, Advanced possessions may be summed across the two nonoverlapping windows only as diagnostic exposure metadata. The diagnostic records early, late, summed possessions, and whether `POSS >= 150`. It never changes team disposition and never supplies a target.

No `OFF_RATING`, `DEF_RATING`, or `NET_RATING` aggregation is permitted. No full-season rating or recovered-only target is reconstructed.

## Frozen dispositions

The implementation calls only the exact R2C.1 schema validator/classifier. Every required field is explicit; sparse, malformed, contradictory, or extra-field input fails closed to `recovery_unresolved`.

- `proven_non_exhaustive` requires the complete authenticated record and at least one validated recovered-only key.
- `operationally_resolved_no_observed_omission` requires all four responses present/authenticated/valid, each below 250, Base/Advanced equality in both windows, complete coverage, exact union equality, zero set differences, and zero structural anomalies.
- every other state is `recovery_unresolved`.

Operational resolution means no omission was observed under this frozen design; it is not universal endpoint-exhaustiveness proof. Proven non-exhaustiveness establishes that the returned full-season population was incomplete, but R2D does not perform the later whole-team exclusion or seek targets elsewhere.

## Artifacts and stop rule

On complete acquisition and reconciliation, the planning namespace contains exactly eight files named in the production prompt. `artifact_hashes.json` uses a nonrecursive rule and excludes itself. The protected namespace contains immutable per-attempt and official-invocation evidence. Historical bodies are referenced, not copied.

`readiness_effect.json` changes only Indiana/Memphis exact-250 evidence status. It does not declare the final-test pipeline ready or authorize execution.

The phase stops after the R2D checkpoint. The narrowest permissible next step is a separate read-only audit. No commit or push is part of this phase.
