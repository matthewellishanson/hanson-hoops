# Phase 3F-R3 final-test construction and readiness report

**PASS — 2025–26 final-test dataset constructed and all six readiness gates passed; ready for read-only audit**

## Decision and repository state

Mandatory preflight passed on branch `research/pair-fit-v2` at exact HEAD `6dc1234fd6dc2643af8718f77ca5651eb5c6594a`, upstream divergence `0/0`, clean index, and initially clean worktree. The official write-once namespace is `curated/phase3f-r3/`; it remains ignored. No commit or push occurred.

The R0/R0.1 29,701-row expanded-training construction, R1S plan, R2A 2024–25 Per100/Totals profiles, protected R2B/R2B.1/R2B.2/R2B.2.1 lineage, R2C/R2C.1 specifications, failed R2D, corrected R2D.1, and completed R2D.2 evidence were authenticated through pinned manifests, payload hashes, and namespace fingerprints. All 60 direct full-season protected responses were byte-authenticated. The 2024–25 profile bodies are `047d8c…fc9ff` and `3bd210…ccd5`; the expanded preprocessing state is `a0180d…f47e`.

## Constructed population and matrix

- Raw direct full-season rows: 5,403 across all 30 teams; 4,903 across the retained 28 teams before eligibility.
- Retained eligible population: 2,811 rows and 2,250,488 possessions.
- Indiana (`1610612754`) and Memphis (`1610612763`): zero retained rows each; both excluded in full. No other team was excluded.
- Complete history: 2,154 rows; one missing: 597; both missing: 60; missing player slots: 717.
- Selected profile slots: 4,859 from 2024–25, 38 from 2023–24, and 8 from 2022–23. Strict-prior failures and lookback violations: zero.
- Estimator matrix: `2,811 × 45`, exact frozen feature order, finite throughout, no target/exposure/reliability/provenance or slot-specific columns.
- Slot-swap comparisons: 126,495; mismatches: zero.
- Staging, row index, target vector, and estimator matrix have identical row counts and ordering. Observation keys are unique and numeric-canonical. Base/Advanced pair keys match for every team. Every target is direct full-season Advanced `NET_RATING`; every eligibility possession is direct full-season Advanced `POSS` on the matching Base-reconciled key. No recovery-window row supplies a retained row, target, or possession.
- R0 player-slot medians and symmetric fills were reused; the R0 scaler was applied exactly once. No final-test statistic was learned. The persisted matrix is explicitly `scaled_once_ready_for_direct_ridge_prediction`.

## Frozen readiness gates

| Gate | Status |
| --- | --- |
| `predictor_evidence_completeness` | passed |
| `target_evidence_completeness` | passed |
| `team_population_exhaustiveness` | passed |
| `row_eligibility` | passed |
| `row_alignment` | passed |
| `protected_result_reveal` | passed |

This checkpoint does not clear its own read-only audit and does not authorize the one-time final model execution.

## Generated artifacts

The manifest content SHA-256 is `23d55a74dc0d10548658914a146571724aac195b6aa44d96d2507ee20aa94e32`. Its explicit nonrecursive rule hashes the ten payloads and excludes itself and `summary.json`.

| Artifact | SHA-256 |
| --- | --- |
| `final_test_staging.csv` | `c7994aceebedf4093e97d3b0b41d28ab69abaebb38f6486d07c82a5125635f06` |
| `final_test_row_index.csv` | `b0c2204be4dd67d504cde0e720f3453160416a3e9f838aad6e45273d197225f9` |
| `final_test_target_vector.csv` | `a258c02992f2006ee083d39b79d328f775d8923157d80f7bed2c73955d276198` |
| `final_test_estimator_matrix_scaled.csv` | `b8213cd44ace50cb88860c832d0f810e497e403c31ff029b9ed323ed3a601f6f` |
| `estimator_feature_manifest.json` | `b2ef6f25b18e1b5522c2624c1b0532648ac961c4558114fc8d94e437351564a6` |
| `applied_preprocessing_state_identity.json` | `027022517341ea65febe3b779feb7254f2605cb5f125795cd0f97c258311efa6` |
| `population_diagnostics.json` | `b804699b30027e3ed1f7a255dd36d5b359f529d2838748828e23b8975ee6812d` |
| `history_selection_diagnostics.json` | `502e46022560428c83af930fac0ad30f46ce2c6a454ec7a797b51d575b8fcaba` |
| `input_fingerprints.json` | `23f0f9e00ff205988a3890017003bc59e6a704fc1aae78c8cef455a8e58922fb` |
| `readiness_gates.json` | `3b63cc6502dab36de9d8413fa3f3495cfcd57941355fffd112ae0a5eb5e495a8` |
| `artifact_hashes.json` | `58382f587c1b2b679fb8a24ac7652b8ff131749c5e6a0e248a769f4a535aacd6` |
| `summary.json` | `0d262e096e3fc3de9a8ca8b5cb6d84f7ea1a608eca662289cdf43310b1b8b2f7` |

Protected lineage fingerprints and the expanded-training namespace fingerprint (`dd93ca3c9db95ffff35197c85891f4596e794d704f4b2fe84bb740f0361c226f`) matched before and after. `input_fingerprints.json` records the complete identities.

## Verification and stop boundary

Focused R3 tests: 15 passed, including two independent byte-identical disposable builds and write-once restart refusal. Directly relevant historical regressions: 108 passed; 7 obsolete checkpoint-guard tests rejected the current required HEAD instead of their phase-local historical HEAD, with no scientific or construction regression failure. `py_compile`, strict JSON and manifest verification, ignore checks, prohibited capability/artifact scans, protected/expanded fingerprint replay, and `git diff --check` all passed.

Network, acquisition, retry, estimator construction, fitting, prediction, metric, and model-serialization operations in this checkpoint: zero each. The exact Git-visible inventory is this policy, this report, the implementation module, CLI, and focused test module.

The narrowest justified next step is one focused read-only audit of this checkpoint. A successful audit still does not authorize final model execution; that requires separate user authorization.
