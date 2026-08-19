# Phase 1B architecture and ingestion design

## Status and boundary

Phase 1B is a design-and-contract phase only. This document specifies the future raw JSON → curated Parquet → DuckDB flow and the release gates that must exist before historical expansion. It does not authorize or perform acquisition of the remaining teams, create a Parquet dataset or DuckDB catalog, train a model, select an exposure threshold, or use 2025-26 data.

The executable portions of this design are standard-library validation contracts in `src/pair_fit_v2/phase1b_contract.py` and `src/pair_fit_v2/player_feature_registry.py`. They do not import a Parquet or DuckDB engine and do not perform network or output-file I/O.

## Proposed flow

```text
immutable NBA response JSON
          │
          ├── acquisition event + cache metadata
          ▼
validated raw-asset manifest ── schema quarantine / resume ledger
          │
          ▼
row-preserving Base ⟗ Advanced ⟕ prior-player reconciliation
          │
          ▼
partitioned curated Parquet + curated-output manifest
          │
          ▼
DuckDB catalog/views over Parquet + catalog-registration manifest
```

The JSON cache remains the evidence layer. Parquet is the typed, query-efficient analytical layer. DuckDB is a disposable catalog and query layer over Parquet, not the sole copy of data. Every downstream artifact must be reproducible from immutable cache inputs and versioned contracts.

## Layer contracts

### 1. Immutable raw JSON

Future acquisition writes one response body to a unique cache asset derived from the complete normalized request identity. A successful HTTP response establishes the source event; cache verification is separate.

Raw JSON rules:

- never edit a successful cached payload in place;
- never reuse a filename or asset ID for a different endpoint or parameter set;
- record the request identity independently of response rows;
- validate JSON and all expected result sets before declaring the asset verified;
- keep a failed or schema-drifted asset in the manifest with its error state;
- do not infer a team or season from `GROUP_NAME`; attach them from validated request context.

Future metadata must distinguish:

- `response_body_bytes`: bytes received for the recorded source event;
- `cache_file_bytes`: bytes in the serialized cache file;
- `canonical_json_hash`: semantic parsed-JSON integrity under a named canonicalization version;
- optional `raw_body_hash`: byte-level integrity of the received response body;
- `serialization_version`: exact cache serializer and settings.

These fields must not be collapsed into one ambiguous payload-size or content-hash field.

### 2. Validated raw-asset manifest

One season manifest has a complete normalized logical identity and one raw-asset entry per expected team/measure request. A regular-season Base+Advanced ingestion therefore expects 30 teams × 2 measures = 60 raw assets. Team IDs are canonicalized into numeric order and measure sets into the documented contract order (`Base`, then `Advanced`), so caller input order cannot change the logical manifest ID. Generated asset records use that same team-major, measure-minor order.

The manifest stores:

- manifest kind, contract version, deterministic manifest ID, league, season and season type;
- the authoritative expected team-ID set and required measure set;
- endpoint, `group_quantity`, and any other request parameter governed by the manifest;
- deterministic raw asset ID plus the complete normalized endpoint/request identity;
- status: `planned`, `acquired`, `verified`, `failed` or `quarantined`;
- attempt count and last categorized error;
- acquisition event fields, cache provenance fields and schema fingerprints;
- stage states for raw validation, curated Parquet and DuckDB registration.

The manifest ID is recomputed from the normalized logical identity and must match exactly. Each asset then passes two independent checks: its stored asset ID must match its own embedded identity, and that embedded identity must match the expected team/measure request constructed from the containing manifest and externally approved season contract. A self-consistent asset cannot certify a wrong endpoint, league, season, season type, team, measure, group quantity or extra request parameter.

The manifest is a state ledger, not a request queue that loses prior attempts. An attempt appends provenance and then advances status only after its output is verified.

### 3. Curated Parquet

The proposed primary dataset is `pair_observations`. Its grain is exactly one full pair observation key. Base and Advanced are reconciled with a full outer join so an unmatched source row is retained, flagged and blocked from a clean-season release rather than discarded.

Proposed partition layout:

```text
curated/pair_observations/
  league_id=00/
    target_season=2024-25/
      season_type=regular-season/
        team_id=1610612744/
          part-<deterministic-batch-id>.parquet
```

Partition columns remain present in the logical table contract even if a writer omits them from physical file columns. Files should be written to a same-filesystem temporary path, verified, then atomically renamed. A curated-output manifest records input asset IDs and hashes, transformation contract version, row counts, output path, file bytes, Parquet schema fingerprint and file hash.

No target, exposure or history filter is allowed in the all-rows curated table. Filtered analytical views may be derived later.

### 4. DuckDB catalog

DuckDB should register views over the Parquet dataset with Hive partition discovery; it should not become the only durable data layer. The catalog is reproducible and may be deleted and rebuilt from Parquet manifests.

Planned logical views:

- `pair_observations_all`: every curated observation, including unmatched and target-ineligible rows;
- `pair_targets_eligible`: rows whose explicit target eligibility is true;
- `pair_complete_history_primary`: target-eligible rows with `prior_history_status = 'complete'`;
- `pair_data_quality`: all flags, eligibility reasons, source-presence fields and provenance IDs;
- `player_features_prior`: registered prior-period player features with source/version columns.

View definitions must be versioned and hashed in a catalog-registration manifest. The all-rows view is the reconciliation authority; filtered views are never substitutes for it.

## Stable keys

Keys are stored as typed columns. Delimited display strings or hashes are conveniences, not join authority.

| Key | Ordered components | Rule |
| --- | --- | --- |
| `season_key` | `league_id`, `target_season`, `season_type` | Season label is `YYYY-YY`; season type is a normalized lowercase slug. |
| `team_season_key` | `season_key`, `team_id` | NBA IDs are positive decimal strings normalized without leading zeroes. |
| `pair_key` | `player_1_id`, `player_2_id` | Two distinct IDs sorted with the existing lexicographic canonical rule; source order and names are irrelevant. |
| `observation_key` | `team_season_key`, `pair_key` | Primary key of `pair_observations`. Fixed Phase 1A league/season-type context is explicit in Phase 1B. |
| `raw_asset_id` | contract version + endpoint + every normalized request parameter | SHA-256-derived logical ID; not a response-content hash. |
| `player_feature_key` | `feature_source_id`, `feature_source_version`, `feature_season`, `player_id` | Source/version prevents accidental collision between different definitions. |

`GROUP_ID` and `GROUP_NAME` remain raw audit fields and are never stable observation keys. The same pair on two teams or in two season types remains two observations.

`group_quantity` is part of raw request identity and prevents pair, trio, quartet and five-player cache collisions. The current `pair_observations` contract remains strictly two-player grain with `group_quantity=2`. Future higher-order lineup research must use a new versioned group-observation contract containing `group_size` and an ordered canonical collection of player IDs. A future interface may aggregate pair-model predictions across a larger selection, but that is not equivalent to a model trained directly on higher-order lineups. Generalized group ingestion and modeling are not implemented in this pass.

## Curated pair-observation contract

The curated row groups fields by purpose:

- identity: league, target season, season type, team ID, canonical player IDs;
- raw labels: Base/Advanced `GROUP_ID` and `GROUP_NAME` values;
- source presence: `base_row_present`, `advanced_row_present`, raw asset IDs and source row ordinals;
- exposure: Base `MIN` as `base_shared_min`, Advanced `POSS` as `advanced_poss`, and Advanced `MIN` retained separately;
- targets: returned offensive, defensive and net ratings without alteration;
- target policy: `possession_rate_target_eligible` and an ordered `target_eligibility_reasons` list;
- prior coverage: `prior_history_status` with exactly `complete`, `one_missing` or `both_missing`;
- lineage: run/manifest ID, transformation contract version and input hashes;
- audit flags: malformed identity, duplicate key, unmatched measure, schema drift and field-level parse failures.

Eligibility is derived, never imputed. Missing/nonnumeric possessions, `POSS <= 0`, or missing/nonnumeric required ratings make a possession-rate target ineligible. The endpoint values remain in the row. No positive exposure threshold is selected here.

Prior-history status is independent of target eligibility. `complete` remains the primary baseline population; all statuses remain in storage for coverage analysis and later evaluation of a universal no-history fallback.

Proposed Parquet logical types:

| Column group | Columns | Type / nullability |
| --- | --- | --- |
| Observation key | `league_id`, `target_season`, `season_type`, `team_id`, `player_1_id`, `player_2_id` | UTF-8 string, non-null |
| Raw labels | Base/Advanced group IDs and names | UTF-8 string, nullable when that source row is absent |
| Source presence | `base_row_present`, `advanced_row_present` | Boolean, non-null |
| Source lineage | Base/Advanced asset IDs and source row ordinals | UTF-8 string / INT64, nullable by source presence |
| Exposure | `base_shared_min`, `advanced_min`, `advanced_poss` | FLOAT64, nullable; no imputation |
| Returned targets | `off_rating`, `def_rating`, `net_rating` | FLOAT64, nullable; no imputation |
| Target policy | `possession_rate_target_eligible` | Boolean, non-null |
| Target reasons | `target_eligibility_reasons` | LIST<UTF-8 string>, non-null (empty when eligible) |
| Prior coverage | `prior_history_status` | Dictionary-encodable UTF-8 string, non-null, constrained enum |
| Audit flags | malformed, duplicate, unmatched and parse flags | Boolean, non-null |
| Transform lineage | manifest ID and transform contract version | UTF-8 string, non-null |

NBA IDs remain strings to avoid accidental numeric coercion across tools. Raw JSON remains the authority for exact source serialization; curated numeric fields preserve parsed endpoint values and never overwrite the raw evidence.

## Resumability and failure behavior

The safe resume decision is asset-local:

| Existing state | Required next action |
| --- | --- |
| Fully verified cache hash, serialization version and accepted schema | Skip raw work. |
| Cache exists but provenance or schema verification is incomplete | Re-read and verify cache only. |
| `planned` or retryable `failed` | Acquire later or restore the exact cache; never done implicitly by verification. |
| `quarantined` | Stop for schema review. |
| Manifest contract version changed | Migrate or rebuild the manifest before any stage continues. |

Curated and catalog stages use the same rule: skip only when input IDs/hashes, contract version and output hash all match. A partial temporary file never advances the manifest. Retrying must be idempotent and must not create duplicate observation keys.

## Schema-drift policy

A schema fingerprint is the result-set name, ordered column list and column count. Row count is recorded as data volume, not schema identity.

Drift classifications are:

- `identical`: accepted;
- `reordered`;
- `additive`;
- `subtractive`;
- `mixed` additions/removals;
- `result_set_name_changed`;
- `invalid_fingerprint` for count inconsistencies or duplicate columns.

Every non-identical classification is quarantined for explicit review. No field is silently dropped, filled, renamed, reordered or type-coerced to make a new response fit the old contract. An approved schema change requires a new schema/transform contract version, updated data dictionary, regression fixture and an explicit backfill decision.

## Complete 30-team season validation gates

The following checks must all be reported. A failure preserves evidence and blocks clean-season release; it does not delete rows.

### Manifest and raw assets

- authoritative season snapshot contains exactly 30 distinct expected team IDs;
- exactly one Base and one Advanced asset exists per team: 60 unique deterministic asset IDs;
- manifest logical identity is complete, normalized and equal to the externally approved league/season/season-type/endpoint/group-quantity/request-parameter contract;
- the stored manifest ID exactly matches the ID recomputed from that normalized logical identity;
- every stored asset ID exactly matches the ID recomputed from its embedded request identity;
- independently, every embedded asset identity exactly matches the containing manifest's expected team/measure request, field by field;
- all 60 assets are `verified`, have successful source-event provenance and verified cache provenance;
- schema fingerprints are nonempty, internally valid and uniquely named, with exactly one `Overall` and one `Lineups` fingerprint per asset;
- every fingerprint is recomputed as `identical` against the approved measure-specific schema contract; a stored `accepted` label alone never passes the gate;
- no remaining asset is failed, pending or quarantined.

### Identity and measure reconciliation

- every pair row parses to two distinct canonical player IDs;
- no duplicate full observation key exists within a measure;
- all 30 team IDs and request contexts match the manifest;
- Base/Advanced join is one-to-one on the full observation key;
- Base-only and Advanced-only counts are reported and must be zero for a clean release;
- the all-rows curated count equals the Base/Advanced key union even when the clean-release gate fails.

### Targets, exposure and history

- every curated row has explicit target eligibility and reproducible reason codes;
- every `POSS <= 0` or missing/nonnumeric possession row is retained and ineligible;
- returned ratings are unchanged and missing/nonnumeric target values are reported;
- Base `MIN` and Advanced `POSS` are present as separate exposure fields; Advanced `MIN` is never substituted for Base `MIN`;
- every row has one valid prior-history status and status counts sum to the curated row count;
- no absent prior statistic is zero-imputed;
- every player feature row is strictly earlier than the target season/cutoff.

### Parquet, lineage and catalog

- Parquet schema and physical types match the approved curated contract;
- partition values agree with row key columns;
- output row count, file list, byte sizes and hashes match the curated manifest;
- every curated file lists its exact input asset IDs/hashes and transform version;
- DuckDB all-rows view count equals the curated manifest row count;
- eligible and history-status view counts reconcile exactly to all-rows flags;
- uniqueness and nullability constraints are rechecked through DuckDB;
- the catalog contains no data from the untouched final test season during development.

## Player-feature source registry

`player_feature_registry.py` defines a registry contract instead of hard-coding one feature endpoint into ingestion. Each source declares:

- stable source ID and source version;
- status (`observed`, `proposed` or `retired`);
- source kind/locator and an explicit aggregation contract;
- `player_season` grain and join keys;
- strict pre-target-season availability rule;
- feature families and a field contract;
- notes describing unresolved semantics.

The observed Phase 0F `LeagueDashPlayerStats` source is registered as evidence, but its candidate fields are not an approved model feature set.

Later heliocentrism sources can be registered under the `heliocentrism` family without changing pair ingestion. Before activation, each must document its source event, metric formula, numerator/denominator, aggregation grain, trade handling, missingness, availability time, schema contract and version. Examples such as touch concentration, time of possession or possession-ending burden are research directions only; Phase 1B selects no source, formula or feature weight.

Registry validation rejects a source that permits target-season information. Feature joins retain `feature_source_id`, `feature_source_version`, `feature_season` and `player_id` so definitions remain auditable.

## Cache-only Phase 1B verification

The design contracts were replayed over only the existing four-team 2024-25 Base/Advanced caches:

- 4 pilot teams and 8 raw assets;
- 8 unique deterministic raw asset IDs;
- all 8 recorded canonical JSON hashes matched their cache payloads;
- Base and Advanced schema drift classification was `identical` for every pilot team;
- 736 pair observations and 736 unique full Phase 1B observation keys;
- team row counts remained Warriors 183, Celtics 141, Wizards 208 and Nets 204;
- the retained Washington zero-possession finding remained the sole ineligible `POSS <= 0` row;
- the default player-feature source registry passed validation.

This is bounded contract verification, not a 30-team season release. No remaining-team manifest was executed, no live request was made, and no Parquet or DuckDB artifact was created.

## Approval gates before ingestion expands

Before requesting any remaining-team acquisition, review and approve:

1. the key and curated column contracts;
2. the manifest/provenance field set and hash/serialization versions;
3. the quarantine policy and schema-version migration process;
4. the row-preserving outer-join behavior and clean-season release gates;
5. the exposure and target-eligibility policy, including any future positive threshold;
6. the uniform missing-history treatment and universal fallback evaluation plan;
7. the chronological validation design.

Model training remains out of scope.
