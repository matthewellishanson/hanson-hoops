PASS — Phase 3F-R2C exact-250 recovery specification frozen; ready for read-only audit

## Repository and preflight

- Branch: `research/pair-fit-v2`
- Starting and final committed HEAD: `d233b71749104dcc494fbc979a4c83e86e1054ff`
- Upstream: `origin/research/pair-fit-v2`; ahead `0`, behind `0`
- Starting index and working tree: clean
- Prior blocked R2C attempt: stopped during preflight with no deliverable, generated namespace, request identity, or working-tree change
- No prior `cache/phase3f-r2c-public-source/`, `planning/phase3f-r2c/`, R2C deliverable, or Indiana/Memphis recovery state existed
- Indiana (`1610612754`) and Memphis (`1610612763`) were and remain the only `exact_250_unresolved` teams

The final Git-visible inventory is exactly:

- modified: `.gitignore`
- added: `PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_POLICY.md`
- added: `PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_REPORT.md`
- added: `src/pair_fit_v2/phase3f_r2c_recovery_specification.py`
- added: `src/pair_fit_v2/phase3f_r2c_cli.py`
- added: `tests/test_phase3f_r2c_recovery_specification.py`

The index remains empty. No commit or push was performed.

## Public source request

Exactly one public request was made and it completed successfully. It was an exact-allowlist HTTP GET with established non-secret research headers, `trust_env=False`, redirects disabled, a 30-second timeout, zero automatic retries, and no fallback.

- URL: `https://pr.nba.com/2025-26-nba-regular-season-schedule/`
- Title: `NBA announces schedule for 2025-26 regular season - NBA.com: NBA Communications`
- Publication timestamp: `2025-08-14T19:13:45+00:00`
- Retrieval timestamp: `2026-10-02T23:17:28.172654Z`
- HTTP outcome: `200`, not redirected
- Response bytes: `126442`
- Raw SHA-256: `8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3`
- Verified season start: `2025-10-21`
- Verified season end: `2026-04-12`

The ignored, write-once namespace `cache/phase3f-r2c-public-source/` contains only the authorization/request metadata, immutable start, immutable outcome, exact response body, and verified source summary. No link was crawled and no attachment was downloaded.

## Complementary-window proof

- Early: `2025-10-21` through `2026-01-31`
- Late: `2026-02-01` through `2026-04-12`
- Both within verified interval: yes
- Nonoverlapping: yes
- Contiguous: yes; `2026-02-01` immediately follows `2026-01-31`
- Missing dates: zero
- Verified interval: 174 inclusive calendar days
- Window union: 174 inclusive calendar days
- Complete coverage: yes

## Exact future request inventory

These are frozen identities, not authorizations or executions:

1. `teamdashlineups:1610612754:2025-26:regular-season:2025-10-21:2026-01-31:base`
2. `teamdashlineups:1610612754:2025-26:regular-season:2025-10-21:2026-01-31:advanced`
3. `teamdashlineups:1610612754:2025-26:regular-season:2026-02-01:2026-04-12:base`
4. `teamdashlineups:1610612754:2025-26:regular-season:2026-02-01:2026-04-12:advanced`
5. `teamdashlineups:1610612763:2025-26:regular-season:2025-10-21:2026-01-31:base`
6. `teamdashlineups:1610612763:2025-26:regular-season:2025-10-21:2026-01-31:advanced`
7. `teamdashlineups:1610612763:2025-26:regular-season:2026-02-01:2026-04-12:base`
8. `teamdashlineups:1610612763:2025-26:regular-season:2026-02-01:2026-04-12:advanced`

All eight bind `TeamDashLineups`, `2025-26`, `Regular Season`, `GroupQuantity=2`, `PerMode=Totals`, their exact measure/window, all unchanged corresponding R2B.2 parameters, both team trigger identities and hashes, the two governing contracts, and a unique exact future output namespace. A ninth or divergent identity is rejected.

## Trigger and governing identities

Indiana Pacers:

- Base ordinal 35, `teamdashlineups:1610612754:base`, 65,800 bytes, raw `d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3`, canonical JSON `0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5`
- Advanced ordinal 36, `teamdashlineups:1610612754:advanced`, 67,740 bytes, raw `45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee`, canonical JSON `605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120`

Memphis Grizzlies:

- Base ordinal 53, `teamdashlineups:1610612763:base`, 66,452 bytes, raw `540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29`, canonical JSON `b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc`
- Advanced ordinal 54, `teamdashlineups:1610612763:advanced`, 68,221 bytes, raw `d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6`, canonical JSON `2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3`

Governing contracts:

- Corrected R2B.1 response-contract identity: `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`
- R2B.2.1 future protected-transport-contract file SHA-256: `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`

## Operational resolution policy

`operationally_resolved_no_observed_omission` requires all four team responses to be authenticated and structurally valid; every individual window response below 250 canonical rows; exact Base/Advanced equality within each window; complete complementary coverage; exact equality between the window union and full-season pair-key set; zero recovered-only and full-season-only keys; and zero duplicate, malformed, same-player, Base-only, or Advanced-only keys.

This is an operational readiness decision: no omission was observed under the predeclared design. It is not proof of universal or mathematical endpoint exhaustiveness and must never be presented as “proven exhaustive.” A valid recovered-only key instead yields `proven_non_exhaustive`; all other incomplete or conflicting states yield `recovery_unresolved`.

## Generated planning artifacts

The import-only canary passed. Two disposable builds were byte-identical and their directories were removed. The official build ran exactly once. `planning/phase3f-r2c/` contains exactly three ignored, write-once files:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `recovery_plan.json` | 121,619 | `79276836678e163d3ff45e03040aba95a412c590a6928f027765ea33bbc71daf` |
| `artifact_hashes.json` | 602 | `25bac05220a8d7c1645b235a98b8800a28d7d6df821a0a9c1a9cbe2721d4fd76` |
| `summary.json` | 705 | `d2c77126e161f695a92c1e679a216f007f4eedb35b2e3ab766d7c396625e2980` |

The manifest rule is nonrecursive SHA-256 over the exact bytes of `recovery_plan.json` and `summary.json`; `artifact_hashes.json` excludes itself to avoid circularity.

## Verification

- Focused R2C tests: 33 passed
- Applicable R2B.1, R2B.2, R2B.2.1, R2A, R1S, R0/R0.1, acquisition, recovery, and canonicalization regressions: 360 passed, 16 deselected
- Additional foundational acquisition/canonicalization regressions: included in the 360-pass total
- `py_compile`: passed
- Disposable deterministic builds: byte-identical
- Official generated inventory and manifest: passed
- Git-ignore checks: passed
- Credential and prohibited-artifact scans: passed
- `git diff --check`: passed

The 16 deselections are historical construction/state tests whose sole failure is an intentional hard pin to an earlier committed HEAD:

- `test_phase3f_r2b_1_response_contract.py::{test_build_preserves_failure_and_freezes_future_eligibility,test_deterministic_build_and_populated_or_partial_namespace_refusal,test_generated_inventory_is_exact_and_hash_manifest_is_correct}`
- `test_phase3f_r2b_2_protected_acquisition_continuation.py::{test_exact_authorization_contract_and_original_ordinals,test_failed_r2b_and_all_pinned_inputs_preserved,test_atlanta_offline_revalidation_exact_findings_and_no_copy,test_authorization_and_invocation_write_once,test_full_synthetic_execution_spacing_reconciliation_exact250_and_outputs,test_stop_on_first_failure_before_next_request}`
- `test_phase3f_r2b_2_1_procedural_closure.py::{test_pinned_r2b_r2b1_r2b2_evidence_and_structural_state,test_r2b2_authorization_ambiguity_detected_without_mutation,test_historical_pacing_limitation_exact_wording_and_values,test_indiana_memphis_remain_unresolved_with_no_recovery_identity,test_deterministic_build_and_write_once_refusal,test_generated_json_is_finite_and_hash_manifest_is_correct}`
- `test_phase3f_r0_1_documentation_reconciliation.py::test_git_visible_allowlist_and_ignore_behavior`

No behavioral failure was suppressed.

## Preservation evidence

Before-state fingerprints were captured in `recovery_plan.json` as path, byte count, SHA-256, and nanosecond modification time for every file. After-state comparison was exact for every entry:

| Namespace | Files | Bytes | Inventory SHA-256 |
|---|---:|---:|---|
| `planning/phase3f-r2b` | 2 | 72,591 | `65271de8523330662115d55ee0d30adc29396e50bfe670fc060f135ef271dc93` |
| `planning/phase3f-r2b.1` | 5 | 107,046 | `f939d0a17c6e5cc1af9ab32a8555d7933dfc6123bac16f02dcbcc40a2c6c82a9` |
| `planning/phase3f-r2b.2` | 14 | 970,695 | `e7197ffe2a0c79e1ebd9cf35d0eece53f1343ac69e1ac6f8600abb9382ed6026` |
| `planning/phase3f-r2b.2.1` | 5 | 35,479 | `e40e4bd0bbc06a62f5881bb241d4a5d1df5c202309aac9291fc0de097eab5c33` |
| `cache/phase3f-r2b` | 4 | 53,126 | `8b350170f1faf7d8ef33e8ba0ce4075ee35e3535008636b26169b908cc9e624e` |
| `cache/phase3f-r2b.2` | 295 | 6,263,873 | `3e7c88f73b8c873b3dc99c3ad6cc7dc44158afdcd05984b2001d6620287e94a5` |

All 60 full-season protected Base/Advanced bodies remain byte-, hash-, path-, and timestamp-identical. Protected evidence remains ignored and absent from Git-visible inventory. No protected response body was parsed, copied, displayed, changed, deleted, or acquired; it was read only as opaque bytes for fingerprints.

## Request and readiness accounting

- Public-source requests: exactly 1
- Protected requests: 0
- Indiana/Memphis recovery requests: 0
- Final-test rows constructed: 0
- Model operations: 0
- Indiana and Memphis remain unresolved until the eight identities are separately authorized, acquired, reconciled, and audited
- All final-test readiness gates retain their correct pending state

The narrowest justified next step is a separate read-only audit of this checkpoint. PASS does not authorize any of the eight protected recovery requests.
