# Phase 3E-R4.2 Correction-Only Reconciliation Report

1. Original R4: **INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE**
2. Reconciled scientific result: **VALID DEVELOPMENT-HOLDOUT PASS**

The unchanged persisted prediction vector numerically satisfies the frozen development-holdout PASS gates. This conclusion is accepted through a correction-only reconciliation under an explicit provenance waiver. The original R4 execution remains formally invalid.

## Why reconciliation was required

R4 was invalid because its first Stage B missing-history artifact omitted the required independent materiality and adversity flags, after which the defective Stage B artifacts and manifest were overwritten. The first stopped invocation, exact narrow preflight patch, immutable command log, original artifacts, and original test console output were not durably preserved. Exactly-one-fit/prediction lineage is strongly corroborated, not directly proven. No recovered evidence contradicts the production account. The user approved the bounded waiver so the unchanged persisted vector could be evaluated without any refit or regenerated prediction.

Before R4.1, an initial launcher command failed because it omitted the research project's `src` directory from `PYTHONPATH`. Python did not import the package and no reconciliation function began. The separately authorized R4.1 launch then imported successfully but stopped during Git-status verification because meaningful leading status whitespace was stripped. R4.1 never reached source-evidence verification or prediction-file opening. Its two-event ledger remains classified as `CORRECTION-ONLY RECONCILIATION FAILED — PRE-EVIDENCE GIT-STATUS PARSING FAILURE` and is preserved unchanged.

## Direct verification and prohibitions

Prediction: `modeling/phase3e-r4/predictions.csv` at `616d39c61408986bcae69f4d1b2a5747d8322929a2cf1b003fcbf683b70fe58b`; Stage A: `b209f2a60ff4651f097f4347ad78f8c76ec8aae8e4f1a67d1e874ef7c986ee52`; policy canonical/serialized: `6e0eff4b38c520ed5bd0c26100b2ddb4b911d6d3c9bb92fd7f016416b6211ad4` / `f5d1e8852693b74d4e82ae505e9d355526a3ddaedc7fbb7ffc7282db3f48ee48`; original invalid decision: `34cc815f739c4182d5c22c4ad3b4d8bd1cee08e3798ed368f7d13b71e2c6856a`; original invalid summary: `e7245c11a0364bd0810a0022b67a856939ceb90ea961d461e0fc22daead00178`; original report: `321eb2de5fe1cf6d2a41b2b24d28f6e80a148546f11ca599433a258fac472342`.

The 2,700-row, 11-column prediction file was verified as finite, uniquely keyed, numerically canonical, aligned position-for-position with the frozen R2 row index, limited to 2024-25, and free of Charlotte and Philadelphia. Its baseline is one constant historical-training-mean column. Static AST checks found no scikit-learn import and no estimator-operation call in the reconciliation module or CLI. The reconciliation opened no training estimator matrix, created no model artifact, and generated or changed no target, baseline, or prediction.

## Recomputed metrics

Ridge MAE 7.344893; baseline MAE 7.924122; improvement 0.579229. Ridge RMSE 9.420378; baseline RMSE 9.992960; improvement 0.572582.

R² 0.107290; prediction-minus-target bias -0.077438; Spearman 0.342059; prediction SD 3.036098; target SD 9.970414; SD ratio 0.304511.

Possession-weighted Ridge MAE/RMSE 6.134144/7.828373; baseline 7.189354/8.914767. Exact-250 is not applicable because zero retained rows are flagged.

## Missing history and diagnostics

- complete: n=2139, MAE=7.104021, RMSE=9.142723, bias=-0.718412, difference=0.000000, adequate=true, descriptive-only=false, material=false, adverse=false
- one_missing: n=523, MAE=8.128621, RMSE=10.338338, bias=2.064858, difference=1.024601, adequate=true, descriptive-only=false, material=true, adverse=true
- both_missing: n=38, MAE=10.116903, RMSE=11.368155, bias=6.517906, difference=3.012883, adequate=false, descriptive-only=true, material=true, adverse=true

All 28 team rows and 28 no-refit leave-one-team-out rows were retained. Best descriptive team MAE: 1610612750 at 5.148470; worst: 1610612760 at 11.301656.

All ten calibration bins contain 270 rows. Lower/upper target-minus-prediction differences are 0.992231/1.356356. Residual target-minus-prediction correlation/slope versus prediction: 0.025415/0.078854; versus possessions: 0.083707/0.001033.

Historical warnings: extreme MAE=false, RMSE above worst=false, absolute bias above historical maximum=false, fold-range flags={"bias": false, "prediction_std": false, "prediction_to_target_std_ratio": false, "r2": true, "spearman": false, "target_std": false}. These remain non-decisional under R3.

## Preservation, hashes, and verification

The original 13-file namespace fingerprint remained `2278916dde4d32614258152e03070a0e2586c5f3dd986f4356812bd3e46cb1d0` before and after reconciliation. Every byte length, SHA-256, and nanosecond modification timestamp matched. The original report hash and timestamp also matched. Manifest canonical hash: `97056c95b00a3bd27392ad8c39ef8f4906b300677386ab01d36aa2092f39edd0`.

The failed R4.1 namespace fingerprint remained `196246aef8df37398ee720e7aedcbe31b2d96ec3b4a00335939bc810af780b08` before and after R4.2. Its sole ledger remained `8e510eb6fc76faea6035d2b362a44bcca4bf0503632114c1537733f07a56f140` with identical bytes, creation time, and last-write time; no event was appended.

- `execution_events.jsonl`: `958b65b010f70c94de6aa4e9065a8b30f14c374236a321d40299613b4c750ef5`
- `reconciled_calibration_bins.csv`: `3a7469b63b47d64ecf651c0b418c62f3444d877a307921109f8c3be404cddfaa`
- `reconciled_historical_stability.json`: `df5b453565a60251125591c4f4b72817a222afb4be791f2ba9e6a43c68a24e6d`
- `reconciled_leave_one_team_out_metrics.csv`: `e014ec8a892d056803b76cf06f8abe7ec0749f1c2102c0e73fb6e264f734253b`
- `reconciled_missing_history_metrics.csv`: `1de19e3c283551f368b7f222d1dd891b1a4c1d8463db704594064f4f55d1e2fb`
- `reconciled_overall_metrics.json`: `123c4611489792101b6b5788bc6d959381001eadeffe3f8bc6e41e9fea4c76be`
- `reconciled_residual_diagnostics.json`: `bfbe604adcf20b534beb38cf848fca5468a2a62b69fd02553e773bcbc669a759`
- `reconciled_team_metrics.csv`: `86826f0c5b01812decd5d222582e1e3ed26198b5df329e200f0d4f1787d21910`
- `reconciliation_configuration.json`: `65e14964ee70defafbfbc3a9c6bb4a0a934bc99e3fadff36d5c7d97797b6c02d`
- `reconciliation_decision.json`: `d4e72b48e6cfabf9e302093a96dbc66f001ad934fab917a350956756501ae8e4`
- `source_evidence_verification.json`: `240e3fa5974980c94b982ecb7d5c149d947860c6c202fd49fc498155e59c9670`
- `verification_results.json`: `87d205db9fed0fa5edda3dec7eb1ea59b62f771970b63d89d992ed98b8196a28`

- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m pytest -q tests/test_phase3e_r4_2_reconciliation.py` — exit 0; passed=34; failed=0; deselected=0
- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m pytest -q tests/test_phase3e_r3_evaluation_policy.py -k "not exact_r4_output_inventory_schemas_and_mutation_allowlist"` — exit 0; passed=73; failed=0; deselected=1
- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m pytest -q tests/test_phase3e_r4_2_reconciliation.py::test_pinned_persisted_prediction_audit_without_model_code` — exit 0; passed=1; failed=0; deselected=0
- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m pytest -q tests/test_phase1a_pilot_audit.py::test_per_team_canonical_keys_are_unique_within_team tests/test_phase1b_architecture.py::test_stable_keys_make_league_season_type_team_and_unordered_pair_explicit` — exit 0; passed=2; failed=0; deselected=0
- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m py_compile src/pair_fit_v2/phase3e_r4_2_reconciliation.py src/pair_fit_v2/phase3e_r4_2_cli.py` — exit 0; passed=None; failed=None; deselected=0
- `git diff --check` — exit 0; passed=None; failed=None; deselected=0
- `git check-ignore -v --no-index modeling/phase3e-r4-2-reconciliation/ignore-probe` — exit 0; passed=None; failed=None; deselected=0
- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m pytest -q tests/test_phase3e_r4_2_reconciliation.py::test_static_model_prohibitions` — exit 0; passed=1; failed=0; deselected=0
- `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe -m pytest -q tests/test_phase3e_r4_2_reconciliation.py::test_network_and_protected_season_blocking` — exit 0; passed=1; failed=0; deselected=0

## Scope

The provenance limitation remains attached to this scientific result. It does not retroactively validate R4. The 2024-25 season remains spent as development evidence. The protected final-test season remains untouched, no network was accessed, and no production work began. Final-test execution must retain immutable commands, events, failures, original artifacts, manifests, and test output.
