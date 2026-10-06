PASS — Phase 3F-R2C.1 correction-only recovery specification hardened; ready for read-only audit

## Repository and audit status

- Branch: `research/pair-fit-v2`
- Required and final committed HEAD: `d233b71749104dcc494fbc979a4c83e86e1054ff`
- Upstream: `origin/research/pair-fit-v2`; ahead 0, behind 0
- Index: empty before and after production
- Original R2C audit: `FAIL — R2C recovery specification is not defensible`
- R2C.1: correction checkpoint awaiting a separate read-only audit

The original five R2C deliverables remain unchanged and its generated plan remains failed historical evidence. R2C.1 supersedes it only for possible future recovery authorization after audit. Neither checkpoint authorizes acquisition.

## Final Git-visible inventory

The exact final inventory is:

- modified: `.gitignore`
- preserved untracked R2C files: `PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_POLICY.md`, `PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_REPORT.md`, `src/pair_fit_v2/phase3f_r2c_recovery_specification.py`, `src/pair_fit_v2/phase3f_r2c_cli.py`, `tests/test_phase3f_r2c_recovery_specification.py`
- added R2C.1 files: `PHASE3F_R2C_1_RECOVERY_SPECIFICATION_CORRECTION_POLICY.md`, `PHASE3F_R2C_1_RECOVERY_SPECIFICATION_CORRECTION_REPORT.md`, `src/pair_fit_v2/phase3f_r2c_1_recovery_specification.py`, `src/pair_fit_v2/phase3f_r2c_1_cli.py`, `tests/test_phase3f_r2c_1_recovery_specification.py`

`.gitignore` adds only `/planning/phase3f-r2c.1/` beyond the failed checkpoint's authorized `/planning/phase3f-r2c/` addition. No commit or push was performed.

## Preservation fingerprints

The original R2C public and planning fingerprints are:

| Path | Bytes | SHA-256 |
|---|---:|---|
| `cache/phase3f-r2c-public-source/authorization-request.json` | 435 | `434f051b5bd91897b2dd0206a9cff2d8ca711da4d097e95533fae9d91d613327` |
| `cache/phase3f-r2c-public-source/attempt-1-start.json` | 224 | `ddaab6e0b05903fd886e9b2f3ceace22d177dc2d439bd43964b418f732c1f204` |
| `cache/phase3f-r2c-public-source/attempt-1-outcome.json` | 397 | `f04a957870bc603571deac07ed9a4ab7bdd6f1a771941671ae9a2d3bf928f3c9` |
| `cache/phase3f-r2c-public-source/response.html` | 126,442 | `8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3` |
| `cache/phase3f-r2c-public-source/verified-source-summary.json` | 1,080 | `348718fa280bba090e132651c4c6905a3685a97e998b1ed0f7aca9fff8110bb3` |
| `planning/phase3f-r2c/recovery_plan.json` | 121,619 | `79276836678e163d3ff45e03040aba95a412c590a6928f027765ea33bbc71daf` |
| `planning/phase3f-r2c/artifact_hashes.json` | 602 | `25bac05220a8d7c1645b235a98b8800a28d7d6df821a0a9c1a9cbe2721d4fd76` |
| `planning/phase3f-r2c/summary.json` | 705 | `d2c77126e161f695a92c1e679a216f007f4eedb35b2e3ab766d7c396625e2980` |

Their exact UTC timestamps were, in the same table order: `2026-10-02T23:17:26.7746108Z`, `2026-10-02T23:17:26.7758365Z`, `2026-10-02T23:17:28.1736549Z`, `2026-10-02T23:17:28.0028000Z`, `2026-10-02T23:17:28.1746568Z`, `2026-10-02T23:18:36.4331557Z`, `2026-10-02T23:18:36.4341618Z`, and `2026-10-02T23:18:36.4372877Z`.

The five failed R2C Git-visible files also remained exact:

| Path | Bytes | SHA-256 | UTC timestamp |
|---|---:|---|---|
| `PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_POLICY.md` | 8,135 | `5eedfc058ff616d928364082e574688cf77c6b6a3c916df02ded5c3527ac9fc3` | `2026-10-02T23:27:36.7087573Z` |
| `PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_REPORT.md` | 10,173 | `f36126191f0b4f8d0472460c2e661cca6efe58aaab911e2d0b86b41b9f5ec801` | `2026-10-02T23:31:06.6277103Z` |
| `src/pair_fit_v2/phase3f_r2c_recovery_specification.py` | 35,653 | `285a9ce240f9c232667c6c7e48bd1df3df38dfdba19e9350ddeb0efef6fe2174` | `2026-10-02T23:30:37.5045514Z` |
| `src/pair_fit_v2/phase3f_r2c_cli.py` | 1,107 | `abf1131635343f6b3178cae57ebe790b75d74922c314b14f8af268f6ac0106c8` | `2026-10-02T23:13:54.2392402Z` |
| `tests/test_phase3f_r2c_recovery_specification.py` | 14,859 | `bbb132a88a8cc3f16b31da2cba35365b9f99f47bc92f8659e558a7d738e732d5` | `2026-10-02T23:30:37.8740256Z` |

The corrected plan records path, bytes, SHA-256, and nanosecond timestamp for these five files, the eight public/planning files, and all 325 R2B-family files. Before/after equality was exact. Namespace aggregates remained:

| Namespace | Files | Bytes | Inventory SHA-256 |
|---|---:|---:|---|
| `planning/phase3f-r2b` | 2 | 72,591 | `65271de8523330662115d55ee0d30adc29396e50bfe670fc060f135ef271dc93` |
| `planning/phase3f-r2b.1` | 5 | 107,046 | `f939d0a17c6e5cc1af9ab32a8555d7933dfc6123bac16f02dcbcc40a2c6c82a9` |
| `planning/phase3f-r2b.2` | 14 | 970,695 | `e7197ffe2a0c79e1ebd9cf35d0eece53f1343ac69e1ac6f8600abb9382ed6026` |
| `planning/phase3f-r2b.2.1` | 5 | 35,479 | `e40e4bd0bbc06a62f5881bb241d4a5d1df5c202309aac9291fc0de097eab5c33` |
| `cache/phase3f-r2b` | 4 | 53,126 | `8b350170f1faf7d8ef33e8ba0ce4075ee35e3535008636b26169b908cc9e624e` |
| `cache/phase3f-r2b.2` | 295 | 6,263,873 | `3e7c88f73b8c873b3dc99c3ad6cc7dc44158afdcd05984b2001d6620287e94a5` |

## Corrected validation

The exact schema contains 12 strict Boolean fields and 11 strict nonnegative integer fields. All 23 are required. Extra fields are rejected. There are no defaults and no coercion. Boolean counts, floats, nonfinite values, negatives, strings, nulls, lists, dictionaries, nested values, missing fields, contradictions, conflict, failure, and quarantine all return `recovery_unresolved` with ordered reason codes and without an uncaught exception.

`proven_non_exhaustive` now requires explicit full-season authentication, present/authenticated/valid recovery evidence, explicit recovered-key validation, a positive strict-integer recovered-only count, Base/Advanced equality, zero key-integrity errors, and no conflict/failure/quarantine. `operationally_resolved_no_observed_omission` requires every frozen affirmative condition explicitly true, both negative indicators explicitly false, four explicit row counts below 250, and every reconciliation/error count zero. The operational result is not proof of universal or mathematical exhaustiveness.

The R2B.2.1 contract is authenticated by the exact path `planning/phase3f-r2b.2.1/future_protected_transport_contract.json` and SHA-256 `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`. The R2B.1 identity remains `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`.

All four full-season triggers are cross-checked across the exact-250, request, fingerprint, and attempt inventories. The validator binds ordinal, request ID, team, measure, raw bytes, raw hash, canonical hash, completed-verification state, and 250 rows. The exact authenticated byte counts are 65,800; 67,740; 66,452; and 68,221.

## Negative audit probes

Direct tests cover the empty record, four-Boolean-only record, count-only record, missing recovered-key validity, every individually missing schema field, an extra field, malformed nested provenance, both Boolean values in every count field, both integral-looking floats, NaN, both infinities, a negative integer, numeric string, null, list, dictionary, non-mapping containers, recovered-count/validity contradiction, conflict, failure/quarantine, a 250-row window, full-season-only keys, Base/Advanced mismatch, altered/missing/traversing/absolute/case-changed transport paths, altered transport hash, missing transport file, altered/missing/wrong-type trigger bytes with unchanged hashes, and altered trigger state/team/measure/row count. Valid examples cover all three dispositions.

## Historical test accounting

The 16 audit-identified historical deselections and three additional tests excluded here because they parse protected bodies were inspected individually. They are not described as HEAD-only, and no claim is made that their behavioral assertions were executed when they were not.

| Committed test | Historical HEAD expectation and substantive behavior | Why not run directly | Current safe coverage / gap |
|---|---|---|---|
| `test_phase3f_r2b_1_response_contract.py::test_atlanta_offline_compatibility_expected_findings` | No direct HEAD assertion; parses Atlanta and asserts exact schema, pair, and Base-field findings | Protected response-body parsing is prohibited | Exact opaque Atlanta fingerprint and immutable prior verification metadata; findings not re-derived |
| `test_phase3f_r2b_1_response_contract.py::test_historical_60_response_schema_pinning` | No direct HEAD assertion; parses all 60 historical protected responses and checks schema/order | Protected response-body parsing is prohibited | All 60 bodies and verification artifacts retain exact opaque fingerprints; schemas are exercised synthetically, not re-derived from bodies |
| `test_phase3f_r2b_1_response_contract.py::test_build_preserves_failure_and_freezes_future_eligibility` | Old repository pin; also R2B failure, Atlanta quarantine, 59 frozen requests, zero retry/recovery authorization | Its build validates protected historical bodies | Opaque preservation plus `test_historical_r2b1_metadata_current_equivalent_without_body_parsing`; body semantics not re-parsed |
| `test_phase3f_r2b_1_response_contract.py::test_deterministic_build_and_populated_or_partial_namespace_refusal` | Old pin; deterministic R2B.1 output and write-once refusal | Build reaches protected-body validation | R2C.1 write-once/determinism plus immutable authenticated R2B.1 artifacts; no R2B.1 rebuild |
| `test_phase3f_r2b_1_response_contract.py::test_generated_inventory_is_exact_and_hash_manifest_is_correct` | Old pin; exact R2B.1 inventory and payload hashes | Build reaches protected-body validation | Existing R2B.1 inventory is fingerprinted exactly; R2C.1 manifest has an independent current test |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_exact_authorization_contract_and_original_ordinals` | Old pin; 59 identities, ordinals, authorization limits, zero recovery/final-test/model authority | Historical phase repository-state contract | Safe metadata equivalent asserts the 59 requests and authorization fields; R2C.1 authenticates selected triggers |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_failed_r2b_and_all_pinned_inputs_preserved` | Old pin; Atlanta raw fingerprint, R2B.1 pins, absent promotion files | Historical phase repository-state contract | Full opaque namespace fingerprint equality and exact current metadata checks |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_atlanta_offline_revalidation_exact_findings_and_no_copy` | Old pin; parses quarantined Atlanta body and asserts schema/pair findings | Protected response-body parsing is prohibited | Exact opaque bytes/hash/timestamp and absence/preservation checks; semantic revalidation intentionally not repeated |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_authorization_and_invocation_write_once` | Old pin; idempotent authorization and invocation write-once | Historical constructor is bound to prior repository state | R2C.1 write-once regression and immutable R2B.2 authorization fingerprint; historical constructor not rerun |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_full_synthetic_execution_spacing_reconciliation_exact250_and_outputs` | Old pin; 59-call synthetic transport, pacing, reconciliation, outputs, zero recovery/final-test | Helper parses protected Atlanta body; execution path is outside correction scope | Existing R2B.2 output metadata and R2C.1 trigger/250-state checks; transport execution itself not repeated |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_base_advanced_mismatch_disposition` | No direct HEAD assertion; combines synthetic evidence with protected Atlanta pair extraction to test mismatch disposition | Protected response-body parsing is prohibited | R2C.1 directly tests Base/Advanced mismatch with wholly synthetic disposition evidence; Atlanta pairs are not re-read |
| `test_phase3f_r2b_2_protected_acquisition_continuation.py::test_stop_on_first_failure_before_next_request` | Old pin; synthetic timeout stops sequence and quarantines first identity | Historical acquisition controller is outside correction-only scope | The exact authenticated R2B.2.1 contract preserves the stop/quarantine rule; transport execution itself is not repeated |
| `test_phase3f_r2b_2_1_procedural_closure.py::test_pinned_r2b_r2b1_r2b2_evidence_and_structural_state` | Old pin; 14 artifacts, 59 bodies, Atlanta fingerprint, pacing interpretation, no recovery namespace | Historical verifier is pinned to prior repository state | Exact opaque preservation of all 325 files plus current procedural-closure metadata equivalent |
| `test_phase3f_r2b_2_1_procedural_closure.py::test_r2b2_authorization_ambiguity_detected_without_mutation` | Old pin; 59 future-only requests and byte-preserving validation | Historical verifier is pinned to prior state | Safe metadata equivalent plus before/after fingerprint equality |
| `test_phase3f_r2b_2_1_procedural_closure.py::test_historical_pacing_limitation_exact_wording_and_values` | Old pin; exact pacing statistics and cautious conclusion | Historical verifier is pinned to prior state | Authenticated procedural-closure artifact preserves exact text/values; calculation not rerun |
| `test_phase3f_r2b_2_1_procedural_closure.py::test_indiana_memphis_remain_unresolved_with_no_recovery_identity` | Old pin; two 250/250 equal-key unresolved teams, zero recovery identities/authorization | Historical verifier is pinned to prior state | Current metadata equivalent plus exact R2C.1 trigger and summary tests |
| `test_phase3f_r2b_2_1_procedural_closure.py::test_deterministic_build_and_write_once_refusal` | Old pin; deterministic closure output and namespace refusal | Historical build is pinned to prior state | Existing output hashes plus independent R2C.1 dual-build/write-once test; no closure rebuild |
| `test_phase3f_r2b_2_1_procedural_closure.py::test_generated_json_is_finite_and_hash_manifest_is_correct` | Old pin; finite closure JSON and manifest | Historical build is pinned to prior state | Existing closure fingerprints plus independent finite-JSON/manifest test; no closure rebuild |
| `test_phase3f_r0_1_documentation_reconciliation.py::test_git_visible_allowlist_and_ignore_behavior` | Old HEAD and exact Git-visible allowlist; also exact `.gitignore` behavior | Conflicts with both authorized R2C/R2C.1 additions and the current `.gitignore` delta | New exact current Git-visible allowlist and ignore regression; the committed old allowlist is intentionally not equivalent/current |

Tests that would parse protected evidence were prohibited, not merely deselected. Optional diagnostic substitution was not used as primary evidence. Current synthetic/metadata equivalents are reported separately from committed historical execution.

## Generated artifacts and verification

The ignored write-once namespace `planning/phase3f-r2c.1/` contains exactly three files:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `corrected_recovery_plan.json` | 131,714 | `eeb762fa61608b7920ef418175c8c26d54bd7436f7fa5bbbca9982d089330c07` |
| `artifact_hashes.json` | 599 | `be6abe8605a480e62d20b7c368b16039c1072804565fa4ef8ee0ba04919fa686` |
| `summary.json` | 718 | `810478e5ff8d715a9044d41c34abd7f483df6c936e18cb2f97a162ea74964417` |

An import-only canary passed. Two disposable written builds were byte-identical and were removed. The official build ran exactly once and was not rerun. Existing and partial namespace refusal passed.

Verification totals and checks:

- direct passes: 302 total
- focused R2C.1 tests: 105 passed
- safe R2C tests: 12 passed
- safe broader current regressions: 185 passed
- committed tests deselected: 19 total
- prohibited tests not run because they parse protected response bodies: 8 of those 19
- stale historical phase/HEAD/Git-state tests not run directly: 11 of those 19
- optional diagnostic substitutions: 0
- dedicated current synthetic/opaque-metadata equivalents: 4 passed (included in the 105 focused tests)
- `py_compile`: passed
- `git diff --check`: passed
- ignore, credential, capability, prohibited-artifact, exact-inventory, and 338-file preservation scans: passed

Pytest emitted cache-provider warnings because the pre-existing `.pytest_cache` directory was not writable; test execution and results were unaffected.

## Request and readiness accounting

- Network requests: 0
- Public-source reuse: yes; requests made by R2C.1: 0
- Protected requests: 0
- Indiana/Memphis recovery requests: 0
- Protected response bodies parsed or copied: 0
- Final-test rows: 0
- Estimator/model operations: 0
- Indiana and Memphis: still `exact_250_unresolved`
- Final-test readiness: blocked on recovery and later audited gates

The narrowest justified next step is a separate read-only audit of R2C.1. This PASS does not authorize any of the eight recovery requests.
