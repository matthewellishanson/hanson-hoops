# Phase 3F-R2C Exact-250 Recovery Specification Policy

## Classification and authority boundary

**PASS — Phase 3F-R2C exact-250 recovery specification frozen; ready for read-only audit**

This checkpoint is specification-only. It authenticates one public season-boundary source, freezes eight possible future protected recovery identities, and defines pair-population reconciliation. It makes zero protected requests and zero recovery requests. It does not authorize protected pair acquisition, recovery execution, final-test construction, preprocessing, model fitting, prediction, metrics, serialization, databases, APIs, frontend work, or deployment.

The immediately preceding R2C attempt stopped correctly during preflight and created no deliverable, generated namespace, request identity, or working-tree change. That no-change outcome is preserved.

R2B remains permanently failed. Atlanta Base remains the quarantined R2B response accepted only through the audited R2B.1/R2B.2 offline continuation. R2B.2 retains its historical conditional procedural classification. R2B.2.1 remains the audit-cleared procedural closure and governs every later protected transport.

## Authoritative season boundary

The only permitted public request is one HTTP GET to `https://pr.nba.com/2025-26-nba-regular-season-schedule/`. The request must use exact URL equality, established non-secret research headers, `trust_env=False`, redirects disabled, a 30-second timeout, zero retries, and one attempt. No fallback, search, mirror, schedule API, substitute request, crawl, or attachment download is permitted.

The preserved response verifies that the 2025–26 NBA Regular Season began on `2025-10-21` and concluded on `2026-04-12`. These boundaries freeze two complementary windows:

| Window | DateFrom | DateTo |
|---|---|---|
| Early | `2025-10-21` | `2026-01-31` |
| Late | `2026-02-01` | `2026-04-12` |

Both windows are within the verified interval. The early window ends one calendar day before the late window begins, so they do not overlap and omit no date. Their combined 174 calendar days equal the verified interval's 174 calendar days.

## Frozen future identities

Every identity uses endpoint `TeamDashLineups` (`teamdashlineups`), season `2025-26`, season type `Regular Season`, `GroupQuantity=2`, `PerMode=Totals`, and the listed measure and window. Every other parameter is copied unchanged from the corresponding authenticated full-season R2B.2 request. Each identity binds both of its team's full-season Base and Advanced trigger identities and hashes, the corrected R2B.1 response-contract identity `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`, and the R2B.2.1 future protected-transport-contract file SHA-256 `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`.

| Ordinal | Request ID | Future output namespace |
|---:|---|---|
| 1 | `teamdashlineups:1610612754:2025-26:regular-season:2025-10-21:2026-01-31:base` | `cache/phase3f-r2c-protected-recovery/01-1610612754-early-base` |
| 2 | `teamdashlineups:1610612754:2025-26:regular-season:2025-10-21:2026-01-31:advanced` | `cache/phase3f-r2c-protected-recovery/02-1610612754-early-advanced` |
| 3 | `teamdashlineups:1610612754:2025-26:regular-season:2026-02-01:2026-04-12:base` | `cache/phase3f-r2c-protected-recovery/03-1610612754-late-base` |
| 4 | `teamdashlineups:1610612754:2025-26:regular-season:2026-02-01:2026-04-12:advanced` | `cache/phase3f-r2c-protected-recovery/04-1610612754-late-advanced` |
| 5 | `teamdashlineups:1610612763:2025-26:regular-season:2025-10-21:2026-01-31:base` | `cache/phase3f-r2c-protected-recovery/05-1610612763-early-base` |
| 6 | `teamdashlineups:1610612763:2025-26:regular-season:2025-10-21:2026-01-31:advanced` | `cache/phase3f-r2c-protected-recovery/06-1610612763-early-advanced` |
| 7 | `teamdashlineups:1610612763:2025-26:regular-season:2026-02-01:2026-04-12:base` | `cache/phase3f-r2c-protected-recovery/07-1610612763-late-base` |
| 8 | `teamdashlineups:1610612763:2025-26:regular-season:2026-02-01:2026-04-12:advanced` | `cache/phase3f-r2c-protected-recovery/08-1610612763-late-advanced` |

Any ninth identity, other team, season, season type, endpoint, group quantity, measure, date range, exploratory/control request, or identity lacking trigger hashes and governing-contract bindings must be rejected before transport.

## Future transport contract

A later, separately authorized acquisition checkpoint must enforce exact phase-local authorization consistency, exact namespace binding, executing-source pinning, sequential ordinal order, and a persisted monotonic gap of at least one full second from completion of one attempt to start of the next. It must use a 30-second timeout, disabled redirects, `trust_env=False`, zero automatic retries, one attempt per identity, immutable start and outcome records, and verification before promotion. Any failure is quarantined and stops the sequence immediately. Incomplete, conflicting, failed, or quarantined state is restart-blocking.

Neither this specification nor later acquisition completion authorizes final-test construction or model execution.

## Pair-population reconciliation

Each window requires authenticated Base and Advanced bundles and exact Base/Advanced canonical pair-key equality. A pair key consists of exactly two distinct positive player IDs sorted numerically. Player names are never identity fields. Malformed, duplicate, same-player, Base-only, and Advanced-only keys are rejected. Zero-possession rows are preserved.

For each team, the early and late key sets are unioned and compared with the authenticated full-season key set. The later report must include full-season, early, late, union, and shared counts; full-season-only and recovered-only keys; duplicate, malformed, Base-only, and Advanced-only counts; and whether every individual window response has fewer than 250 canonical rows.

Window possessions may be summed only as exposure metadata because the windows do not overlap. `OFF_RATING`, `DEF_RATING`, and `NET_RATING` must not be aggregated. No full-season target may be reconstructed, and no rating value may determine pair or team retention.

## Frozen dispositions

### `proven_non_exhaustive`

Apply when at least one valid recovered-only pair key exists. The full-season 250-row response is then proven incomplete. Do not retain only the returned 250 rows, drop only recovered pairs, or invent missing targets. Under the whole-team policy, exclusion from the eventual final-test population is required unless a separately authorized, definition-supported direct source supplies the omitted full-season targets. That exclusion is applied and verified later, never during R2C.

### `operationally_resolved_no_observed_omission`

Apply only when all four responses are authenticated and structurally valid; every individual window response has fewer than 250 canonical rows; Base and Advanced keys match within each window; the windows cover the complete verified interval; the union exactly equals the full-season pair-key set; recovered-only and full-season-only counts are zero; and duplicate, malformed, Base-only, and Advanced-only counts are zero.

This means no omission was observed under the predeclared complementary-window design and the team is operationally resolved for final-test readiness. It is not proof of universal or mathematical endpoint exhaustiveness. No report, readiness artifact, or eventual presentation may call the team “proven exhaustive.”

### `recovery_unresolved`

Apply whenever either preceding classification cannot be established, including a failed, quarantined, missing, incomplete, unauthenticated, invalid, conflicting, or exact-250 window response; Base/Advanced disagreement; full-season-only keys; or incomplete window coverage. The readiness gate cannot pass. Do not automatically retain or exclude the team; stop for a new audited decision.

## Stop condition

Indiana and Memphis remain unresolved. A PASS here permits only a separate read-only audit. No frozen recovery identity may be executed without a later explicit authorization.
