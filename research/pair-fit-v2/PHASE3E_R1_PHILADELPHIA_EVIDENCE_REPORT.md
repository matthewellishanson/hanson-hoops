# Phase 3E-R1 Philadelphia evidence acquisition

## Primary classification

**Philadelphia full-season response proven non-exhaustive**

The two verified Philadelphia windows contain 271 canonical unordered pair
keys. Philadelphia's verified full-season Base and Advanced responses contain
the same 250 keys. The window union includes all 250 full-season keys plus 21
valid recovered-only keys, which satisfies the predeclared requirement for
classification 1.

No recovered-only pair was assigned a full-season `NET_RATING`. No window
rating was aggregated or used as a target. This checkpoint did not construct a
holdout dataset or estimator matrix, run the frozen model, generate
predictions, calculate metrics, serialize a model, or touch production code.

## Start gate and predeclared policy

The required start gate passed before any work or Philadelphia response access:

- branch: `research/pair-fit-v2`
- clean starting HEAD: `a21314d71b369890844f1fdd883ac0375561507d`
- upstream: `origin/research/pair-fit-v2` at the same commit
- commit subject: `Phase 3E_R0 (Evidence Reconciliation) completed and audited`

The eight-rule population policy was written before inspecting any
Philadelphia response. It is preserved in
`PHASE3E_R1_INCOMPLETE_TEAM_SEASON_POLICY.md` (1,553 bytes; serialized-byte
SHA-256
`9273090b5cc55faddf54f0e531ad3845d5f67e311fa806bf2a6e7d8db74a6c41`).
The immutable acquisition authorization is
`cache/phase3e-r1/authorization.json` (8,344 bytes; SHA-256
`192acbc0562f43b8585d815874b38b317df1127657518b6f838dc7b809e01973`).

## Attempted requests and outcomes

The requests ran sequentially in the predeclared order. Each identity consumed
one attempt, used the established NBA headers, set `trust_env=False`, disabled
redirects, used a 30-second timeout, and had zero automatic retries. The next
transport attempt began at least one second after the preceding attempt
completed. All four outcomes were HTTP 200 and passed JSON, identity, schema,
team, date-window, and row-width validation. No response was quarantined.

| Seq. | Window | Measure | Started (UTC) | Completed (UTC) | HTTP | Rows | Bytes | Raw-body SHA-256 | Canonical-JSON SHA-256 |
|---:|---|---|---|---|---:|---:|---:|---|---|
| 1 | 2024-10-22 through 2025-01-31 | Base | 2026-09-14 03:12:12.164662 | 2026-09-14 03:12:15.132943 | 200 | 136 | 35,345 | `5d966f8084f162f1c23f3ff3ef62d51301917c5fad311b8aba8c5e3cab0688aa` | `8d28ddabb00505c06e54581dd546a902b30b497be767f05cac5e0b038919d175` |
| 2 | 2024-10-22 through 2025-01-31 | Advanced | 2026-09-14 03:12:16.137410 | 2026-09-14 03:12:17.659152 | 200 | 136 | 36,503 | `0347ad63edb0724d3eefda6922859ee073c2974e3d6e6787c640ca98e3a6e13b` | `e8fde708fa87bdbda3363accba8bf08b9d0ae8f9facedda4e2a6c7448e099fd4` |
| 3 | 2025-02-01 through 2025-04-13 | Base | 2026-09-14 03:12:18.664577 | 2026-09-14 03:12:19.901559 | 200 | 206 | 52,492 | `f76f94f7e71af7521f374fc0df9b442c3a4a95e2f1face6bc152040b751bc6ae` | `4568adc631bb6a66289591d86c9654d26ac03c64450b4f041d2e2f536c2b5bcc` |
| 4 | 2025-02-01 through 2025-04-13 | Advanced | 2026-09-14 03:12:20.908288 | 2026-09-14 03:12:22.610047 | 200 | 206 | 54,938 | `bb037725627f54cd0dac652b3ba279bd617f49984cf546f183713542901971e7` | `c351d12825ca0a038f6f4904df77f417c4d71104c194372f757f016f906b4832` |

The corresponding write-once outcome-record SHA-256 values, in the same order,
are `feb90278f06446b0ecfe26a39f610d8020122f12404fb10a0e7be9abd46d23ea`,
`b0af5054b5b8d42be8b80371e4128723bf2d168b00eba4e4584ec41dccd5dec1`,
`5b9c4f01d0aef17e87be3e9183b3784cecad5cbccdc7869d01754b5a2d777495`,
and `c89401f5fcad56268279209445f3b51aa5d787c4bc4a194af2181f0195bdeda2`.
The corresponding write-once started-record hashes are
`6159f48dfc202517dc9cde5be7a9c1b5bf6c5050cc1bbbf16d7b3d2ca084572f`,
`6100092d3fac3a0cb27c123286453c0eea062f6f8eabd4e16a34ca859fe7fae9`,
`f2c90f85debbbe3885d18e2a99a30f15ac576a9055510a0a81598ee9f95142c9`,
and `c0cfbf4d27730d3c97cb947afd2cb34244b0306d30b799c8a9290a5ed101f57d`.
The verified bodies and their attempt records are under
`cache/phase3e-r1/verified/` and `cache/phase3e-r1/attempts/`, respectively.

## Population reconciliation

| Finding | Result |
|---|---:|
| Full-season Base keys | 250 |
| Full-season Advanced keys | 250 |
| Early-window Base / Advanced keys | 136 / 136 |
| Late-window Base / Advanced keys | 206 / 206 |
| Keys present in both windows | 71 |
| Early-only / late-only keys | 65 / 135 |
| Canonical window-union keys | 271 |
| Full-season keys absent from the union | 0 |
| Recovered-only keys absent from full season | 21 |
| Malformed keys | 0 |
| Same-player keys | 0 |
| Duplicate keys | 0 |
| Base-only keys | 0 |
| Advanced-only keys | 0 |
| Missing, nonnumeric, or negative `POSS` rows | 0 |
| Recovered-only pairs potentially meeting `POSS >= 150` | 0 |

The recovered-only pairs have 1 to 14 summed Advanced possessions apiece. The
21 pair rows sum to 160 overlapping pair possessions and 72.265 overlapping
pair minutes; these sums are exposure diagnostics, not unique team totals.

| Player IDs | Pair | Window(s) | Summed POSS | Summed MIN |
|---|---|---|---:|---:|
| `200768`, `1630288` | K. Lowry - J. Dowtin Jr. | early | 6 | 3.216667 |
| `202331`, `1631223` | P. George - D. Roddy | late | 7 | 4.133333 |
| `202704`, `1631311` | R. Jackson - L. Quinones | early | 10 | 3.083333 |
| `203083`, `203954` | A. Drummond - J. Embiid | early | 3 | 1.116667 |
| `203083`, `1641737` | A. Drummond - A. Bona | early, late | 8 | 3.991667 |
| `203083`, `1642024` | A. Drummond - A. Reese | late | 3 | 1.883333 |
| `203954`, `1629022` | J. Embiid - L. Walker IV | late | 13 | 6.266667 |
| `203954`, `1631223` | J. Embiid - D. Roddy | late | 9 | 4.733333 |
| `203954`, `1641737` | J. Embiid - A. Bona | late | 3 | 1.516667 |
| `1626162`, `1631223` | K. Oubre Jr. - D. Roddy | late | 6 | 3.233333 |
| `1626162`, `1631311` | K. Oubre Jr. - L. Quinones | early | 12 | 5.466667 |
| `1626162`, `1642024` | K. Oubre Jr. - A. Reese | late | 9 | 4.723333 |
| `1629022`, `1629643` | L. Walker IV - C. Okeke | late | 14 | 5.816667 |
| `1630178`, `1631311` | T. Maxey - L. Quinones | early | 1 | 0.416667 |
| `1630215`, `1630600` | J. Butler - I. Mobley | late | 12 | 4.500000 |
| `1630231`, `1631311` | K. Martin - L. Quinones | early | 7 | 3.033333 |
| `1630288`, `1630762` | J. Dowtin Jr. - P. Wheeler | late | 8 | 3.983333 |
| `1630288`, `1631311` | J. Dowtin Jr. - L. Quinones | early | 11 | 4.950000 |
| `1630600`, `1641737` | I. Mobley - A. Bona | late | 6 | 2.066667 |
| `1630658`, `1630762` | C. Castleton - P. Wheeler | late | 3 | 1.083333 |
| `1642272`, `1642348` | J. McCain - J. Edwards | early | 9 | 3.050000 |

The full-season Base asset is 65,799 bytes with raw SHA-256
`bfc252f60c0a7192c95b80c741bd322827141b0f1840e4bd3c9be7097f45e6ea`
and canonical-JSON SHA-256
`cedf359e12a07f9800bd7657915d0858cadb8b96c410731b16bd8dbadc16e07b`.
The full-season Advanced asset is 67,595 bytes with raw SHA-256
`9c1d022e5aa933b23e3f66842b6e181f72d1840f3cfaa29ae276f8a263811470`
and canonical-JSON SHA-256
`a3e4810bcf2d3f939b6e34eb2bf6bd70145eb6849abe22819dc1276d984cdff4`.

## Mechanical population disposition

- Charlotte was already proven non-exhaustive. It remains provisionally
  excluded in full because definition-supported direct full-season targets for
  its omitted pairs are unavailable.
- Philadelphia is now proven non-exhaustive by 21 valid recovered-only keys.
  The identical predeclared rule therefore excludes Philadelphia in full.
- No selective retention of the full-season 250, selective dropping of the 21
  recovered pairs, or reconstructed `DEF_RATING`/`NET_RATING` target is allowed.

## Deterministic evidence and scope checks

The cache-only replay reproduced deterministic content SHA-256
`122bfce172afbea1c9e19ba214c5e193cc2cd6c21ce8c9e595ccb7fa7027f3a8`.
The ignored serialized result is
`modeling/phase3e-r1/philadelphia_evidence.json` (26,973 bytes; SHA-256
`907f8474a052ad6358737c8941d6e7a059889d154214e44a5c62aa7b975b4bc5`).

Phase 1C's manifest and Phase 1E's ledger retained their pre-acquisition hashes:

- Phase 1C manifest: `5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c`
- Phase 1E ledger: `5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde`

The R1 path guard rejects any path containing the final-test season before
filesystem access. The runner reports `final_test_season_accessed: false`.
No noncapped validation package was acquired, and no request outside the four
Philadelphia identities was attempted.
