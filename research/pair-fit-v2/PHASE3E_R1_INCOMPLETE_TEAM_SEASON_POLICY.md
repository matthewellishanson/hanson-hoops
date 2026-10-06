# Phase 3E-R1 incomplete-team-season policy predeclaration

This policy was fixed at the start of Phase 3E-R1, before any Philadelphia
window response was opened or acquired. The clean starting checkpoint was
`a21314d71b369890844f1fdd883ac0375561507d` on
`research/pair-fit-v2`, matching `origin/research/pair-fit-v2`.

1. A 2024-25 team-season proven non-exhaustive will be excluded from the holdout population in full unless omitted full-season targets can be obtained from a definition-supported direct source.
2. Simple or empirically approximate window aggregation will not be used to create full-season `DEF_RATING` or `NET_RATING` targets.
3. Selectively retaining only the pairs returned by an incomplete full-season response is prohibited.
4. Selectively dropping only recovered pairs is prohibited.
5. Charlotte is already proven non-exhaustive and is therefore provisionally excluded in full under this rule.
6. Philadelphia's disposition will be determined by the same rule after its bounded recovery evidence is reconciled.
7. An exact-250 response alone is a warning signal, not proof of incompleteness.
8. No rule may be changed after the Philadelphia responses are inspected during this checkpoint.

The only authorized live scope is Philadelphia (`1610612755`), 2024-25
Regular Season, `TeamDashLineups`, group quantity 2, using Base and Advanced
for each of these inclusive windows: 2024-10-22 through 2025-01-31 and
2025-02-01 through 2025-04-13. No other request, retry, fallback, team,
season, measure, or date range is authorized.
