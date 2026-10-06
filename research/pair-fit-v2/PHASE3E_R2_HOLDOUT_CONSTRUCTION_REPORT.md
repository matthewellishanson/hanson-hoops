# Phase 3E-R2: deterministic 2024-25 development-holdout construction

## Conclusion

**2024-25 holdout dataset constructed; ready for read-only audit**

The cache-only builder constructed 2,700 eligible observations from 28 retained 2024-25 Regular Season team-seasons. Charlotte and Philadelphia were excluded in full under the already-adjudicated non-exhaustive-team policy. No recovered pair was selectively restored, no date-window target was aggregated, and exact-250 was not used as an independent exclusion rule.

This checkpoint did not instantiate, fit, load, serialize, or run an estimator. It generated no prediction and calculated no model-performance, baseline, calibration, residual, or prediction-dispersion statistic. The 2024-25 `NET_RATING` field was retained unevaluated and checked only for presence and numeric finiteness. No 2025-26 path was opened.

## Start gate and immutable prerequisites

The gate passed before construction:

- branch: `research/pair-fit-v2`
- starting HEAD: `cb749f7c7841c87eb8ddc473c745981b9f67898a`
- upstream: `origin/research/pair-fit-v2` at the same commit
- starting tree: clean
- commit subject: `Philadelphia Evidence Report and Incomplete Team Season Policy completed`

The builder pins the Phase 3E-R1 policy (`9273090b5cc55faddf54f0e531ad3845d5f67e311fa806bf2a6e7d8db74a6c41`), R1 report (`f70011e3084eda35271a250106d232f2ce4422cee20f3b7f315f2d8167c73d9d`), ignored R1 result (`907f8474a052ad6358737c8941d6e7a059889d154214e44a5c62aa7b975b4bc5`), and Phase 3D selection decision (`5ef9663dff906fc04b3a31aec56c0dce1ce9fe4e7cdcc87dbaab95762ff02ca0`). The frozen Phase 3B `POSS >= 150` training table is pinned at `da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8`.

## Frozen population

Across all 30 cached team-seasons, the full-season Advanced responses contain 5,297 raw pair rows summing to 2,517,129 overlapping pair possessions. Charlotte and Philadelphia each contribute 250 raw rows. Their whole-team exclusions remove:

| Team | Raw rows | `POSS >= 150` rows | All-row summed POSS | Eligible summed POSS |
| --- | ---: | ---: | ---: | ---: |
| Charlotte Hornets | 250 | 143 | 82,532 | 75,088 |
| Philadelphia 76ers | 250 | 151 | 82,659 | 76,375 |
| Combined | 500 | 294 | 165,191 | 151,463 |

The remaining 28 teams contain 4,797 raw rows summing to 2,351,938 possessions. Applying `POSS >= 150` retains 2,700 rows summing to 2,241,098 possessions.

Relative to the full 30-team cached population, the retained 28 teams hold 90.5607% of raw rows and 93.4373% of raw summed possessions; the two exclusions remove 9.4393% and 6.5627%, respectively. Within the all-team threshold-eligible population, the retained rows are 90.1804% of rows and 93.6694% of summed possessions; the exclusions remove 9.8196% and 6.3306%.

## Thirty-team Base/Advanced reconciliation

`B-only/A-only` reports canonical pair-key differences. `D/M/S` is duplicate/malformed/same-player rows across Base plus Advanced. `T miss/nonfinite` and `P miss/nonpositive` are Advanced-field counts. All schemas, identities, and pair-key sets reconcile. The eight nonpositive possession rows are zero-possession audit rows; there are no negative possessions, and the threshold excludes them mechanically.

| Team ID | Team | Raw | Eligible | Summed POSS | B-only/A-only | D/M/S | T miss/nonfinite | P miss/nonpositive | Reconciled |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1610612737 | Atlanta Hawks | 169 | 113 | 86,990 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612738 | Boston Celtics | 141 | 70 | 81,355 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612739 | Cleveland Cavaliers | 164 | 92 | 84,554 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612740 | New Orleans Pelicans | 222 | 140 | 83,849 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612741 | Chicago Bulls | 190 | 100 | 87,276 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612742 | Dallas Mavericks | 216 | 122 | 84,336 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612743 | Denver Nuggets | 125 | 72 | 84,923 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612744 | Golden State Warriors | 183 | 110 | 84,005 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612745 | Houston Rockets | 131 | 90 | 83,354 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612746 | LA Clippers | 188 | 81 | 82,372 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612747 | Los Angeles Lakers | 208 | 97 | 82,933 | 0/0 | 0/0/0 | 0/0 | 0/1 | yes |
| 1610612748 | Miami Heat | 167 | 99 | 82,329 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612749 | Milwaukee Bucks | 192 | 82 | 83,976 | 0/0 | 0/0/0 | 0/0 | 0/2 | yes |
| 1610612750 | Minnesota Timberwolves | 125 | 63 | 82,613 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612751 | Brooklyn Nets | 204 | 136 | 81,689 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612752 | New York Knicks | 164 | 64 | 82,291 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612753 | Orlando Magic | 127 | 108 | 80,880 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612754 | Indiana Pacers | 162 | 74 | 85,474 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612755 | Philadelphia 76ers | 250 | 151 | 82,659 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes; excluded in full |
| 1610612756 | Phoenix Suns | 161 | 93 | 83,377 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612757 | Portland Trail Blazers | 140 | 88 | 83,663 | 0/0 | 0/0/0 | 0/0 | 0/1 | yes |
| 1610612758 | Sacramento Kings | 218 | 81 | 83,580 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612759 | San Antonio Spurs | 152 | 100 | 84,305 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612760 | Oklahoma City Thunder | 143 | 93 | 84,230 | 0/0 | 0/0/0 | 0/0 | 0/1 | yes |
| 1610612761 | Toronto Raptors | 206 | 124 | 84,980 | 0/0 | 0/0/0 | 0/0 | 0/1 | yes |
| 1610612762 | Utah Jazz | 172 | 120 | 85,146 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612763 | Memphis Grizzlies | 181 | 98 | 87,328 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes |
| 1610612764 | Washington Wizards | 208 | 113 | 85,517 | 0/0 | 0/0/0 | 0/0 | 0/1 | yes |
| 1610612765 | Detroit Pistons | 138 | 77 | 84,613 | 0/0 | 0/0/0 | 0/0 | 0/1 | yes |
| 1610612766 | Charlotte Hornets | 250 | 143 | 82,532 | 0/0 | 0/0/0 | 0/0 | 0/0 | yes; excluded in full |

Aggregate row-quality counts are duplicate 0, malformed 0, same-player 0, missing target 0, nonfinite target 0, missing possession 0, nonpositive possession 8, and negative possession 0.

## Prior-profile history

Every predictor source is strictly before 2024-25 and within the maximum three-season lookback. No target-season complete player profile is a predictor.

| History class | Eligible rows |
| --- | ---: |
| Complete | 2,139 |
| One player missing | 523 |
| Both players missing | 38 |

Across the 5,400 player slots, 4,801 have selected history and 599 are missing. Selected profile seasons/ages are identical distributions because age is measured from 2024-25: 2023-24/age 1 has 4,713 slots, 2022-23/age 2 has 69, and 2021-22/age 3 has 19.

Phase 3D player-slot median imputation, reproduced from the 27,001 training rows and 3,883 unique training player-season profiles, resolves missing slot inputs. No no-shot row requires second-stage symmetric-feature imputation in either the training population or the holdout. The diagnostic remains materialized so later audit can verify the zero requirement without inferring it.

## Exact 45-feature estimator contract

The pure estimator matrix contains exactly these ordered columns:

1. `pair_mean.AGE`
2. `pair_mean.FGM`
3. `pair_mean.FGA`
4. `pair_mean.FG3M`
5. `pair_mean.FG3A`
6. `pair_mean.FTM`
7. `pair_mean.FTA`
8. `pair_mean.OREB`
9. `pair_mean.DREB`
10. `pair_mean.AST`
11. `pair_mean.TOV`
12. `pair_mean.STL`
13. `pair_mean.BLK`
14. `pair_mean.BLKA`
15. `pair_mean.PF`
16. `pair_mean.PFD`
17. `pair_mean.PTS`
18. `pair_mean.PLUS_MINUS`
19. `pair_mean.effective_field_goal_pct`
20. `pair_mean.true_shooting_pct`
21. `pair_mean.three_point_attempt_rate`
22. `pair_mean.free_throw_rate`
23. `pair_absolute_difference.AGE`
24. `pair_absolute_difference.FGM`
25. `pair_absolute_difference.FGA`
26. `pair_absolute_difference.FG3M`
27. `pair_absolute_difference.FG3A`
28. `pair_absolute_difference.FTM`
29. `pair_absolute_difference.FTA`
30. `pair_absolute_difference.OREB`
31. `pair_absolute_difference.DREB`
32. `pair_absolute_difference.AST`
33. `pair_absolute_difference.TOV`
34. `pair_absolute_difference.STL`
35. `pair_absolute_difference.BLK`
36. `pair_absolute_difference.BLKA`
37. `pair_absolute_difference.PF`
38. `pair_absolute_difference.PFD`
39. `pair_absolute_difference.PTS`
40. `pair_absolute_difference.PLUS_MINUS`
41. `pair_absolute_difference.effective_field_goal_pct`
42. `pair_absolute_difference.true_shooting_pct`
43. `pair_absolute_difference.three_point_attempt_rate`
44. `pair_absolute_difference.free_throw_rate`
45. `pair_traded_history_count`

The estimator matrix header is byte-inspected by tests and contains only these 45 fields. It contains no IDs, target, `MIN`, `TOTAL_MIN`, `GP`, `POSS`, player-slot columns, usage/exposure field, weight, shot field, reliability field, target-period statistic, or audit/provenance value. Targets and exposures remain in separate staging and row-index artifacts.

All 2,700 rows were rebuilt after swapping Player 1 and Player 2. All 121,500 feature comparisons were unchanged; mismatch count is zero.

## Leakage-safe preprocessing

The builder reproduces the frozen Phase 3D order without an estimator: learn player-slot medians from unique training player-season profiles, impute both slots identically, construct symmetric features, learn any remaining symmetric-feature medians from training rows, then learn Ridge scaling from the training matrix. The preprocessing population is exclusively the 2014-15 through 2023-24 Phase 3B `POSS >= 150` table. Neither 2024-25 predictors nor its target contributes to a median, feature order, mean, or scale.

The matrix is therefore ready for a later separately authorized read-only evaluation runner. Alpha 3000 is recorded as frozen design metadata only; no Ridge object was constructed.

## Deterministic artifacts

Generated outputs are under Git-ignored `curated/phase3e-r2/`:

| Artifact | Rows × columns | SHA-256 |
| --- | ---: | --- |
| `holdout_staging.csv` | 2,700 × 84 | `2a281f379258f0f14a59395d656484fe265443217da028e7e2733ae698ffac58` |
| `holdout_row_index.csv` | 2,700 × 15 | `2ba178639cd2f1c4dcba5407a1b040bd993d7cdee31b045a33c6de0583d0304b` |
| `holdout_estimator_matrix.csv` | 2,700 × 45 | `eea1e78f427877c3c173e2607bbe2a42d87d39c7ea3a8e41e2277d95cf44ca25` |
| `estimator_feature_manifest.json` | — | `4cb3e75bc1c37a56063147b75fdc5def582ad65a704ce282afa96a7897ad4b1c` |
| `population_diagnostics.json` | — | `6c0b136f93b3ec2c24d9ee70cb930160d45af5b10a27c32df6b65baafd2558ed` |
| `preprocessing_state.json` | — | `05730ce4ecd8944e236e791faecf242174272692794477e39d1523f9475d7da3` |
| `input_fingerprints.json` | — | `11e00e15ac188a5d7d243b484192fe4604d37d21e06b482fb724c81683f45918` |
| `artifact_hashes.json` | — | `50247fad8a51d314a6cf3933a5341ee8327fca292a06ea95b1c5816bcc3992f2` |

The artifact-manifest canonical content hash is `3c4cc2685b17eb594e3450129b46e7a23a7a2b038d256b70fc813d5431a7d5c6`; summary canonical content hash is `fc6c5a30fcd62b180fc86454ef3e80886644d1d3ae896ed9d14142584696a96c`. The builder checked all 129 referenced cache/manifest/metadata files before and after construction and found no fingerprint change.

Two independent builds were required to contain the same nine filenames with byte-identical contents. Focused Phase 3E-R2 tests passed 6/6. Applicable Phase 3B, 3C, and 3D curation/feature-contract regressions passed 47/47. Pytest emitted only its existing inability to write `.pytest_cache`; test execution and generated artifacts were unaffected.

## Reproduction

From `research/pair-fit-v2`, with the repository virtual environment available:

```powershell
$env:PYTHONPATH = 'src'
..\..\.venv\Scripts\python.exe -m pair_fit_v2.phase3e_r2_cli --project-root . --output-dir curated\phase3e-r2
```

The CLI is cache-only and wraps the full build in a socket network prohibition. It rejects any path bearing the protected final-test season before file access.
