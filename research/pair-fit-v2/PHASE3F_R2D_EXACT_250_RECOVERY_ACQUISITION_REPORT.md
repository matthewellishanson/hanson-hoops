FAIL — authorized recovery acquisition or reconciliation failed

# Phase 3F-R2D Exact-250 Recovery Acquisition Report

## 1. Git state and inventory

- Branch: `research/pair-fit-v2`
- Starting and final committed HEAD: `f7f72eda75fecfeab044b6f0315f263b71af657d`
- Upstream: `0` ahead / `0` behind
- Index: clean; nothing staged
- Worktree: exactly the authorized Git-visible R2D inventory:
  - modified `.gitignore` only to ignore `/planning/phase3f-r2d/` (the repository already ignores all of `cache/`);
  - `PHASE3F_R2D_EXACT_250_RECOVERY_ACQUISITION_POLICY.md`;
  - `PHASE3F_R2D_EXACT_250_RECOVERY_ACQUISITION_REPORT.md`;
  - `src/pair_fit_v2/phase3f_r2d_recovery_acquisition.py`;
  - `src/pair_fit_v2/phase3f_r2d_cli.py`;
  - `tests/test_phase3f_r2d_recovery_acquisition.py`.
- No commit or push occurred.

## 2. Authorization and executing-source identity

The immutable authorization is `planning/phase3f-r2d/recovery_authorization.json`:

- bytes: `35,696`
- SHA-256: `5bbf18388958f8dcdc9cd61062391a3a4c47f9e357ff463e4270802bf6e1eb3e`
- corrected plan: `131,714` bytes, SHA-256 `eeb762fa61608b7920ef418175c8c26d54bd7436f7fa5bbbca9982d089330c07`
- response-contract identity: `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`
- future transport contract: `4,074` bytes, SHA-256 `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`
- pinned acquisition source: `68,430` bytes, SHA-256 `c5858fd5c9ca28cda4a60251cb1d77f1dba6a1433cb698a429f93e9f2994e901`
- pinned CLI: `1,907` bytes, SHA-256 `019174917199ffa56bc50cb4365894c4cd47c4a3c0f4d767dc070fb829d3a187`
- Python: `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe`, 274,424 bytes, SHA-256 `0b471133e110cfb53a061cad528ce8e517d7b9ac41a0a396c39ad795a487fc14`
- working directory: `C:\Users\mehan\code\hanson-hoops\research\pair-fit-v2`
- required `PYTHONPATH`: `src`

The official process rehashed and accepted the pinned source, CLI, executable, authorization, working directory, environment, namespaces, contracts, and exact eight-request allowlist before transport.

## 3. Invocation counts

- Explicit import-only canary processes: `1`
- Official invocation processes: `1`
- Official invocation start: `2026-10-03T05:36:41.080669Z`
- Official invocation end: `2026-10-03T05:36:49.682720Z`
- Exit code: `1`
- Persisted stdout: empty
- Persisted stderr: `RecoveryError: returned parameter mismatch: DateFrom`
- Second launch or retry: `0`

## 4. Request count

- Frozen/authorized identities: `8`
- Transport attempts made: `1`
- Responses received: `1`
- Unauthorized requests: `0`
- Automatic retries: `0`
- Redirects followed: `0`

The phase stopped immediately after quarantining ordinal 1. Ordinals 2–8 remain `not_started`.

## 5. Per-request results

| Ordinal | Team | Window | Measure | HTTP | Redirects / retries | Rows | Bytes | Raw SHA-256 | Canonical SHA-256 | Request disposition | Gap before next |
|---:|---|---|---|---:|---|---:|---:|---|---|---|---|
| 1 | Indiana | early | Base | 200 | 0 / 0 | 227 | 58,235 | `9726387a7e3f3f6cae9656cf74d1d4194a0e1f4593bc5bb15b016bae9a072593` | `09f5970be9c4a9fdc2ece0cdeeeeef0bc04b8afb2c84f257781e0a81e44f7213` (independent read-only calculation) | `failed_or_quarantined` | no next request |
| 2 | Indiana | early | Advanced | — | — | — | — | — | — | `not_started` | — |
| 3 | Indiana | late | Base | — | — | — | — | — | — | `not_started` | — |
| 4 | Indiana | late | Advanced | — | — | — | — | — | — | `not_started` | — |
| 5 | Memphis | early | Base | — | — | — | — | — | — | `not_started` | — |
| 6 | Memphis | early | Advanced | — | — | — | — | — | — | `not_started` | — |
| 7 | Memphis | late | Base | — | — | — | — | — | — | `not_started` | — |
| 8 | Memphis | late | Advanced | — | — | — | — | — | — | `not_started` | — |

Ordinal 1 was the first request, so its pacing fields correctly record no preceding completion and `first_request_not_applicable`. No request-to-request pacing interval exists because the fail-stop prevented request 2.

## 6. Failure and restart state

The exact authorized request used ISO inputs `DateFrom=2025-10-21` and `DateTo=2026-01-31`. The HTTP 200 response echoed `DateFrom=10/21/2025` and `DateTo=01/31/2026`. The production authenticator required exact returned-parameter string equality and therefore rejected the response at `DateFrom`.

Independent read-only inspection showed that the body otherwise satisfies the corrected R2B.1 structural contract: strict JSON, result-set order `Overall` then `Lineups`, one Overall row, 227 Lineups rows, exact Base schemas, and a non-250 row count. This does not reverse the official authentication failure.

Immutable failure evidence:

- attempt start: 748 bytes, SHA-256 `9f81e72bb1a101e88775143e3b50be00a533dcef2fc9da91801651fd192c28e1`
- raw response: 58,235 bytes, SHA-256 `9726387a7e3f3f6cae9656cf74d1d4194a0e1f4593bc5bb15b016bae9a072593`
- attempt outcome: 678 bytes, SHA-256 `f9fad8a8dc790ceec0f89d32cad299d322f98c2bd458dddacbd2e8a2b0de79b4`
- quarantine: 417 bytes, SHA-256 `81abba7da00f63d2b8eeabb225b604c7d6672881fc3b30d3014d0b571e250199`
- invocation start: 1,955 bytes, SHA-256 `59a3adc11f6f2b63fd70005c90fef7879d146b8f24f2519ea0c431a2d9ee3b4b`
- invocation outcome: 244 bytes, SHA-256 `54b1aab08150e9da465616e3d6313502efdf59f54be56372eac45320cb4675aa`

The restart state for ordinal 1 is `failed_or_quarantined`. The immutable invocation-start record makes a second official launch prohibited. No repair or rerun was attempted.

## 7. Full-season trigger reauthentication

Before transport, the four permitted full-season records reauthenticated and parsed at 250 rows each:

- Indiana Base, ordinal 35: 65,800 bytes; raw `d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3`; canonical `0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5`.
- Indiana Advanced, ordinal 36: 67,740 bytes; raw `45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee`; canonical `605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120`.
- Memphis Base, ordinal 53: 66,452 bytes; raw `540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29`; canonical `b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc`.
- Memphis Advanced, ordinal 54: 68,221 bytes; raw `d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6`; canonical `2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3`.

No other historical protected response body was opened or parsed by the production implementation.

## 8. Indiana reconciliation

Not performed. The mandatory gate requiring all four Indiana recovery responses to be `completed_verified` was not met. Indiana early Base is quarantined; Indiana early Advanced and both late responses are absent.

## 9. Memphis reconciliation

Not performed. All four Memphis recovery responses remain absent because the phase stopped on Indiana request 1.

## 10. Pair-key differences

- Indiana recovered-only keys: not computed
- Indiana full-season-only keys: not computed
- Memphis recovered-only keys: not computed
- Memphis full-season-only keys: not computed

The phase did not partially construct either team's recovery union.

## 11. Exposure diagnostics

Not computed. No recovered-only population exists, and the failed request was Base rather than Advanced.

## 12. Frozen team dispositions

- Indiana Pacers: `recovery_unresolved` because a required recovery response is `failed_or_quarantined`, three are missing, and no complete reconciliation record can satisfy the exact R2C.1 schema.
- Memphis Grizzlies: `recovery_unresolved` because all four required recovery responses are missing following the authorized fail-stop.

No favorable disposition artifact was generated. These are the frozen classifier's mandatory fallback outcomes for failed or missing evidence, not completed population-reconciliation results.

## 13. Readiness effect

Indiana and Memphis remain unresolved. The applicable final-test readiness gate remains blocked. No `readiness_effect.json` was created because acquisition did not complete. This phase does not declare the full final-test pipeline ready and does not authorize execution.

## 14. Generated artifacts and hashes

The only planning artifact is the immutable authorization listed in section 2. The protected evidence artifacts are the six files listed in section 6.

The seven post-reconciliation result files were correctly not created:

- `request_ledger.json`
- `response_fingerprints.json`
- `team_reconciliation.json`
- `team_dispositions.json`
- `readiness_effect.json`
- `artifact_hashes.json`
- `summary.json`

There is no manifest because the exact eight-response evidence gate was not met.

## 15. Tests and checks

- Pre-transport R2D suite: `36 passed`
- Post-failure R2D suite: `36 passed`
- `py_compile`: passed before transport and after failure
- `git diff --check`: passed before transport and after failure (line-ending notice only)
- Related historical suites: `220 passed`, with 16 expected phase-local failures because those legacy builders require their older committed HEADs or their old dirty-file inventory. Historical files were not modified to suppress these failures.
- Import-only canary: one process, passed
- Independent response hash, canonical hash, structural envelope, row count, restart-state, and preservation replay: passed

Synthetic tests prohibited network and wrote only pytest temporary paths, never the official namespaces.

## 16. Historical preservation fingerprints

The same before/after fingerprints were reproduced after failure:

| Namespace | Files | Bytes | Inventory SHA-256 |
|---|---:|---:|---|
| `planning/phase3f-r2b` | 2 | 72,591 | `65271de8523330662115d55ee0d30adc29396e50bfe670fc060f135ef271dc93` |
| `planning/phase3f-r2b.1` | 5 | 107,046 | `f939d0a17c6e5cc1af9ab32a8555d7933dfc6123bac16f02dcbcc40a2c6c82a9` |
| `planning/phase3f-r2b.2` | 14 | 970,695 | `e7197ffe2a0c79e1ebd9cf35d0eece53f1343ac69e1ac6f8600abb9382ed6026` |
| `planning/phase3f-r2b.2.1` | 5 | 35,479 | `e40e4bd0bbc06a62f5881bb241d4a5d1df5c202309aac9291fc0de097eab5c33` |
| `cache/phase3f-r2b` | 4 | 53,126 | `8b350170f1faf7d8ef33e8ba0ce4075ee35e3535008636b26169b908cc9e624e` |
| `cache/phase3f-r2b.2` | 295 | 6,263,873 | `3e7c88f73b8c873b3dc99c3ad6cc7dc44158afdcd05984b2001d6620287e94a5` |
| `planning/phase3f-r2c` | 3 | 122,926 | `fb7d85802cadde1510e53a25a81ad8c7d7f5f813a5b1bd4086970859e1af2e31` |
| `cache/phase3f-r2c-public-source` | 5 | 128,578 | `fd9c05c0f5f58b51aaa4627eaa8d732d7209ad98c6925a063bc68abf40cc80b0` |
| `planning/phase3f-r2c.1` | 3 | 133,031 | `b2d0ed15ce272603ced88ac6efc084c8b4d34994b86ddab6c5868efb4764e7e6` |

Historical Git-visible fingerprints also match the immutable authorization. No R2B, R2B.1, R2B.2, R2B.2.1, R2C, or R2C.1 artifact changed.

## 17. Unauthorized-request confirmation

Exactly one of the eight authorized identities was attempted. No ninth request, other team, season, endpoint, date window, measure, control request, retry, proxy request, fallback request, or public-source reacquisition occurred.

## 18. Rating and target confirmation

No rating aggregation or possession weighting occurred. No `OFF_RATING`, `DEF_RATING`, or `NET_RATING` was combined. No full-season rating or recovered-only target was reconstructed.

## 19. Dataset and model confirmation

No final-test population or dataset was constructed. No prior-profile join, preprocessing, estimator fitting, prediction, metric, classification, or model serialization occurred.

## 20. Final Git and evidence state

HEAD remains `f7f72eda75fecfeab044b6f0315f263b71af657d`; upstream remains `0/0`; the index remains clean. The only Git-visible changes are the exact six authorized R2D deliverables. The ignored planning namespace contains only the immutable authorization. The ignored protected namespace contains the immutable invocation records and the ordinal-1 start, raw body, failed outcome, and quarantine record. That evidence was unchanged during post-failure verification.

## 21. Narrowest justified next step

A separate read-only audit of this failed R2D checkpoint is the only permissible next step. The audit may assess whether exact echoed-date string equality was a specification/implementation defect, but no repair, new authorization, retry, second official launch, additional acquisition, final-test construction, or model execution is authorized here.
