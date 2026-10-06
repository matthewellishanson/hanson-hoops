# Phase 3F-R1S narrow corrections complete; ready for repeated read-only audit

## Repository state

- Branch: `research/pair-fit-v2`
- HEAD: `20469c320886b6ea306fe3e5d17cbc3db23c6824`
- Upstream: `origin/research/pair-fit-v2`
- Ahead/behind: `0/0`
- Index: clean
- No commit or push was performed.

The only tracked change is the narrow `.gitignore` replacement of the three removed R1/R1.1/R1.2 planning rules with `/planning/phase3f-r1s/`. The five R1S policy, report, source, CLI, and test files are untracked. The official three-file planning namespace is ignored.

## Narrow correction record

Before deletion, `tests/__pycache__/test_phase3f_r1_acquisition_plan.cpython-312-pytest-8.3.5.pyc` was independently verified as exactly 94,310 bytes with SHA-256 `e3606207e9a7c92e8b156567b99a5a60a5e5400c0863dda07ed575aa69aa9f94`. That exact abandoned-R1 bytecode remnant was deleted. No other pre-existing bytecode or cache file was deleted.

The readiness boundary now states:

> Final model execution requires all three of the following: (1) every frozen Phase 3F final-test readiness gate passes; (2) the completed readiness checkpoint receives read-only audit clearance; and (3) the user separately authorizes the one-time final model execution.

The six frozen gate identities remain predictor evidence completeness, target evidence completeness, team-population exhaustiveness, row eligibility, row alignment, and protected final-result reveal. Any failed or unresolved gate blocks execution. R1S planning does not authorize acquisition; acquisition completion does not authorize final-test construction or model execution; reconciliation does not authorize fitting or prediction; readiness assessment does not itself authorize execution; final execution remains a separate later phase; and no unresolved or excluded team-season may silently enter the final test.

Correction-pass changes were limited to:

- `PHASE3F_R1S_SIMPLIFIED_ACQUISITION_POLICY.md`
- `PHASE3F_R1S_SIMPLIFIED_ACQUISITION_REPORT.md`
- `src/pair_fit_v2/phase3f_r1s_acquisition_plan.py`
- `tests/test_phase3f_r1s_acquisition_plan.py`
- replacement of the three verified files in `planning/phase3f-r1s/`

The R1S CLI and `.gitignore` rule were not changed by the correction pass. No unrelated file changed.

## Authorized cleanup

The following uncommitted implementation files were deleted:

- `PHASE3F_R1_ACQUISITION_MACHINERY_POLICY.md`
- `PHASE3F_R1_ACQUISITION_MACHINERY_REPORT.md`
- `PHASE3F_R1_1_ACQUISITION_INTEGRITY_POLICY.md`
- `PHASE3F_R1_1_ACQUISITION_INTEGRITY_REPORT.md`
- `PHASE3F_R1_2_EVIDENCE_AUTHENTICATION_POLICY.md`
- `PHASE3F_R1_2_EVIDENCE_AUTHENTICATION_REPORT.md`
- `src/pair_fit_v2/phase3f_r1_acquisition_plan.py`
- `src/pair_fit_v2/phase3f_r1_cli.py`
- `src/pair_fit_v2/phase3f_r1_1_acquisition_integrity.py`
- `src/pair_fit_v2/phase3f_r1_1_cli.py`
- `src/pair_fit_v2/phase3f_r1_2_evidence_authentication.py`
- `src/pair_fit_v2/phase3f_r1_2_cli.py`
- `tests/test_phase3f_r1_acquisition_plan.py`
- `tests/test_phase3f_r1_1_acquisition_integrity.py`
- `tests/test_phase3f_r1_2_evidence_authentication.py`

The exact ignored planning files deleted were:

- `planning/phase3f-r1/{artifact_hashes.json,conditional_recovery_policy.json,input_fingerprints.json,prior_profile_inventory.json,readiness_gate_contract.json,record_schemas.json,request_authorization_plan.json,summary.json}`
- `planning/phase3f-r1.1/{artifact_hashes.json,authenticated_plan_binding.json,correction_contract.json,hardened_record_schemas.json,input_fingerprints.json,reconciliation_and_readiness_contract.json,restart_and_quarantine_contract.json,semantic_verification_contract.json,summary.json}`
- `planning/phase3f-r1.2/{artifact_hashes.json,correction_contract.json,evidence_bundle_contract.json,input_fingerprints.json,readiness_authentication_contract.json,restart_semantics_contract.json,summary.json}`

The exact failed-phase generated test/bytecode residue deleted was:

- `.pytest_tmp/phase3f_r1_20/{left,right}/{artifact_hashes.json,correction_contract.json,evidence_bundle_contract.json,input_fingerprints.json,readiness_authentication_contract.json,restart_semantics_contract.json,summary.json}`
- `src/pair_fit_v2/__pycache__/{phase3f_r1_acquisition_plan,phase3f_r1_cli,phase3f_r1_1_acquisition_integrity,phase3f_r1_1_cli,phase3f_r1_2_evidence_authentication,phase3f_r1_2_cli}.cpython-312.pyc`
- `tests/__pycache__/test_phase3f_r1_acquisition_plan.cpython-312.pyc`
- `tests/__pycache__/test_phase3f_r1_1_acquisition_integrity.{cpython-312,cpython-312-pytest-8.3.5}.pyc`
- `tests/__pycache__/test_phase3f_r1_2_evidence_authentication.{cpython-312,cpython-312-pytest-8.3.5}.pyc`

Deletion stayed within the explicitly authorized R1/R1.1/R1.2 paths. No unrelated file, Phase 3E evidence, raw cache, or R0/R0.1 file was deleted or modified.

## Retained and new paths

Retained unchanged: all committed Phase 3F-R0/R0.1 policies, reports, sources, CLIs, and tests, plus the complete `curated/phase3f-r0/` and `curated/phase3f-r0.1/` namespaces.

New commit-eligible paths:

- `PHASE3F_R1S_SIMPLIFIED_ACQUISITION_POLICY.md`
- `PHASE3F_R1S_SIMPLIFIED_ACQUISITION_REPORT.md`
- `src/pair_fit_v2/phase3f_r1s_acquisition_plan.py`
- `src/pair_fit_v2/phase3f_r1s_cli.py`
- `tests/test_phase3f_r1s_acquisition_plan.py`

New ignored generated paths:

- `planning/phase3f-r1s/acquisition_plan.json`
- `planning/phase3f-r1s/artifact_hashes.json`
- `planning/phase3f-r1s/summary.json`

## R0/R0.1 nonmutation

Before-and-after SHA-256 fingerprints matched for all 14 generated artifacts:

| Namespace | File | SHA-256 |
|---|---|---|
| R0 | `artifact_hashes.json` | `802a14a978d937a07bf0cbeb1b93fa177b2904ef3e611f47d31a1ac3bbadf4e1` |
| R0 | `expanded_feature_manifest.json` | `93693a520151387f0c9fb514ada7324639387a7ae60bae5bba9d2a607a5beb14` |
| R0 | `expanded_preprocessing_state.json` | `a0180d9fc0436515f8a6f302727b4c0b030274cfbcce1a5ded7883568f05f47e` |
| R0 | `expanded_training_estimator_matrix_unscaled.csv` | `a8a2b08daa3c56ccda78d34f77c2a29b7ef7c9e00835e7ab6ac77412ec6f8588` |
| R0 | `expanded_training_row_index.csv` | `3062b1524e7599dcab32ae1dc419040e7f16f6730308e3a88b18c71293d4c427` |
| R0 | `expanded_training_staging.csv` | `3fced86922b533b0da2b42748d6c0b8afddef57b1281fe14880b11a446df21b6` |
| R0 | `final_test_policy.json` | `a3e5b7271b45b0ff997fde81d546bdd6d055a7177f44d31b41924beca8bb7e48` |
| R0 | `input_fingerprints.json` | `04caeba6a0872fac6fad3d7a8aaa3861dbc484228c6d3b8ddb3e24a1a1819428` |
| R0 | `population_diagnostics.json` | `a1d16291d10352aba4afced0d2d6cfc272c04acf1266f702b3ada1e866589d8c` |
| R0 | `summary.json` | `f2475571a32af96a6c802d90d5fa8f20fcfc2f7b0d9e27f2ce1cad1c88407b41` |
| R0.1 | `artifact_hashes.json` | `805350d8eb6aa9361f6745e8871996a226847ad989ebd77adbe8b000565a1047` |
| R0.1 | `documentation_reconciliation.json` | `cb5b7ec2e83ad36ed0e9be683023cee553928e9aa3f08768a81d872ab8107ed7` |
| R0.1 | `referenced_r0_artifacts.json` | `bb3ff4f51660aeba503d1bc5af18fae9847bf3d432eff4b7654007e986871198` |
| R0.1 | `summary.json` | `cc6e37cfb1c554f7da1bbd3d4a098a3d435fdffb59b83a1ee46c0d9f9a8bc1b0` |

All 10 committed R0/R0.1 files also matched their HEAD Git blob identities and their pre-cleanup SHA-256 fingerprints.

## Simplified contract

The checkpoint protects against accidental request drift, unauthorized endpoint/season/team/measure/parameter use, duplicates, retries, contradictory state, changed bytes, omissions, stage mixing, and premature protected-evidence access. It does not protect against a malicious repository owner, arbitrary rewriting by a locally unrestricted caller, a compromised operating system, or locally forged evidence. Git review, audit, and the future committed checkpoint are the practical authority boundary. SHA-256 establishes mutation and byte identity, not authorship or authorization.

The plan freezes 60 protected request identities and two missing non-protected dependency identities. It contains no executable recovery request. Exactly 250 rows remains an unresolved warning. The five restart states, transport rules, minimal future records, population rules, and separation of acquisition, reconciliation, readiness, and execution are explicit.

## Generated artifacts

The conditionally passed artifacts were verified before replacement:

| Superseded artifact | Bytes | SHA-256 |
|---|---:|---|
| `acquisition_plan.json` | 63,395 | `cfa24151162ae86c147d72fe2025bd95e1714e7335b2046628fd70262b3f54b7` |
| `artifact_hashes.json` | 447 | `4f5395ef83083f70da3a97964433909d027a97c95d25b0c097ee64fa67102c9c` |
| `summary.json` | 361 | `287b4e938d34c24530a103ccf710ba5139f269153c0d49787b8c107fef7d0c75` |

Two separate temporary corrected builds were byte-identical. Their bytes define the corrected official identities:

| Corrected artifact | Bytes | SHA-256 |
|---|---:|---|
| `acquisition_plan.json` | 64,477 | `fd0db91ad876df39d13829ac7e11b920a24e5b394c9f025115a7db46010056c4` |
| `artifact_hashes.json` | 447 | `7f3ddbc31665797b0c0acb24c49b9c47c2ddd0b31d92a1c98e8b39921e2ac347` |
| `summary.json` | 446 | `81f16d12563aa36d1770f172dea1c090e1ed37da5d4c15744f132a9f1352f19b` |

## Verification

- Focused R1S correction tests: 27 passed.
- Applicable R0/R0.1, acquisition, recovery, canonicalization, exact-250, incomplete-team, and protected-path regressions: 150 passed, 1 deselected. The deselected committed R0.1 test asserts its historical construction HEAD and correctly rejects the current authorized HEAD; all other selected behavior and evidence tests passed.
- `py_compile`: passed for the R1S module, CLI, and tests.
- `git diff --check`: passed.
- Source capability scan: no HTTP client, socket, estimator, fitting, prediction, metric, or model-serialization import/call exists in R1S.
- Corrected temporary-build determinism: two builds, byte-identical for all three files.
- Import-only canary count: one; passed immediately before the corrected official build.
- Corrected official build count: one; post-build verification was read-only.
- Populated and partial destination refusal: passed without altering existing bytes.
- Manifest inventory and self-exclusion: exactly three files are declared; `artifact_hashes.json` hashes `acquisition_plan.json` and `summary.json` and excludes itself to avoid recursion.

No network request was made. No real 2025–26 evidence path or payload was inspected. No estimator was loaded or fitted; no prediction, metric, final-test dataset, or model artifact was produced.
