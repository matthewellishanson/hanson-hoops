# Phase 1D endpoint population-exhaustiveness report

## Conclusion

**Charlotte's 2024-25 Regular Season full-season `TeamDashLineups` Base response is `proven_non_exhaustive`.** A valid `LastNGames=41` response contains three canonical two-player keys that are absent from Charlotte's verified full-season 250-row Base key set. This proves omission of valid season pairs. It does not prove that the server implementation is a hard top-250 cap.

Phase 1D used one of the three authorized live diagnostic requests. Philadelphia `TeamDashLineups` and Charlotte `LeagueDashLineups` were skipped immediately after the first response became conclusive through offline validation of its immutable cache. No reconstruction, partial-window aggregation, other-season acquisition, materialization, or modeling occurred.

## Starting state and mandatory gate

- Starting/final branch: `research/pair-fit-v2`
- Starting HEAD: `3b514774311e2ebd7ab7ea522fb6da78f2ebfe62`
- Final HEAD: unchanged at `3b514774311e2ebd7ab7ea522fb6da78f2ebfe62` (no commit or history operation)
- Initial tree: clean; `git status --short --untracked-files=all` returned no entries
- Initial complete offline suite: 138 passed using the repository `.venv` (the system `C:\Python314\python.exe` did not have pytest, so no tests ran under that interpreter)
- Persisted Phase 1C manifest ID: `season-manifest:3caa17ef8d9d465ab3e803f2`
- Phase 1C manifest file SHA-256 before/after the diagnostic: `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c`
- Phase 1C gate: valid; clean raw-season release: true; cache errors: 0
- Phase 1C state: 60 verified assets and no other status
- Cache-only rows: 5,297 Base; 5,297 Advanced; 5,297 matched; 0 Base-only; 0 Advanced-only
- Possession-based target eligibility: 5,289 eligible; 8 ineligible because possessions are nonpositive
- Exact-250 teams: only Philadelphia and Charlotte, each with 250 Base and 250 Advanced rows

The gate passed before Phase 1D code changes or a live request. The Phase 1C operational manifest and its 60 asset statuses, paths, and hashes were not changed.

## Pre-request cache-only boundary evidence

The offline diagnostic classifies all four Philadelphia/Charlotte full-season responses as `boundary_signal_present`. This classification is a signal, not proof.

| Team | Measure | Rows | Players | Theoretical unordered pairs | Absent theoretical combinations | Minimum exposure | Maximum value across rank fields | Envelope metadata |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Philadelphia | Base | 250 | 30 | 435 | 185 | `MIN=6.333333` | 271 | none |
| Philadelphia | Advanced | 250 | 30 | 435 | 185 | `POSS=13`, `MIN=6` | 271 | none |
| Charlotte | Base | 250 | 27 | 351 | 101 | `MIN=2.833333` | 257 | none |
| Charlotte | Advanced | 250 | 27 | 351 | 101 | `POSS=5`, `MIN=3` | 257 | none |

Every row has a distinct, structurally valid canonical pair key. The response envelopes contain only top-level `parameters`, `resource`, and `resultSets`; each result set contains only `name`, `headers`, and `rowSet`. They contain no pagination, total-count, limit, continuation, or truncation metadata. These facts preserve the Phase 1C finding: exact 250, absent theoretical combinations, higher low-end exposure, and rank values above 250 suggested a returned-row boundary but did not by themselves prove omission.

## Authorization and diagnostic isolation

The authorization allowed at most three sequential new requests and prohibited retry. The deterministic sequence was:

1. Charlotte `TeamDashLineups`, Base, `LastNGames=41`
2. Philadelphia `TeamDashLineups`, Base, `LastNGames=41`, only if Request 1 was valid and inconclusive
3. Charlotte-filtered `LeagueDashLineups`, Base, full season, only if Requests 1 and 2 were valid and inconclusive

Diagnostic identities use the separate `phase1d-diagnostic-asset:` namespace. Payloads and metadata are stored under Git-ignored `cache/phase1d/diagnostics/`; they cannot collide with `raw-asset:` IDs or `cache/phase1c/raw/` paths. The Phase 1D ledger contains three deterministic identities, one attempt for the first, and zero attempts for the later two. Diagnostic rows are used only for pair-key comparison and were never inserted into the 5,297-row full-season observation population.

## Request 1: Charlotte shorter window

### Exact request identity

- Endpoint: `TeamDashLineups`
- URL endpoint path: `/stats/teamdashlineups`
- NBA team: Charlotte Hornets (`1610612766`)
- League: `00`
- Season: `2024-25`
- Season type: `Regular Season`
- Measure: `Base`
- Group quantity: `2`
- `LastNGames=41`
- `PerMode=Totals`, `PaceAdjust=N`, `PlusMinus=N`, `Rank=N`
- Empty filters: `DateFrom`, `DateTo`, `GameID`, `GameSegment`, `Location`, `Outcome`, `PORound`, `SeasonSegment`, `ShotClockRange`, `VsConference`, `VsDivision`
- Zero filters: `Month=0`, `OpponentTeamID=0`, `Period=0`
- Transport: one direct `requests.Session`, established research headers, `trust_env=False` (no proxy), explicit 30-second timeout, no concurrency, no retry, no header rotation, and no authentication workaround

### Acquisition evidence

- Live attempts: 1
- HTTP status: 200
- Latency: `2.062400200054981` seconds
- Response bytes: 46,408
- Diagnostic asset ID: `phase1d-diagnostic-asset:a7595273f2ba589d86e54209`
- Exact response-body SHA-256: `83a5e3d920eadca3e1bb4bdf0841271720459d884162ee2baa71ec1e6bd31f2c`
- Canonical parsed-JSON SHA-256: `c30c2dcafda6b8d8253a966fdcebe1224c2b54d14cecf832f08dfdfd3bad1ca9`
- Result sets: `Overall` (1 row, 57 columns) and `Lineups` (181 rows, 56 columns)
- Schema result after offline revalidation: identical to the approved Phase 1C Base schema
- Pair structure: 181 valid unique canonical keys; 0 malformed keys; 0 duplicate keys
- Envelope pagination/truncation metadata: none

### Auditable validation stop and offline correction

The live runner first stopped and persisted a `validation_error` because the outgoing identity used the endpoint's empty `PORound` sentinel while the response echoed `PORound=0`. It made no retry and did not advance to Request 2. Offline inspection established that the already-verified Phase 1C full-season responses use the same empty-request/numeric-zero response convention. The validator was narrowed to treat only that documented `PORound` representation as equivalent.

The same immutable 46,408 response bytes were then revalidated offline. The original stopped attempt and error remain recorded; the correction records `no_live_request=true` and `did_not_advance_sequence=true`. This was not a retry, did not consume another authorization, and did not touch Requests 2 or 3.

### Pair-key comparison

| Comparison | Count |
|---|---:|
| Shorter-window rows / valid unique keys | 181 / 181 |
| Matched full-season keys | 178 |
| Shorter-window-only keys | 3 |
| Full-season-only keys | 72 |

Exact shorter-window-only evidence:

| Canonical player IDs | Returned group | GP | Base MIN | Structurally valid |
|---|---|---:|---:|---|
| `203901`, `1630163` | E. Payton - L. Ball | 1 | 1.133333 | yes |
| `1629006`, `1631111` | J. Okogie - W. Moore Jr. | 1 | 2.316667 | yes |
| `1630163`, `1630585` | L. Ball - M. Garrett | 1 | 1.516667 | yes |

Each key contains exactly two distinct positive NBA player IDs and appears once in the same-season Charlotte shorter-window response. None appears in Charlotte's verified full-season 250-row Base set. The result is therefore `proven_non_exhaustive` for Charlotte's full-season response.

## Requests skipped

- Request 2, Philadelphia `TeamDashLineups` Base `LastNGames=41`: skipped; zero attempts and no cache payload, because Request 1 proved non-exhaustiveness.
- Request 3, Charlotte-filtered `LeagueDashLineups` Base full season: skipped; zero attempts and no cache payload, because Request 1 proved non-exhaustiveness.

Authorization summary: 3 authorized, 1 attempted, 2 skipped. No failed transport or HTTP request occurred. The original local validation stop consumed the one Request 1 attempt; its immutable HTTP 200 response was accepted only by offline normalization correction.

## Why the shorter-window evidence is proof

In plain language, Charlotte's last 41 games are part of Charlotte's full 2024-25 regular season. If the full-season pair list contained every observed pair, every valid pair found in those 41 games would also be in the full-season list. Three pairs are present in the shorter window but absent from the full-season set. Therefore the full-season endpoint response omitted valid season pairs.

This is a set-membership proof of omission. It does not reveal whether the server uses a fixed row cap, a ranking rule, a query-plan limit, or another undocumented boundary. “Hard top-250 cap” is not established.

## Separate completeness conclusions

- Request-set completeness: unchanged and complete—30 teams and all 60 required Phase 1C assets are verified.
- Returned-row integrity: unchanged—all 5,297 returned Base/Advanced observations remain structurally valid and reconcile one-to-one.
- Population exhaustiveness: Charlotte's full-season `TeamDashLineups` response is `proven_non_exhaustive`. Philadelphia remains `boundary_signal_present` and is not independently diagnosed because the required early stop skipped its request.
- Teams without an exact boundary signal: `no_population_concern_detected` is the appropriate limited statement; it is not proof that undocumented endpoint behavior is impossible.

The Phase 1C request set and returned rows remain valid evidence about the population the endpoint actually returned. The new result supersedes only the earlier statement that Charlotte population exhaustiveness was unresolved.

## Implications and recommended next phase

The 5,297-row table cannot be treated as an exhaustive league-wide population without an explicit selection-bias limitation or a defensible recovery method. Historical expansion or model training should not proceed until a separate recovery-feasibility phase evaluates, without silently mixing grains:

1. Alternative endpoint acquisition.
2. Multiple non-overlapping windows followed by a validated aggregation method.
3. Game-level reconstruction.
4. An explicitly defined top-250 analytical population with a documented selection-bias limitation.
5. Exclusion of affected team-seasons if no defensible recovery method exists.

Partial-window Advanced ratings cannot simply be averaged. Ratings are ratios over possessions; windows can have different denominators, rounding, and overlapping or missing exposure. Aggregation requires an approved numerator/denominator formula and validation that reconstructed values reproduce known full-season rows. Phase 1D implements none of these strategies.

Recommended next phase: a separately authorized recovery-feasibility study before historical expansion, curated materialization, feature selection, thresholds, validation design execution, or model training.

## Offline verification

- Phase 1D-specific mocked/fixture tests added: 16
- Final complete offline suite: 154 passed
- Two independent cache-only Phase 1D replays: identical
- Replay classification: `proven_non_exhaustive`
- Replay counts: 1 attempted asset, 1 offline-verified diagnostic, 178 matched, 3 diagnostic-only, 72 full-season-only
- Canonical replay SHA-256, both runs: `18c09bcc226053b7a3d521be3f8447f1db9455fe8bdcac1545eb6164ed4fae0c`
- Replay transport surface: none; `replay_authorized_diagnostics` has no transport argument
- Phase 1C remains 60/60 verified and unchanged
- `git diff --check`: passed
- Diagnostic payload, sidecar metadata, and ledger: confirmed Git-ignored by `research/pair-fit-v2/.gitignore`
- Prohibited-artifact search: no Parquet, DuckDB, Feather, database, or 2025-26 path
- Research-local `.pytest_tmp`: safely removed after verification
