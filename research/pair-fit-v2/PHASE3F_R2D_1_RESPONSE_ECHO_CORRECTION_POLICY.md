# Phase 3F-R2D.1 Response-Echo Correction Policy

## Scope and permanent status

Phase 3F-R2D.1 is an offline, specification-only checkpoint. It corrects the narrow TeamDashLineups returned-parameter comparison used by a future acquisition continuation, evaluates the one quarantined Indiana Early Base response without changing it, and freezes a continuation design. It has no network, recovery-execution, population-reconciliation, final-test, prior-profile, preprocessing, estimator, prediction, metric, serialization, database, API, frontend, presentation, deployment, commit, or push authority.

The original Phase 3F-R2D classification remains `FAIL — authorized recovery acquisition or reconciliation failed`. Its one response remains `failed_or_quarantined`; its authorization, source, CLI, policy, report, tests, invocation records, attempt record, outcome, quarantine, stdout, stderr, and body remain immutable. Indiana and Memphis remain `recovery_unresolved`. A passing R2D.1 assessment establishes only `eligible_for_future_offline_revalidation_under_corrected_echo_contract`; it does not create completed verification, promote or copy the body, or use it in reconciliation.

## Frozen inputs and preflight

The required branch is `research/pair-fit-v2`, committed HEAD is `f7f72eda75fecfeab044b6f0315f263b71af657d`, upstream is `0/0`, and the index is empty. Before editing, the only Git-visible state was the expected R2D `.gitignore` modification and five untracked R2D deliverables. The R2D.1 builder reauthenticates:

- R2C.1 corrected plan `planning/phase3f-r2c.1/corrected_recovery_plan.json`, 131,714 bytes, SHA-256 `eeb762fa61608b7920ef418175c8c26d54bd7436f7fa5bbbca9982d089330c07`;
- R2B.1 contract identity `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`;
- R2B.2.1 transport contract, 4,074 bytes, SHA-256 `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234`;
- original R2D authorization, 35,696 bytes, SHA-256 `5bbf18388958f8dcdc9cd61062391a3a4c47f9e357ff463e4270802bf6e1eb3e`;
- the exact R2D source, CLI, policy, report, tests, invocation records, attempt start, outcome, quarantine, and response;
- every historical namespace and Git-visible file fingerprint pinned by the R2D authorization, including R2B-family, R2C, R2C.1, and public-source evidence.

Other protected bodies are read only as opaque bytes for SHA-256 preservation. They are never parsed. The only protected response parsed by R2D.1 is the pinned Indiana Early Base body.

Exactly one R2D attempt must exist. Original ordinals 2–8 must have no directory and therefore no start, response, outcome, verification, or quarantine record. The R2D planning namespace must contain only `recovery_authorization.json`; reconciliation, disposition, readiness, summary, and manifest outputs must remain absent. Any discrepancy fails closed before R2D.1 output is written.

## Pinned quarantined response

The single body is `cache/phase3f-r2d/protected-recovery/01-1610612754-early-base/attempt-1-response.bin`. Its frozen identity is:

- Indiana Pacers Early Base, Team ID `1610612754`;
- sent dates `2025-10-21` through `2026-01-31`;
- HTTP 200, no redirect, no retry;
- 58,235 bytes;
- raw SHA-256 `9726387a7e3f3f6cae9656cf74d1d4194a0e1f4593bc5bb15b016bae9a072593`;
- canonical JSON SHA-256 `09f5970be9c4a9fdc2ece0cdeeeeef0bc04b8afb2c84f257781e0a81e44f7213`;
- last-write timestamp `2026-10-03T05:36:49.6738827Z`;
- result-set order `Overall`, `Lineups`; 57 columns and one row, then 56 columns and 227 rows;
- 227 unique canonical pairs and zero row-width, duplicate, malformed, same-player, or invalid-ID errors.

The body, its path, timestamp, hashes, failed outcome, and quarantine must match exactly.

## Sole response-echo comparator

`compare_response_echo` is the only authoritative echo comparator. Both public verification entry points delegate directly to it. A future continuation must use it for offline revalidation, each initial response verification, completed-state replay, restart classification, and final evidence reconciliation. Importing or calling the failed R2D comparator, reverting to literal date comparison, or adding an alternate comparator is prohibited.

The comparator evaluates every one of the 25 expected fields in a frozen deterministic order, evaluates every returned extra, and collects all missing fields and mismatches before returning. It returns raw sent and echoed values, the rule, applicable normalized values, equivalence, deterministic reason code, missing fields, extras and their permitted status, mismatch count, and overall pass/fail. It does not perform fuzzy matching.

### Date fields

Special parsing applies only to `DateFrom` and `DateTo`. The sent value must be a string matching exact ISO `YYYY-MM-DD`. An echo may match only exact ISO `YYYY-MM-DD` or exact US numeric `MM/DD/YYYY`. Parsing uses explicit formats, validates the calendar date, and requires identical year, month, and day. Both values are recorded raw and normalized to ISO.

Missing, null, empty, padded, non-string, invalid, shortened, timestamped, timezone-suffixed, locale-text, alternate-separator, extra-character, or different-day values fail. No other field receives date parsing.

### `PORound`

`PORound` has one field-specific historical sentinel equivalence: sent raw `""` may equal echoed JSON integer `0` only when `type(echoed) is int`. Boolean false, string `"0"`, null, float `0.0`, negative float zero, any nonzero integer, missing, array, object, or whitespace fails. Exact type-and-value equality is also allowed for a valid frozen `PORound` value. This rule cannot apply to another field.

The basis is the repository-local Phase 1D endpoint finding that TeamDashLineups consistently echoed an empty `PORound` sentinel as numeric zero. R2D.1 is stricter than the old Phase 1D helper because it does not accept string zero.

### Established representations and extras

The legacy R2D comparison normalized a JSON null to an empty string and otherwise compared string representations. R2D.1 preserves only the observed, named behaviors:

- `GroupQuantity`, `LastNGames`, `Month`, `OpponentTeamID`, `Period`, and `TeamID`: exact frozen nonnegative decimal string or the same JSON integer; Boolean and float forms fail;
- `GameID`, `GameSegment`, `Location`, `Outcome`, `SeasonSegment`, `ShotClockRange`, `VsConference`, and `VsDivision`: sent empty string may echo as exact empty string or JSON null;
- `LeagueID`, `MeasureType`, `PaceAdjust`, `PerMode`, `PlusMinus`, `Rank`, `Season`, and `SeasonType`: exact string identity only.

The old R2D expected-field loop did not reject extra returned fields and therefore accepted the observed `ISTRound=null`. R2D.1 narrows that behavior: the sole permitted extra is exactly `ISTRound` with JSON null. Any other `ISTRound` value or any other extra fails. Every expected field is now required.

## Offline assessment

After authenticating the original authorization, transmitted identity, start, outcome, quarantine, exact body bytes, hashes, and timestamp, R2D.1 parses only that body. It runs the sole echo comparator and the established R2B.1 structural validator. Eligibility requires both to pass and no unpermitted mismatch to remain.

Eligibility does not change the original failure. R2D.1 never writes `verification.json` or `verified-response.bin` in R2D, never copies the response, never changes `failed_or_quarantined`, and never reconciles populations.

## Future continuation specification

Only after a separate read-only audit, committed checkpoint, and explicit user authorization may a later continuation begin. It must first reauthenticate the original R2D authorization, request, attempt, outcome, quarantine, and exact body, then apply the corrected echo contract offline. Failure stops before any network activity. Success may create a new verification record in a new continuation namespace that references—but does not copy or overwrite—the body.

Indiana Early Base remains original ordinal 1 and can never be requested again. Only these original R2C.1 ordinals may later receive one network attempt each, with zero retry and fail-stop behavior:

2. Indiana Early Advanced
3. Indiana Late Base
4. Indiana Late Advanced
5. Memphis Early Base
6. Memphis Early Advanced
7. Memphis Late Base
8. Memphis Late Advanced

The exact original request ID, canonical identity hash, parameters, window, measure, team, ordinal, order, and R2C.1 per-identity lineage are preserved. For each remaining identity, `future_output_namespace` is the immutable R2C.1 value under `cache/phase3f-r2c-protected-recovery/...`; it is not a continuation write destination. The distinct `continuation_output_namespace` is the corresponding path under `cache/phase3f-r2d.2/protected-recovery-continuation/...`. Continuation network ordinals 1–7 may be recorded only as secondary sequencing metadata. The seven responses plus the separately revalidated ordinal-1 body can form an eight-response evidence set only after continuation-time offline verification. R2D.1 grants no continuation authority.

## Deterministic write-once output

The ignored namespace `planning/phase3f-r2d.1/` contains exactly:

1. `response_echo_contract.json`
2. `continuation_plan.json`
3. `quarantined_response_assessment.json`
4. `artifact_hashes.json`
5. `summary.json`

All documents are fully built and strict-JSON validated in memory before the directory is created. JSON is deterministic, UTF-8, sorted-key, newline-terminated, and rejects NaN and infinity. Any existing output directory—empty, partial, or complete—is refused, and files use exclusive creation. The manifest rule is nonrecursive SHA-256 over the other four exact artifact byte streams; the manifest excludes itself while its inventory lists all five files.

Two disposable builds must be byte-identical and removed. A disposable build may be created while the official namespace exists, but every build destination remains write-once. The authorized pre-commit correction may replace only the five existing R2D.1 planning artifacts after validation; it may not preserve a second superseded namespace.

## Stop boundary

A production PASS authorizes only a separate read-only audit. It does not authorize promotion, continuation-time verification, any of requests 2–8, Indiana Early Base reacquisition, reconciliation, final-test construction, prior-profile joining, preprocessing, or model execution.
