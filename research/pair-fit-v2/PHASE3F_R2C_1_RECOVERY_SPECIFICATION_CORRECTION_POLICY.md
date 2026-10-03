# Phase 3F-R2C.1 Correction-Only Recovery Specification Policy

## Status and authority boundary

**R2C failed its read-only audit: `FAIL — R2C recovery specification is not defensible`.** The original R2C public-source and planning evidence remains immutable historical evidence. R2C.1 supersedes R2C only as the specification that a future recovery-authorization checkpoint must use, and only after R2C.1 passes a separate read-only audit.

R2C.1 is offline and correction-only. It makes no network, protected, or recovery request; opens no protected response body as structured data; constructs no final-test row; and performs no estimator, prediction, metric, serialization, database, backend, API, frontend, presentation, or deployment operation. Neither R2C nor R2C.1 authorizes acquisition of the eight frozen identities.

## Frozen science and request inventory

The authenticated official source remains the previously acquired NBA Communications page at `https://pr.nba.com/2025-26-nba-regular-season-schedule/`: 126,442 bytes, raw SHA-256 `8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3`. It establishes the regular-season interval `2025-10-21` through `2026-04-12`. R2C.1 reuses that exact five-file namespace without a request and without reparsing the HTML.

The complementary windows remain unchanged:

| Window | DateFrom | DateTo |
|---|---|---|
| early | `2025-10-21` | `2026-01-31` |
| late | `2026-02-01` | `2026-04-12` |

The eight future Indiana/Memphis Base/Advanced identities, their parameters, output namespaces, and scientific purpose remain byte-for-byte equivalent to the independently validated identities in the failed R2C plan. Population-only reconciliation remains frozen. Ratings are not aggregated, targets are not reconstructed, zero-possession rows remain population evidence, and no rating value controls retention.

## Exact disposition-input contract

The machine-readable schema is `phase3f-r2c.1.team-disposition-input.v1`. Its field set is exact; all fields are required; additional properties are rejected; no default or coercion exists.

Boolean fields require `type(value) is bool`:

- `full_season_evidence_authenticated`
- `all_four_recovery_responses_present`
- `all_four_recovery_responses_authenticated`
- `all_four_recovery_responses_structurally_valid`
- `complete_complementary_date_coverage`
- `every_individual_window_below_250`
- `early_base_advanced_keys_equal`
- `late_base_advanced_keys_equal`
- `window_union_equals_full_season_keys`
- `recovered_only_keys_validated`
- `conflicting_state`
- `failed_or_quarantined`

Count fields require `type(value) is int` and a value of zero or greater:

- `early_base_pair_row_count`
- `early_advanced_pair_row_count`
- `late_base_pair_row_count`
- `late_advanced_pair_row_count`
- `recovered_only_count`
- `full_season_only_count`
- `duplicate_count`
- `malformed_pair_count`
- `same_player_count`
- `base_only_count`
- `advanced_only_count`

Booleans are rejected as counts even though Python makes `bool` a subclass of `int`. Floats, including `0.0` and `1.0`, nonfinite floats, negative integers, strings, nulls, lists, dictionaries, and nested containers are rejected. Invalid input is never coerced and never receives a favorable fallback.

## Fail-closed disposition rules

The evaluator returns a disposition plus ordered deterministic reason codes. The string-only classifier delegates to the same evaluator. Invalid input cannot propagate an exception to its caller; an unexpected processing failure yields `recovery_unresolved` with `invalid_record_processing_failure`.

`proven_non_exhaustive` is possible only when a positive integer recovered-only count is accompanied by explicit recovered-key validation; authenticated full-season evidence; all four recovery responses present, authenticated, and structurally valid; Base/Advanced equality in both windows; zero malformed, duplicate, same-player, Base-only, and Advanced-only counts; and no conflict, failure, or quarantine. A positive recovered-only count with union equality is contradictory and unresolved. A count-only object can never prove non-exhaustiveness. One or more properly validated recovered-only keys continues to prove that the full-season response is incomplete.

`operationally_resolved_no_observed_omission` is possible only when every Boolean condition is explicitly true except the conflict and failure indicators, which must explicitly be false; all four explicit window row counts are below 250 and agree with the threshold indicator; recovered-only keys are explicitly validated; and every reconciliation/error count is exactly zero. This is operational resolution under the frozen design, not universal or mathematical proof of exhaustiveness.

Every other record yields `recovery_unresolved`, including missing or extra fields, wrong types, Boolean counts, negative or nonfinite counts, contradictions, failed/quarantined evidence, conflicting state, incomplete coverage, a 250-row window, Base/Advanced mismatch, a nonempty full-season-only set, unauthenticated evidence, or unavailable evidence.

Reason-code families are stable and machine-readable: `record_not_mapping`, `missing_field:<field>`, `unexpected_field:<field>`, `invalid_boolean_type:<field>`, `invalid_count_type:<field>`, `negative_count:<field>`, `contradiction:<condition>`, `evidence_conflicting`, `evidence_failed_or_quarantined`, and disposition-specific `required_true...` or `required_zero...` codes.

## Governing-contract and trigger authentication

The future protected transport contract must bind both exact repository-relative path and exact SHA-256:

- path: `planning/phase3f-r2b.2.1/future_protected_transport_contract.json`
- SHA-256: `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`

Absolute paths, traversal, normalization aliases, case changes, alternate relative paths, missing fields, missing files, wrong hashes, and recomputed-hash mismatches are rejected. The corrected R2B.1 response-contract identity remains exactly `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`, and its containing file is also fingerprinted before its identity is read.

Each Indiana and Memphis trigger is independently reconciled across the R2B.2 exact-250 inventory, request inventory, response fingerprints, and attempt inventory. Ordinal, request ID, team ID, measure, raw byte count, raw SHA-256, canonical JSON SHA-256, `completed_verified` state, and 250-row count must all be present, correctly typed, and exact. A byte count of `1`, a missing count, or a string count fails even when all hashes are unchanged.

## Preservation and generated state

The five failed R2C Git-visible deliverables, five-file public-source namespace, three-file original R2C planning namespace, and every file in the relevant R2B/R2B.1/R2B.2/R2B.2.1 evidence and planning namespaces are authenticated by path, byte count, SHA-256, and nanosecond timestamp. Protected bodies are treated only as opaque bytes for hashing; they are not decoded, parsed, copied, displayed, or promoted.

The ignored namespace `planning/phase3f-r2c.1/` is write-once and contains exactly `corrected_recovery_plan.json`, `artifact_hashes.json`, and `summary.json`. Construction and JSON validation occur in memory first. Existing, partial, symlinked, or conflicting namespaces are refused. JSON is canonical and finite. Two disposable written builds must be byte-identical and removed before the one official build.

## Stop condition

Indiana and Memphis remain `exact_250_unresolved`. Final-test readiness remains blocked on recovery and later audited gates. A production PASS for R2C.1 permits only a separate read-only audit; it does not authorize a recovery request.
