# Hanson Hoops agent guidance

## Pair-fit v2 research

- Treat `research/pair_fit_v2` as experimental research.
- Do not modify production frontend or backend behavior unless explicitly requested.
- Keep target outcomes, additive player quality and pair interaction conceptually separate.
- Never use target-season complete player statistics as prior prediction features.
- Do not treat minutes or usage as inherent player quality.
- Use minutes and possessions for eligibility, weighting and uncertainty only.
- Cache external NBA API responses; never repeatedly fetch unchanged raw data.
- Keep raw data immutable.
- Document every modeled field in DATA_DICTIONARY.md.
- Store reusable logic in src; notebooks are not the source of truth.
- Use chronological validation and keep the final test season untouched.
- Compare every learned model against documented baselines.
- Report weighted and unweighted error.
- Explain every modeling decision in plain language.
- Do not claim that an interaction effect is validated unless it improves held-out predictions.
- Run relevant tests before completing a task.

## Git safety

- Do not commit, push, merge, rebase, switch branches, delete branches, or rewrite Git history unless explicitly authorized.
- Do not stage unrelated user changes.
- At handoff, report all modified and untracked files.
- Run the specified tests and review the diff before declaring work complete.
- Never commit raw API caches, generated datasets, credentials, environment files, proxy details or secrets.