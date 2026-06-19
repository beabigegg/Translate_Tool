---
change-id: p2-long-doc-chunking
schema-version: 0.1.0
last-changed: 2026-06-19
---

# CI/CD Gate Review — p2-long-doc-chunking

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| Contract validation | 1 | yes | push + PR | `cdd-kit validate --contracts` in `contract-and-fast-tests` | none |
| Change gate (cdd-kit) | 1 | yes | push + PR | `cdd-kit gate p2-long-doc-chunking` in `contract-and-fast-tests` | none |
| OpenAPI sync | 1 | yes | push + PR | `cdd-kit openapi export --check` in `contract-and-fast-tests` | none |
| Secret scan | 1 | yes | push + PR | grep literal-key pattern in `contract-and-fast-tests` | none |
| Unit / contract / integration / data-boundary / resilience tests | 1 | yes | push + PR | `pytest tests/ -x -q --tb=short` in `contract-and-fast-tests` | `test-results/junit.xml` (14 days) |
| Full regression | 2 | yes | PR only | `pytest tests/ -q --tb=short` in `full-regression` | `test-results/full-regression.xml` (14 days) |
| Env template check | 2 | yes | PR only | `grep PANJIT_API\|DEEPSEEK_API` in `full-regression` | none |
| Golden-sample regression | 2 | yes | PR only | `pytest tests/test_golden_regression.py` in `golden-sample-regression` | none |
| Layout detector dependency | 2 | yes | PR only | grep forbidden deps in `layout-detector-dependency-gate` | none |
| Text expansion benchmark | 2 | yes | PR only | `pytest tests/test_text_expansion_benchmark.py` in `text-expansion-benchmark` | `test-results/text-expansion-benchmark.xml` (14 days) |
| Renderer equivalence | 2 | yes | PR only | `pytest … -k equivalence` in `renderer-equivalence` | `test-results/renderer-equivalence.xml` (14 days) |

### Test coverage provided by Tier 1 `pytest tests/ -x -q`

The existing sweep command automatically picks up all new test files under
`tests/`. No new job or filter flag is needed for the following test families
added by this change (see `test-plan.md` for the full AC → test-id mapping):

- `tests/test_doc_chunker.py` — unit, data-boundary, resilience (AC-1 through AC-6)
- `tests/test_translation_strategy.py` — integration, AC-4, AC-6, AC-7, AC-8
- `tests/test_env_contract.py::TestEnvContractDeclared::test_chunk_overlap_tokens_declared` — contract, AC-3
- `tests/test_sentence_mode_consistency.py::test_sentence_mode_backward_compat_with_chunking_change` — integration, AC-8

## Workflow Changes Applied

One step edited in `.github/workflows/contract-driven-gates.yml`:

1. **Line 3 comment** — updated active-change-gates list to include
   `p2-long-doc-chunking`.
2. **`Change gate (Tier 1)` step** — replaced the `echo "No active change
   gates …"` no-op with `cdd-kit gate p2-long-doc-chunking`. This is the only
   workflow edit required; no new jobs, no new steps.

No new gates were added because:
- All new test files are co-located in `tests/` and are automatically swept
  by the existing `pytest tests/ -x -q` command in `contract-and-fast-tests`.
- The change has no HTTP endpoint, no DB migration, no new binary fixtures,
  and no renderer surface — none of the existing PR-only jobs need
  change-specific augmentation.

## Promotion Policy

- All Tier 1 gates must be green on the PR HEAD commit before merge is
  permitted.
- Tier 2 jobs (`full-regression`, `golden-sample-regression`,
  `layout-detector-dependency-gate`, `text-expansion-benchmark`,
  `renderer-equivalence`) must be green or have a recorded exemption in
  `qa-report.md` with owner + exit date.
- A new failure in any Tier 2 job introduced by this change's commits
  escalates that job to a merge blocker for this PR.
- After merge to `main`, the Tier 2 `full-regression` run on `push` to
  `main` must stay green; a red `main` triggers an immediate revert or
  hot-fix before the next PR is merged.

## Rollback Policy

- Revert the merge commit (`git revert <sha>`) if any Tier 1 gate turns red
  on `main` post-merge. Do not patch-forward until root cause is confirmed.
- `doc_chunker.py`, `translation_service.py` Doc2Doc additions, and the
  `config.py` env wiring are all new code paths; the existing
  `translate_texts()` path is guarded by
  `test_translate_texts_unchanged_after_doc2doc_added` (AC-8). A revert
  restores the pre-change behavior completely.
- If `CHUNK_OVERLAP_TOKENS` was already written to any deployed `.env`, set
  it to the documented default value; the env var is non-secret and additive,
  so no secret rotation is needed.

## Merge Eligibility

**mergeable** when all of the following are true:

1. `contract-and-fast-tests` is green (Tier 1 required gate).
2. All PR-only Tier 2 jobs are green, or any failure is recorded in
   `qa-report.md` with evidence that it is pre-existing and out of scope.
3. `cdd-kit gate p2-long-doc-chunking` exits 0 (verifies contracts, tasks,
   and tier-floor compliance).
4. No open Tier 0 items in `tasks.yml` for this change.
