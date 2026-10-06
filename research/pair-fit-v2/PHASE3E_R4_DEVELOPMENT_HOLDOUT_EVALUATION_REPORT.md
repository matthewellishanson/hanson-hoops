# Phase 3E-R4 Development-Holdout Evaluation Report

**INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE**

Stage A: **passed**. Stage B: **failed**.

Ridge MAE was 7.344893 versus baseline 7.924122, an improvement of 0.579229. Ridge RMSE was 9.420378 versus baseline 9.992960, an improvement of 0.572582.

The primary Ridge values numerically clear both predeclared baseline-relative gates, but the execution is invalid because the first Stage B serialization incorrectly conditioned the two frozen missing-history materiality flags on the 100-row adequacy rule. The independent persisted-prediction audit found that the 38-row both-missing group must be marked material and adverse under the exact frozen ≥0.50 formulas while remaining descriptive-only. This implementation failure is not evidence for or against the model.

## Overall diagnostics

R²: 0.107290; prediction-minus-target bias: -0.077438; Spearman: 0.342059. Prediction SD: 3.036098; target SD: 9.970414; prediction/target SD ratio: 0.304511.

Possession-weighted Ridge MAE/RMSE: 6.134144/7.828373; baseline: 7.189354/8.914767.

Historical warnings — MAE extreme deterioration: false; RMSE above historical worst: false; absolute bias above historical maximum: false; fold-range warnings: r2. These warnings are non-decisional.

## Subgroups and concentration

- complete: n=2139, MAE=7.104021, RMSE=9.142723, bias=-0.718412, MAE difference from complete=0.000000, adequate=true, material=false, adverse lower-confidence difference=false.
- one_missing: n=523, MAE=8.128621, RMSE=10.338338, bias=2.064858, MAE difference from complete=1.024601, adequate=true, material=true, adverse lower-confidence difference=true.
- both_missing: n=38, MAE=10.116903, RMSE=11.368155, bias=6.517906, MAE difference from complete=3.012883, adequate=false, material=true, adverse lower-confidence difference=true. This group remains descriptive and cannot validate or invalidate its confidence tier.

Best descriptive team MAE: 1610612750 at 5.148470; worst: 1610612760 at 11.301656. Team and leave-one-team-out diagnostics are descriptive and noncausal; no team was removed and no model was refit.

Exact-250 diagnostic: applicable=false, rows=0, MAE=null, RMSE=null, bias=null. It uses retained 2024–25 rows only and cannot address excluded-team endpoint truncation.

Calibration lower-tail difference (target minus prediction): 0.992231 (underprediction); upper-tail difference: 1.356356 (underprediction). No calibrator or post-hoc adjustment was fitted.

Residual (target minus prediction) correlation/slope versus prediction: 0.025415/0.078854; versus possessions: 0.083707/0.001033.

## Scope and limitations

Charlotte (`1610612766`) and Philadelphia (`1610612755`) were excluded in full because their full-season endpoint responses were adjudicated non-exhaustive. This excludes approximately 9.82% of otherwise eligible rows and 6.33% of otherwise eligible possessions.

The target is contextual shared-court net rating, not a causal player-pair effect. Historical validation showed modest signal. Missing-history results remain uncertain, especially the 38-row both-missing group. Prediction compression is assessed through the SD ratio and calibration bins. Rows overlap substantially in players and pairs, so observations are not independent player experiments.

Exact-250 evidence is limited to retained rows and cannot rehabilitate excluded teams. No calibration, post-hoc tuning, alternative alpha, HGB comparison, row removal, team removal, or prediction transformation occurred.

The 2024–25 season is now spent as development evidence. The protected 2025–26 season remains untouched.
