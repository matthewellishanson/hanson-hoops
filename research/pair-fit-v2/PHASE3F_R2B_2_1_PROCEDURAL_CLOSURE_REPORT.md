# PASS — Phase 3F-R2B.2.1 procedural closure complete; ready for read-only audit

## Repository and phase state

- Branch: `research/pair-fit-v2`
- Committed HEAD: `1d98c20f41fe550deafa7e68cba611d7d66bf519`
- Upstream: `origin/research/pair-fit-v2`; ahead `0`, behind `0`
- Index: empty
- Working tree: only the audit-reviewed R2B.2 files, this R2B.2.1 checkpoint, and their narrow `.gitignore` entries are visible
- Commit/push: not performed

Original R2B remains permanently `FAILED — authorized protected acquisition attempt failed`. R2B.1 remains the authoritative corrected response contract, identity `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`. R2B.2 retains `CONDITIONAL PASS — acquisition evidence valid; narrow procedural correction required`; no historical authorization, source, CLI, policy, report, test, or runtime evidence was changed by this phase.

## Existing evidence and retained limitations

The checked evidence proves that all 60 protected bodies are byte-intact, all 60 satisfy the R2B.1 contract, 30 Base and 30 Advanced responses are available, both measures contain 5,403 rows, all 30 Base/Advanced canonical-key sets are equal, and no recovery or final-test/model operation occurred. The R2B.2 evidence remains eligible for later scientific use after approved dispositions for unresolved teams. It does not establish final-test readiness.

The closure records four historical procedural limitations without rewriting them:

1. **Authorization flags.** The top-level R2B.2 inventory authorized 59 exact identities at ordinals 2–60, while every copied nested request retained stale R2B.1 values `currently_network_authorized: false` and `may_become_eligible_only_in_later_separately_authorized_phase: true`. Identities, parameters, and ordering did not drift. This is a machine-contract ambiguity, not evidence of an extra or unauthorized request.
2. **Namespace binding.** The historical CLI accepted caller-selected planning and evidence directories and did not prove exact equality to authorization-frozen canonical paths. No alternate execution is alleged.
3. **Executing source identity.** The authorization and invocation did not pin the exact executing source bytes. The observed implementation is 48,758 bytes with SHA-256 `c3e5e9238b353e3ea6b482f1e0d50582494daa69cf6e297ee3cf4fac36288b86`, and its recorded filesystem write time is later than the invocation. No historical executing hash is inferred or fabricated.
4. **Pacing provenance.** UTC completion-to-next-start intervals have minimum `0.986753`, maximum `1.011286`, and average `1.002996` seconds; 3 of 58 are below one second. Start-to-next-start minimum is `1.248367` seconds and completion-to-next-completion minimum is `1.247101` seconds. Current source uses monotonic enforcement, but absolute monotonic values and sleep records were not persisted. No genuine spacing violation is established; exact one-second completion-to-start compliance is strongly supported, not proved. Scientific materiality is nil.

## Controls frozen for later protected acquisition

Future authorization records must use one phase-local per-request authorization object containing `authorization_phase`, `network_authorized`, `attempt_limit`, `ordinal`, `request_id`, and `canonical_request_identity`. Validation rejects disagreement with the top-level inventory. Inherited status fields are prohibited except as clearly namespaced historical metadata.

Future CLIs must bind supplied planning, raw/attempt evidence, and source-evidence paths to the authorization's exact resolved canonical paths. Detectable aliases, symlink/junction substitutions, alternate roots, path-normalization ambiguity, populated/conflicting official state, and alternate-namespace second invocation are rejected before transport.

Future authorizations must pin byte counts and SHA-256 identities for the acquisition implementation, CLI, applicable policy or machine contract, and project-local modules directly controlling request identity, transport, verification, promotion, restart, or pacing. Invocation must revalidate and record that bounded inventory plus the exact command, Python executable, working directory, and `PYTHONPATH`.

Future pacing uses a monotonic clock and persists UTC start/completion, monotonic start/completion, previous monotonic completion, required gap, calculated pre-attempt gap, requested sleep, observed post-sleep gap, and disposition. It sleeps the remainder, recomputes the gap, and refuses transport if the verified gap is still short. UTC is audit context only.

These controls apply to every later protected acquisition, including any Indiana/Memphis recovery. They do not authorize or require R2B.2 reacquisition.

## Unresolved teams

- Indiana Pacers (`1610612754`): Base ordinal 35, 250 rows, raw SHA-256 `d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3`, canonical SHA-256 `0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5`; Advanced ordinal 36, 250 rows, raw SHA-256 `45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee`, canonical SHA-256 `605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120`. Keys are equal; disposition remains `exact_250_unresolved`.
- Memphis Grizzlies (`1610612763`): Base ordinal 53, 250 rows, raw SHA-256 `540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29`, canonical SHA-256 `b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc`; Advanced ordinal 54, 250 rows, raw SHA-256 `d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6`, canonical SHA-256 `2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3`. Keys are equal; disposition remains `exact_250_unresolved`.

Neither team is declared complete or incomplete, excluded, or assigned recovery dates or identities. Those choices remain a user decision under a later, separately authorized recovery specification.

## Official build and generated evidence

The import-only canary passed. Two disposable builds were byte-identical and were removed. The official offline build was invoked exactly once. Its ignored, write-once namespace is `planning/phase3f-r2b.2.1/`:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `procedural_closure.json` | 5,177 | `bff3783cc3b08237efef3796c1cf6131ae6363b1e86eea6835fb9da42cf99673` |
| `future_protected_transport_contract.json` | 4,074 | `20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234` |
| `input_fingerprints.json` | 24,516 | `02676df134a4757bc9c81d231ed136cf711fe00adcf3c4172ec52a8b18f48937` |
| `artifact_hashes.json` | 740 | `04332a6003859e88bcb54e0b5116e4d807d265296617f1835273f563e5bb1f82` |
| `summary.json` | 972 | `ada2409795ef408b5c6c83bb0c515558efc89f98c02f4add075e9f1882c69668` |

The manifest intentionally excludes its own hash to avoid circularity. Official output exactly matches both disposable builds.

## Validation

- Focused and applicable historical regressions: `193 passed, 4 deselected`
- The four deselections are legacy build tests whose expected behavior hard-locks prior-phase builders to their historical committed HEAD; current preservation is independently pinned and tested
- `py_compile`: passed
- `git diff --check`: passed
- Ignore check: passed for `/planning/phase3f-r2b.2.1/`
- Credential scan: passed; no credential material found
- Prohibited-capability scan: passed; no HTTP/socket client, recovery identity creation, final-test construction, estimator, prediction, metric, or model-serialization capability exists in R2B.2.1
- Write-once, finite deterministic JSON, partial/existing namespace refusal, alternate-root refusal, source mismatch refusal, and pacing controls: tested

No network request was made. No protected response was copied or reacquired. No recovery request identity or authorization was created. No final-test rows, profile join, preprocessing, estimator, prediction, metric, or model artifact was produced.

## Decision boundary and next step

R2B.2.1 freezes future procedural controls; it does not resolve Indiana or Memphis and does not authorize recovery or modeling. The narrowest justified next step is a read-only audit of this checkpoint. After that audit, the user may decide whether to authorize a separate Indiana/Memphis population-set recovery specification with exact season windows and request identities.
