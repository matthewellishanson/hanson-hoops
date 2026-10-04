# Phase 3F-R3.1 reproducibility correction report

**PASS — R3.1 reproducibility correction complete; ready for narrow read-only audit**

## Scope and repository state

This is a narrow non-scientific correction to Phase 3F-R3. Mandatory preflight passed on branch `research/pair-fit-v2` at exact HEAD `6dc1234fd6dc2643af8718f77ca5651eb5c6594a`, upstream divergence `0/0`, with an empty index and exactly the five expected untracked R3 deliverables. The existing `/curated/` rule already ignores `curated/phase3f-r3.1/`, so `.gitignore` required no change. No commit or push occurred.

The original write-once `curated/phase3f-r3/` namespace remains historical evidence. Its exact 12-file inventory was fingerprinted before correction by relative path, byte count, SHA-256, and last-write timestamp. The same inventory and all four identity fields matched after correction. The original `summary.json` remains 2,539 bytes with SHA-256 `0d262e096e3fc3de9a8ca8b5cb6d84f7ea1a608eca662289cdf43310b1b8b2f7`; it is historically valid as the original production summary and is superseded only for deterministic composite evidence.

## Corrections

The CLI change removes one surplus line feed at EOF from `src/pair_fit_v2/phase3f_r3_cli.py`. No executable statement or CLI behavior changed.

The original summary serialized `repository.construction_time_changes` from live `git status`. The production build ran before the human readiness report existed and recorded four files; later builds saw the materialized report and recorded five. The corrected builder serializes the contract-defined identity of all five intended R3 Git-visible deliverables:

1. `PHASE3F_R3_FINAL_TEST_READINESS_POLICY.md`
2. `PHASE3F_R3_FINAL_TEST_READINESS_REPORT.md`
3. `src/pair_fit_v2/phase3f_r3_final_test_readiness.py`
4. `src/pair_fit_v2/phase3f_r3_cli.py`
5. `tests/test_phase3f_r3_final_test_readiness.py`

This declaration is separate from live Git-state validation. The builder still rejects a dirty index, unrelated or prohibited paths, and missing core construction files; the final inventory validator requires the exact five R3 deliverables plus this one R3.1 report. A focused regression simulates both pre-report and post-report status and requires identical serialized repository identity.

## Authoritative corrected composite

The authoritative corrected R3 evidence is exactly 12 logical artifacts: the 11 non-summary artifacts in `curated/phase3f-r3/`, referenced in place and not copied, plus `curated/phase3f-r3.1/corrected_summary.json`. The historical original summary is preserved but is not the authoritative deterministic summary for future execution.

The R3.1 namespace contains only `correction.json`, `referenced_r3_artifacts.json`, `corrected_summary.json`, `artifact_hashes.json`, and `summary.json`. Its manifest hashes the first three payloads under an explicit nonrecursive rule and excludes itself and `summary.json`.

Two complete corrected R3 builds were produced in disposable directories. All 12 files matched byte-for-byte between builds. Each build's 11 non-summary files matched the referenced originals, and each corrected `summary.json` matched `corrected_summary.json`. The disposable directories were removed. Corrected summary SHA-256: `0a3867a054ac872fe585382e7bd8fed29fda4ed2cbc4f72d6b8aad1734f76f9e`.

## Scientific and execution boundary

The authoritative composite retains 28 teams; full Indiana and Memphis exclusion; 5,403 all-team raw rows; 4,903 retained-team raw rows; 2,811 eligible rows; 2,250,488 eligible possessions; history counts 2,154 / 597 / 60; 717 missing player slots; source profiles 4,859 / 38 / 8; matrix dimensions 2,811 × 45; 126,495 symmetry checks with zero mismatches; preprocessing identity `a0180d9fc0436515f8a6f302727b4c0b030274cfbcce1a5ded7883568f05f47e`; and all six passed readiness gates. Read-only audit clearance and one-time final-model execution authorization both remain false.

Network access, evidence acquisition, population reconstruction, target or feature mutation, preprocessing refit, estimator import or construction, fitting, prediction, metric calculation, and model serialization were all zero. The only permitted next step is a narrow read-only audit. Even a successful audit does not authorize final Ridge execution.
