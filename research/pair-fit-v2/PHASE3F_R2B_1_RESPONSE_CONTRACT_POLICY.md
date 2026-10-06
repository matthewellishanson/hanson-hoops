# Phase 3F-R2B.1 Protected Response-Contract Correction Policy

## Classification and boundary

**PASS — Phase 3F-R2B.1 corrected response contract frozen; ready for read-only audit**

This checkpoint is a read-only evidence assessment and a deterministic specification build. It does not repair Phase 3F-R2B, authorize transport, promote evidence, construct a final-test population, join profiles, preprocess data, operate a model, or calculate predictions or metrics. Its generated contract identity is `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`.

## Permanent historical status

The original Phase 3F-R2B remains permanently **`FAILED — authorized protected acquisition attempt failed`**. Its quarantine record is historically correct under the implementation frozen at that time. R2B.1 neither rewrites nor “fixes” that execution.

Atlanta Base, ordinal 1, is permanently an attempted identity. It can never become eligible for another network attempt. A later separately authorized phase may revalidate the original bytes offline, but any accepted disposition must link the original request ID, canonical request identity, attempt number, raw path, raw SHA-256, canonical JSON SHA-256, original quarantine path, and this correction-contract identity. The other 59 identities keep their original ordinals 2–60.

## Evidence and strictness decision

The contract was checked against the actual 60 verified 2024–25 full-season TeamDashLineups bodies: 30 Base and 30 Advanced. Every body contains exactly `Overall`, then `Lineups`; all 30 bodies per measure have identical ordered headers for both sets; all rows have the declared width; and every `Overall` set has one row. The preserved 2025–26 Atlanta Base body has the same Base schemas and ordering.

Accordingly, the correction freezes exact ordered schema equality and the established `Overall`, `Lineups` order. A narrower required-column or arbitrary-order rule would be more permissive than the evidence supports and is not adopted. Header hashes below are SHA-256 over compact canonical JSON arrays; the generated `response_contract.json` records every ordered header explicitly.

| Measure | Set | Columns | Ordered-header SHA-256 |
|---|---|---:|---|
| Base | Overall | 57 | `16038004b35cf0c3c477b7257338653ac0112216f22add32070c006f6233d8f9` |
| Base | Lineups | 56 | `a9980efff09c260fa026814ae7a1b74c4acc3ee4d0a7b9cc5ee421987d5fe354` |
| Advanced | Overall | 49 | `1ea7e8e9a2e20f964c8c62be989a083bc578b4699b09b9669f25c83bb17dbff0` |
| Advanced | Lineups | 48 | `520097860d200d772ee9e0b2a220b0d91e25ba64ed61544b1d7f9dfa58194a9e` |

The ordered lists are:

- Base `Overall`: `GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK`.
- Base `Lineups`: `GROUP_SET, GROUP_ID, GROUP_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, SUM_TIME_PLAYED`.
- Advanced `Overall`: `GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GP, W, L, W_PCT, MIN, E_OFF_RATING, OFF_RATING, E_DEF_RATING, DEF_RATING, E_NET_RATING, NET_RATING, AST_PCT, AST_TO, AST_RATIO, OREB_PCT, DREB_PCT, REB_PCT, TM_TOV_PCT, EFG_PCT, TS_PCT, E_PACE, PACE, PACE_PER40, POSS, PIE, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, OFF_RATING_RANK, DEF_RATING_RANK, NET_RATING_RANK, AST_PCT_RANK, AST_TO_RANK, AST_RATIO_RANK, OREB_PCT_RANK, DREB_PCT_RANK, REB_PCT_RANK, TM_TOV_PCT_RANK, EFG_PCT_RANK, TS_PCT_RANK, PACE_RANK, PIE_RANK`.
- Advanced `Lineups`: `GROUP_SET, GROUP_ID, GROUP_NAME, GP, W, L, W_PCT, MIN, E_OFF_RATING, OFF_RATING, E_DEF_RATING, DEF_RATING, E_NET_RATING, NET_RATING, AST_PCT, AST_TO, AST_RATIO, OREB_PCT, DREB_PCT, REB_PCT, TM_TOV_PCT, EFG_PCT, TS_PCT, E_PACE, PACE, PACE_PER40, POSS, PIE, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, OFF_RATING_RANK, DEF_RATING_RANK, NET_RATING_RANK, AST_PCT_RANK, AST_TO_RANK, AST_RATIO_RANK, OREB_PCT_RANK, DREB_PCT_RANK, REB_PCT_RANK, TM_TOV_PCT_RANK, EFG_PCT_RANK, TS_PCT_RANK, PACE_RANK, PIE_RANK, SUM_TIME_PLAYED`.

## Four corrected rules

### 1. Response envelope

A TeamDashLineups body must be strict JSON with exactly two unique, well-formed result-set objects named `Overall` and `Lineups`, in that established order. Missing, duplicated, or unexpected names are rejected. Both sets require unique string headers, exact measure-specific ordered schemas, and row widths equal to the header width. `Overall` must contain exactly one valid team-context row.

### 2. Named result-set selection

Every parser, verifier, reconciliation step, and continuation contract selects `Overall` and `Lineups` by exact name. Array position is never a proxy for semantic identity, and pair rows come only from the uniquely named `Lineups` set. The separately validated ordering rule does not authorize positional extraction.

### 3. Measure-specific ownership

Base owns canonical pair identity and historical time/exposure fields. `GROUP_ID`, `MIN`, and `SUM_TIME_PLAYED` are required by its exact `Lineups` schema; `MIN` and `SUM_TIME_PLAYED` must be numeric, finite, and nonnegative. Base does not own pair `POSS` or the final `NET_RATING` target and must not be rejected because `POSS` is absent.

Advanced owns canonical pair identity plus direct full-season `POSS` and `NET_RATING`. `POSS` is the authoritative future `POSS >= 150` eligibility value and must be numeric, finite, and nonnegative. `NET_RATING` is the authoritative future target and must be numeric and finite. This correction does not change the frozen scientific policy.

### 4. Team-identity location

Team identity is validated from the authorized request `TeamID`, returned response-parameter `TeamID` when a parameter object is present, and the singleton `Overall` row `TEAM_ID`. All available sources must be valid positive numeric IDs and agree. Lineup rows do not contain or require `TEAM_ID`; identity is not inferred from player names and is never injected into raw rows. Later reconciliation may attach team provenance only from validated response context.

## Pair and future reconciliation contract

`GROUP_ID` must contain two distinct positive decimal player IDs. The canonical unordered key sorts them numerically; malformed, same-player, and duplicate canonical pairs are rejected. Base and Advanced `Lineups` sets must be selected by name and have identical pair-key sets. Zero-exposure rows remain visible. Advanced `POSS` supplies eligibility and Advanced `NET_RATING` supplies the target. Exactly 250 rows remains unresolved, not automatically complete or incomplete. Approximate rating reconstruction and selective pair deletion are prohibited. After demonstrated non-exhaustiveness without direct recovery, whole-team exclusion remains the policy.

## Non-executable continuation specification

The failed namespace stays immutable and a later continuation must use a new namespace. Atlanta Base can only be revalidated from its original bytes and receives no second network attempt. Only original ordinals 2–60 may become candidates for later, separate transport authorization; each retains its request ID, ordinal, canonical identity, and exact parameters. If separately authorized, each gets one attempt, zero retries, and fail-stop behavior. Any transport failure stops the continuation. Recovery windows, final-test construction, and modeling remain unauthorized.

The generated continuation plan is not an authorization. It contains no URL, credential, session, retry mechanism, or transport command.

