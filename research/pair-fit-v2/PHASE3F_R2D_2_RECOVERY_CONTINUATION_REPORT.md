# Phase 3F-R2D.2 recovery continuation report

**PASS — recovery continuation complete; Indiana and Memphis dispositions assigned; ready for read-only audit**

## Repository and preflight

The required branch `research/pair-fit-v2`, HEAD `31daa913bffd47bf3ba31e77aaf0f5f896b588b5`, upstream divergence `0/0`, empty index, and initially clean worktree passed before editing or acquisition. The audited R2D.1 five-file namespace and manifest matched exactly. Original R2D remains failed and quarantined; its only body remained byte-identical; ordinals 2–8 had no prior evidence; Indiana and Memphis were unresolved; and no R2D.2 namespace existed. All seven continuation identities matched R2C.1 and R2D by ordinal, request ID, hash, team, measure, window, parameters, dates, and both distinct namespace lineage fields.

Indiana Early Base passed offline revalidation before network activity. The original body remains in place at `cache/phase3f-r2d/protected-recovery/01-1610612754-early-base/attempt-1-response.bin`: 58,235 bytes, raw SHA-256 `9726387a7e3f3f6cae9656cf74d1d4194a0e1f4593bc5bb15b016bae9a072593`, canonical SHA-256 `09f5970be9c4a9fdc2ece0cdeeeeef0bc04b8afb2c84f257781e0a81e44f7213`. Echo mismatches and all structural/pair errors were zero. The R2D.2 record references that body; it was not copied, moved, rewritten, deleted, promoted, or requested again.

## Official acquisition

Official invocation count: 1. Network attempts: exactly 7. Completed and verified: 7. Retries, redirects, failures, quarantines, and unauthorized requests: 0 each. Persisted monotonic gaps all passed; minimum: 1.000 seconds.

| Original ordinal | Identity | HTTP | Rows | Bytes | Raw SHA-256 | Canonical SHA-256 |
|---:|---|---:|---:|---:|---|---|
| 2 | Indiana Early Advanced | 200 | 227 | 60,788 | `4d87ebefae57b2b488f505fec83048be43b3d1aa08cf0ea347949b78a05603c0` | `c6f9b3fcef620a5fc5e23fb720d3d39e241f09add790ab0496cb54793f7244de` |
| 3 | Indiana Late Base | 200 | 149 | 38,182 | `3c4768cc66961f7300e1377ae1b8988cad4b73de1ebad622a39cd7c150f1864a` | `0e52d1c531579d720a5b26b06c845633f3c803aecec84235269f3cb4bfc8a8bb` |
| 4 | Indiana Late Advanced | 200 | 149 | 39,987 | `bd965785f6a806cac6a59f5de33cdfa3adc12181c059370e3ede9a92d049e373` | `3ac594198dbf7f5ba40657de5b5c95b5a2ee2eec70c1caf3747b4376d3224a1d` |
| 5 | Memphis Early Base | 200 | 145 | 37,461 | `aa73e8beee19e11b0bd09b857a0013059a5a18d6b657dd28016723d4afa05785` | `fdbdfe99af185f050d21e110716e127de8c29680a4175875218ab4110af043ab` |
| 6 | Memphis Early Advanced | 200 | 145 | 38,998 | `ae0df15e7c2710cd5ce0718998708980b66020f93abc7fba8a96af399fed4bfd` | `8cf44f1cd79c0d288523147a5a1a735d164f9c2ba34c735bd7614620df1e6b9d` |
| 7 | Memphis Late Base | 200 | 216 | 55,253 | `3adb3427f08d214511de4a89e9dc4b8010cc6dd9a979f39fdbb496363969b26e` | `105cdf63f1a9b8f96777dacc015262814a2c2a01aa3ffff1b94d715d769ffd63` |
| 8 | Memphis Late Advanced | 200 | 216 | 57,963 | `120098de83dba21e90333b6b953113121f6b51a131eb613b2ac6ccb2e5f95293` | `6a3377ac8e51147b695897f1c503c67d211a150ee5f235c80ffa211f379dfb3e` |

Every response had the ordered `Overall`, `Lineups` envelope, the expected measure schema, the corrected R2D.1 echo identity, unique valid canonical pairs, and valid required numeric fields. All Base-only, Advanced-only, malformed, duplicate, and same-player counts were zero. The one zero-possession Memphis pair was preserved.

## Population reconciliation and dispositions

| Team | Full season | Early | Late | Window union | Full-season found | Full-season only | Recovered only | Recovered POSS sum | Recovered `POSS >= 150` | Disposition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Indiana | 250 | 227 | 149 | 270 | 250 | 0 | 20 | 161 | 0 | Exclude whole team |
| Memphis | 250 | 145 | 216 | 300 | 250 | 0 | 50 | 962 | 0 | Exclude whole team |

For both teams, authenticated Base and Advanced keys were equal within each window and for the direct full-season response. The 20 valid Indiana recovered-only keys and 50 valid Memphis recovered-only keys directly prove that each direct 250-row full-season response is non-exhaustive. Under the frozen R2C.1 policy, both entire team-seasons are therefore excluded from the eventual final-test population. No recovered-only pair was selectively dropped or assigned a reconstructed target, and the 250 returned rows were not selectively retained after incompleteness was shown.

The evidence proves non-exhaustiveness of these two direct full-season responses. Whole-team exclusion is the frozen operational consequence. The checkpoint does not prove the global pair population, mathematical exhaustiveness, or that no additional omitted pairs exist.

## Preservation, artifacts, and verification

All 12 preserved R2B/R2C/R2D namespaces matched before and after. Their inventory SHA-256 values, in order, are `65271de8523330662115d55ee0d30adc29396e50bfe670fc060f135ef271dc93`, `f939d0a17c6e5cc1af9ab32a8555d7933dfc6123bac16f02dcbcc40a2c6c82a9`, `e7197ffe2a0c79e1ebd9cf35d0eece53f1343ac69e1ac6f8600abb9382ed6026`, `e40e4bd0bbc06a62f5881bb241d4a5d1df5c202309aac9291fc0de097eab5c33`, `8b350170f1faf7d8ef33e8ba0ce4075ee35e3535008636b26169b908cc9e624e`, `3e7c88f73b8c873b3dc99c3ad6cc7dc44158afdcd05984b2001d6620287e94a5`, `fb7d85802cadde1510e53a25a81ad8c7d7f5f813a5b1bd4086970859e1af2e31`, `fd9c05c0f5f58b51aaa4627eaa8d732d7209ad98c6925a063bc68abf40cc80b0`, `b2d0ed15ce272603ced88ac6efc084c8b4d34994b86ddab6c5868efb4764e7e6`, `a3c4e24e4003c43471d672c9ca281fc5271ada14dcbc7367a15a96774366c64e`, `3dc2212dc24a3d293b85841cfefc6348ef2fee62311c941d17bdffadb3b082bd`, and `0276ce181cedb4135384e41eff9aef8dc3c8ee3317a83a0537b5ebeae7413cb3`.

The ignored R2D.2 namespace contains exactly 39 files and 582,285 bytes. Its inventory SHA-256 is `c92c5717c5735ee3480c2d73117f93c3362922cef2b7d2a56d467733c406b8d7`. Exact inventory: eight root records (`authorization.json`, `preflight.json`, `pacing.json`, both team reconciliation files, `team-dispositions.json`, `summary.json`, and `artifact-hashes.json`); two execution records; one ordinal-1 offline verification; and four records (`attempt-1-start.json`, `attempt-1-response.bin`, `verification.json`, `attempt-1-outcome.json`) in each exact ordinal-2-through-8 request directory. The 38-entry manifest excludes itself; `artifact-hashes.json` is 6,934 bytes with SHA-256 `5415e554e989f29d8c0e868530aba47b6bcde2a3aaa19e606b30140c7c1ba380`.

Git-visible inventory is exactly this policy, this report, the implementation module, CLI, and focused test module. `.gitignore` was unchanged because `cache/` already ignores the R2D.2 namespace.

Focused R2D.2 tests: 15 passed. Directly relevant R2D.1 echo regressions: 34 passed. Directly relevant R2D acquisition regressions: 25 passed. Frozen R2C.1 disposition regressions: 8 passed. `py_compile` passed. The full historical phase modules contain obsolete committed-HEAD and worktree-allowlist assertions and were not treated as current checkpoint regressions. Deterministic cache-only replay passed with zero requests. Final `git diff --check`, ignore checks, prohibited-artifact checks, and final repository state are recorded at handoff.

No final-test dataset was built; no player profile was joined; no imputation or scaling was learned or applied; no estimator matrix was constructed; no target mean was calculated; no estimator was instantiated, fit, loaded, or serialized; and no prediction or model metric was generated. The narrowest justified next step is one focused read-only audit.
