# Preview research agent guidance

- Keep all implementation and documentation changes inside `research/preview-research/` unless a narrowly scoped root ignore rule is strictly required.
- Do not modify the public comparison app, backend routes, Render configuration, production snapshots, or `research/pair-fit-v2`.
- Treat `data/raw/` as immutable source evidence. Re-acquisition must create or deliberately replace only the matching local cache identity.
- Never commit raw downloads, processed datasets, exports, credentials, proxy details, local environments, or notebook checkpoints.
- Every dataset must retain source, request/import parameters, retrieval time, schema, season, season type, row grain, and validation state.
- Never turn failed or empty acquisition into zeros or a successful dataset.
- NBA percentages are stored as fractions unless a field or export note explicitly says percentage points.
- Keep source statistics, source ranks, and locally calculated fields distinguishable. Local calculations use the `CALC_` prefix.
- Never describe on/off differences as causal impact or as Pair Fit predictions.
- Do not calculate or estimate BPM, PER, or Win Shares.
- Run focused tests and review the changed-file list before handoff.

