# Phase 2E: multi-season historical raw acquisition

Primary classification: **`2014-15 through 2023-24 raw training window acquired with population caveats; curation planning ready`**.

This is a raw-acquisition checkpoint, not a curation or modeling result. It records returned NBA endpoint populations, preserves every valid returned row (including zero-possession rows), and leaves filtering, target selection, exposure thresholds, feature selection, missing-history treatment, validation design, and modeling unresolved.

## Scope and evidence basis

Phase 2E completed the seven authorized target/prior pairs below, cache-first and sequentially. Each release has two prior-player assets (Base Per100Possessions and Totals) and 60 pair assets (Base and Advanced for each of 30 teams), for 62 immutable assets per target season.

| Target season | Prior-player season | Phase 2E matched observations | Positive-POSS / preserved zero-POSS |
|---|---|---:|---:|
| 2020-21 | 2019-20 | 5,014 | 4,991 / 23 |
| 2019-20 | 2018-19 | 4,545 | 4,531 / 14 |
| 2018-19 | 2017-18 | 4,806 | 4,795 / 11 |
| 2017-18 | 2016-17 | 4,601 | 4,588 / 13 |
| 2016-17 | 2015-16 | 3,971 | 3,957 / 14 |
| 2015-16 | 2014-15 | 3,852 | 3,844 / 8 |
| 2014-15 | 2013-14 | 4,392 | 4,382 / 10 |
| **Phase 2E total** |  | **31,181** | **31,088 / 93** |

### Asset-counting convention for the complete window

Asset counts refer to immutable raw response bodies, not observation rows or attempt events. The Phase 2B release manifest contains 60 verified pair-asset records: 50 newly acquired in Phase 2B and 10 `reused_verified` pair responses from Phase 2A. It also records two `reused_verified` 2022-23 player-source dependencies from Phase 2A. Phase 2C, Phase 2D, and each Phase 2E release own two player-source responses and 60 pair responses.

| Scope | Pair response assets | Release-owned player-source assets | Reused player-source dependencies | Release-owned asset records | Distinct response assets required by Phases 2B-2E |
|---|---:|---:|---:|---:|---:|
| Phase 2B | 60 (50 new, 10 reused) | 0 | 2 | 60 | 62 |
| Phase 2C | 60 | 2 | 0 | 62 | 62 |
| Phase 2D | 60 | 2 | 0 | 62 | 62 |
| Phase 2E | 420 | 14 | 0 | 434 | 434 |
| **2014-15 through 2023-24** | **600** | **18** | **2** | **618** | **620** |

Thus 618 is the count of release-owned verified asset records in Phases 2B-2E. The distinct-response count is 620 because the Phase 2B release also depends on two immutable Phase 2A player responses; the 10 reused Phase 2A pair responses are already included among the 600 pair assets. Neither number is an acquisition-attempt count, and neither changes raw evidence or the 46,938-observation window total.

The final cache-only combined audit is `research/pair-fit-v2/cache/phase2e/final-combined-audit.json`. Its canonical deterministic analysis SHA-256 is **`d57840f80172df49ea7350520fbf1961499c6f558c70c40ced2bab38c7b5379f`**.

## Acquisition accounting and exceptional events

All 434 authorized identities verified. The accounting below distinguishes an attempt event from a confirmed HTTP response: the original Cleveland event was deliberately retained as uncertain and has no inferred transport result.

| Target | Requested | First starts | Retries | Transport-attempt events | Verified | Failed | Quarantined | Confirmed HTTP 200 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020-21 | 62 | 62 | 1 | 63 | 62 | 0 | 0 | 62 |
| 2019-20 | 62 | 62 | 0 | 62 | 62 | 0 | 0 | 62 |
| 2018-19 | 62 | 62 | 0 | 62 | 62 | 0 | 0 | 62 |
| 2017-18 | 62 | 62 | 0 | 62 | 62 | 0 | 0 | 62 |
| 2016-17 | 62 | 62 | 0 | 62 | 62 | 0 | 0 | 62 |
| 2015-16 | 62 | 62 | 1 | 63 | 62 | 0 | 0 | 62 |
| 2014-15 | 62 | 62 | 0 | 62 | 62 | 0 | 0 | 62 |
| **Combined** | **434** | **434** | **2** | **436** | **434** | **0** | **0** | **434** |

There were no non-200 HTTP responses, permanent failed assets, quarantine records, or final integrity stops. The complete exceptional-event record is:

| Event | Persisted disposition |
|---|---|
| 2020-21 Cleveland (`1610612739`) Advanced, ordinal 16, asset `phase2e-2020-21-asset:e26463f0f4802e8d69d3849c` | Attempt 1 was entered as `started` at `2026-09-06T20:44:45.581037Z` and interrupted before a transport result could be established. It has no status code, body, latency, raw cache, metadata, or failure evidence. The interruption was treated as uncertain, not as a timeout or failure; the coordinator stopped conservatively. |
| Cleveland recovery | The user separately authorized exactly attempt 2, with no added identity or budget. The pre-recovery manifest and ledger were archived byte-for-byte, the authorization was written immutably, and attempt 1 remained unchanged. Attempt 2 began `2026-09-07T19:25:52.772211Z`, returned HTTP 200 in 3.590579300012905 seconds, and verified the 213-row Advanced payload. No third attempt was authorized or used. |
| 2015-16 San Antonio (`1610612759`) Advanced, ordinal 52, asset `phase2e-2015-16-asset:2adde3881dcb026d37746899` | Attempt 1 was a retryable 30-second `ReadTimeout`; it produced no promotion. Attempt 2 began `2026-09-08T00:09:22.238307Z`, returned HTTP 200 in 0.6382855999981984 seconds, and verified 133 lineup rows. |

The recovery authorization is `phase2e.cleveland-16-recovery.v1`: it records `original_outcome: uncertain`, `attempt_number: 2`, and `budget_extension: 0`. Its archived anchors are manifest `5011d70b79eb5efa03470032c899e228b1bd5073d6890ae2326ef2b062f66211` and ledger `6aa32983895bd5502155634bc445775c2a26ccb461137c886ae5adef2368100b`. Those hashes identify the pre-recovery documents; they do not describe the completed current release.

## Certification, schemas, reconciliation, and population caveats

Every season passed the 12-asset canary before continuation, then passed all 30 persisted/recomputed team gates and a repeated cache-only release analysis before its immutable checkpoint was written. Each canary is a certification of the acquired evidence, not a completeness proof.

| Target | Canary assets / matched rows | Canary SHA-256 | Release analysis SHA-256 | Boundary signal |
|---|---:|---|---|---|
| 2020-21 | 12 / 839 | `2c0cc39b6865b75c958a373c693918dac2e53946fefc06d358db8b55203bc4ab` | `bf242a60ff3a8253b2af064aa2af143a43f211ee54cc2178294d2233ad6680e3` | Houston (`1610612745`) returned exactly 250 rows |
| 2019-20 | 12 / 805 | `02697287a3510dc19937ccd2b7db29e194104b766aedfa4d3947a66dad079917` | `6177dd1e3e6f3c6b752370907b4251cb1d1934c61d586643768bd9788abe1404` | none |
| 2018-19 | 12 / 695 | `8e365a9029dc24073a09d15157782a158440009d0a32a4d3eb4ee1dd5fb90db5` | `d5b657889a8b5ead072ede872049bfc96ed58c0bafa8571cba344fae852ab4e7` | none |
| 2017-18 | 12 / 657 | `1a476aa54287731a74afc23f4076fe1e3f4add11c6ecaf33e64280af699a9ad7` | `e8636ecfc54b30af7eb4b9252dd5ae527fcaaa180b97225a2d9ec5ed435d29a5` | none |
| 2016-17 | 12 / 660 | `4c9fd045cb8e7a58de5111f5899c1fd0e04c42bac1d4bb38aeaefd837c4246e5` | `41e0ff112c61a8ac3cc97d2ee659ab1683b5486c9a643350d9e359145f497622` | none |
| 2015-16 | 12 / 618 | `aaf26ce406931ede4f7c952aad3019ebd5a9be2eca15aac4e5fe7c4fc25591c3` | `1c6aec40d79936a42f30f090937e7f482c14366d859b9a7608a62c5212c6578d` | none |
| 2014-15 | 12 / 697 | `4dcab8c4d8b737a459ad434c7fff342eb42b71bed5dd1f397c9496084f07d0d7` | `afa2df3f113cd982a45bd1e5f1402882c9258056093c9b17c30919ada911aee8` | none |

All seven releases matched the approved pair contract `schema-contract:cf262e22edf0272f5fe53293` exactly: Base `Overall`/`Lineups` have 57/56 ordered columns and Advanced has 49/48. The two player sources per season matched the reviewed 69-column `phase2a.player-base.v2` contract (`schema-contract:a39b5a33c328fd9c467ff8d6`). No accepted asset had added, removed, renamed, or reordered fields. The raw responses and metadata remain immutable; schema drift would have been quarantined rather than coerced.

For each target season, Base rows equal Advanced rows and reconcile one-to-one to the matched count in the first table. Across all Phase 2E releases there are zero Base-only keys, Advanced-only keys, malformed/same-player pair rows, duplicate pair keys, standard-rating identity failures, or estimated-rating identity failures. All returned possession and minute values used for descriptive auditing are valid; 93 valid `POSS=0` rows are preserved and target-ineligible rather than discarded. The direct standard and estimated rating identities are recorded as displayed-value checks, not as an approval of a later target choice.

The exact-250 Houston result is a boundary signal, not proof that a row is missing. More generally, returned full-season endpoint populations are not claimed exhaustive: absence of a diagnostic key never proves exhaustiveness. Legitimate pair-team-season observations are retained separately when a player or unordered pair occurs on more than one team or in more than one season. Pair minutes and possessions are overlapping row exposures, not independent league totals. The 2019-20 and 2020-21 identities remain valid distinct pandemic-era seasons. The intended three-point-era window has internal historical change and requires time-aware treatment if curation later proceeds.

## Prior-history coverage: descriptive only

Prior records are joined only by stable player ID from the immediately preceding listed season. A missing source record is reported factually; it is not labeled rookie, inactivity, retirement, or data error. No row was excluded, imputed, or assigned a missing-history policy.

| Target | Complete | One missing | Both missing | Complete pair share |
|---|---:|---:|---:|---:|
| 2020-21 | 3,431 | 1,414 | 169 | 68.43% |
| 2019-20 | 2,803 | 1,513 | 229 | 61.67% |
| 2018-19 | 3,140 | 1,488 | 178 | 65.33% |
| 2017-18 | 2,692 | 1,606 | 303 | 58.51% |
| 2016-17 | 2,556 | 1,264 | 151 | 64.37% |
| 2015-16 | 2,763 | 1,007 | 82 | 71.73% |
| 2014-15 | 2,980 | 1,245 | 167 | 67.85% |
| 2021-22 (Phase 2D) | 3,592 | 1,865 | 288 | 62.52% |
| 2022-23 (Phase 2C) | 3,302 | 1,345 | 158 | 68.72% |
| 2023-24 (Phase 2B) | 3,514 | 1,490 | 203 | 67.49% |
| **2014-15 through 2023-24** | **30,773** | **14,237** | **1,928** | **65.56%** |

The Phase 2E seven-season subtotal is 20,365 complete, 9,537 one-missing, and 1,279 both-missing. Its complete-history rows account for 6,438,865.768332 summed Base minutes and 13,420,510 summed pair possessions; one-missing and both-missing rows remain present. These are overlapping diagnostic exposures, not estimates of unique team time or possessions. The prior Phases 2B-2D counts above are preserved from their immutable release audits; the combined row counts are arithmetic summaries of the individually documented season populations, not a new raw-data aggregate hash or curation decision.

## Complete historical-window status

The raw training-target window now comprises 46,938 pair-season-team observations: 31,181 from Phase 2E plus the already completed 5,745 (2021-22, Phase 2D), 4,805 (2022-23, Phase 2C), and 5,207 (2023-24, Phase 2B). It contains 46,786 positive-possession observations and 152 preserved zero-possession observations. The combined audit describes 1,424 unique players and 35,355 unordered pairs; 8,032 pairs repeat across seasons. These repeated identities are descriptive and are not deduplicated across valid team-season observations.

2024-25 remains the validation season and 2025-26 remains the untouched final test season. No protected-season data was acquired or created by Phase 2E.

## Reproducible evidence hashes

The hashes below have specific persisted meanings: manifest, ledger, initial plan, and allowlist hash their named immutable JSON files; checkpoint analysis and canary hash the cache-only certified computations recorded in that checkpoint. Per-asset raw-body and canonical-JSON hashes remain in the corresponding immutable manifest/metadata. No undocumented cross-asset raw aggregate digest is introduced here.

| Target | Manifest SHA-256 | Ledger SHA-256 | Plan SHA-256 | Allowlist SHA-256 |
|---|---|---|---|---|
| 2020-21 | `60cbffa3af6b6115e8fd0462644f9ac6004f63ed19b22f72e369bc43461e4b60` | `334e1e8106d935fb9571f41ceaed1ea734ec930466ad18407a5a1c2a6f880c69` | `7cea42ddd0e34dfcf68b1569ed70ae5be311c1b9326ba6363f15c1d17749e9f7` | `5183825b6a943ad11df44572d25503fcf6eb3d00a133a5abe711fd883f0545d9` |
| 2019-20 | `eca79fcc130d81c1f5a52fb57d2e6a724058b849ba1e51b62c4215e13cc9f3ac` | `c23a8129b63a5245a24bc7dce51c2d069e78a860bf0a9875bd3d7a351fe25c54` | `3f5e3345d5cc9a59da6a983e0ef86a66c1bf43cc5135972fc7cb08ad72f44f10` | `e46b210f84ac447bfdf708b78f5f03f26c6fd300878b8910c62eccc6c5923309` |
| 2018-19 | `ab015676f489f041273da4bd16a61bdf3cff6c2b973fd41dacfa7fc746229b48` | `49c9977b12d451d8105310c68edaa2cb5298f68721b8fb3ccc7b8b4c54b430b8` | `9dfcbdf4ae27ba1b66c7d9ae455a70f366a43837c0a6b17b2b67a0f79b0e1d59` | `7a40cf91924d5d927127ee1c8cacfd0329f957f85c8296269edece409beef95b` |
| 2017-18 | `018fd2c3a87fddf5b55a48797026da60c36b71e86fd75353877015f134660bb4` | `8a90537fecff338d76b51c9ce4b5012c295f92365d1aaac2138f57832bc1ee01` | `8473a75dbdcc331d8df96e8e45840ff72fcaf85ae211435e60385dd6bc07774d` | `e8a2271e53bdc999d84f6cf3d4e6dd917d7327cf43d752d552676c7e697964bd` |
| 2016-17 | `adfae71d4f297f0a5d6d23f8efece5cd35787b51cdae96d44cca95dd61b4a1cb` | `63e0e965138f4a36a2922b9d6da4e7fac23f2238a9147a1ad852dcfdbb4051f4` | `2566fb338142a388cb5bbeace29f9455eeddee60d2898f86da121e27490aa145` | `9d0cc99c7d6e332242478e2c84b5aa1f304b24b24e0b7fa0b9ff0622fc3b17c2` |
| 2015-16 | `468dfb37fd87e4f67f78f467fd1e04a27ee8f03fdc7faedca01d93592a25042d` | `9f52a748f37f428f78516e28af8f01ed05ada7a5b3ec71433ec66bc08892c50b` | `fccd8ed4ec8c8aae566591c14943e46e15108ad03ca06a139c1c49102411b7e8` | `fcfa5de5d965f4baa5a7862cbb5f4a3f0c95f18b56d0655efb493eea7330ad05` |
| 2014-15 | `94228afc1c346122c6bf289f7dc542e16287b3a3406c36b3c8b60198ec5c4c97` | `28e634b846832c266ead110474b41cadee636be4d73e4bea7e037335f2e5da02` | `dea854a5d239d42abb3c60a2b5960aa64f587ee22a5e097121b6d89a58cdcb4f` | `d520050cf79c23166548aeb4c8d5d612114d50c8c5ef4eeaca195a503e3b837e` |

The final combined deterministic SHA-256 at the start of this report is the canonical serialized `phase2e.combined-audit.v1` result. It is reproducible only from the persisted authorized caches and includes the completed Phase 2E releases plus the released Phase 2B-2D window summaries; it is not a claim about live endpoint population completeness.

## Questions deferred to curation

- Which direct rating field(s), if any, will become target variables; whether estimated fields or recovered-only values have any later role.
- Any positive exposure eligibility threshold, weighting, low-exposure reliability treatment, or handling of the preserved zero-possession rows.
- Feature definitions, transformations, missing-history handling, and whether a no-history fallback exists. No zero-imputation or complete-case policy has been selected.
- Treatment of traded players, team context, repeated players/pairs, time-aware historical change, and the 2019-20/2020-21 seasons.
- Validation protocol, chronological splits, baselines, final-test isolation, and any model or interaction evaluation.
- Whether and how endpoint-population caveats and the 2020-21 Houston exact-250 boundary signal affect later curated analyses.

Nothing in this checkpoint creates curated data or a database, selects a policy, begins Phase 3, trains/evaluates a model, changes immutable raw evidence, or authorizes live acquisition.
