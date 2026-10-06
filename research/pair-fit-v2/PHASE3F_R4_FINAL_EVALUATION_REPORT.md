# Phase 3F-R4 final Ridge evaluation report

## FINAL SCIENTIFIC PASS

The frozen Ridge cleared both predeclared baseline-relative gates on the untouched final-test population.

The mechanical result was not overridden by diagnostics, subgroup findings, or judgment.

## Execution integrity

- Branch `research/pair-fit-v2` at `da6e7c1d1e7c94a8dbf7a4b4c658b2a55695862d`; upstream divergence `0/0`; index clean; Stage 1 began with a clean worktree.
- Import canary: `PHASE3F_R4_IMPORT_CANARY_OK` using the repository virtual environment and explicit project `src` PYTHONPATH.
- Official invocation count: `1`; pre-execution integrity: `passed`; Ridge fit count: `1`; prediction call count: `1`.
- Dimensions: `29701 x 45` training and `2811 x 45` final test; 28 retained teams.
- Indiana `1610612754` and Memphis `1610612763` remained fully excluded.
- Network, alternate estimator, tuning, calibration fitting, model serialization, commit, and push: none.

## Primary result

| Metric | Ridge | Baseline | Baseline minus Ridge |
| --- | ---: | ---: | ---: |
| MAE | 7.789167 | 8.405892 | 0.616725 |
| RMSE | 9.948956 | 10.494412 | 0.545456 |

R-squared was `0.100443`, prediction-minus-target bias `0.360195`, Spearman `0.336381`, prediction SD `2.996897`, target SD `10.489702`, and SD ratio `0.285699`.
Possession-weighted Ridge MAE/RMSE were `6.421191` / `8.203794`; baseline values were `7.560039` / `9.283360`.

## Diagnostics

- `complete`: 2154 rows, MAE `7.670757`, RMSE `9.853432`, bias `-0.020161`, MAE delta from complete `0.000000`.
- `one_missing`: 597 rows, MAE `8.129103`, RMSE `10.246028`, bias `1.428850`, MAE delta from complete `0.458346`.
- `both_missing`: 60 rows, MAE `8.657720`, RMSE `10.353582`, bias `3.381843`, MAE delta from complete `0.986963`.
- Best/worst retained-team MAE: `1610612739` at `5.553361` / `1610612759` at `10.993803`.
- Calibration lower/upper target-minus-prediction differences: `-1.157037` / `1.487429`.
- Historical warning flags: `none`; outside historical fold ranges: `target_std, prediction_to_target_std_ratio`.
- Residual diagnostics are retained in `residual_diagnostics.json`; exact-250 diagnostic applicable: `false`.

## Evidence and limitation

The ignored write-once namespace contains 14 artifacts. Its nonrecursive payload manifest canonical SHA-256 is `7f8236ff4010e62f9fb1ab34a3c3707f90a1cfb0aa11bf1efdea49313b7886b7`. Independent persisted-prediction reproduction is a required read-only post-execution check and is reported at handoff.

The result is a one-time frozen scientific checkpoint, not deployment authorization. The historical 2024-25 development result carries its previously disclosed provenance waiver; the present final execution does not add a new provenance limitation.

The narrowest justified next step is one final read-only scientific audit. Packaging and deployment remain unauthorized.
