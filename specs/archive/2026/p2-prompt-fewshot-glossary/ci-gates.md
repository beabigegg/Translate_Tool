---
change-id: p2-prompt-fewshot-glossary
schema-version: 0.1.0
last-changed: 2026-06-19
title: "CI Gate Plan: LLM prompt few-shot + glossary injection + translate-then-critique loop"
---

# CI/CD Gate Review

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | push, pull_request | `cdd-kit validate --contracts` in `contract-and-fast-tests` | none |
| change-gate | 1 | yes | push, pull_request | `cdd-kit gate p2-prompt-fewshot-glossary` in `contract-and-fast-tests` | none |
| unit-tests | 1 | yes | push, pull_request | `pytest tests/ -x -q` in `contract-and-fast-tests` (sweeps `tests/test_fewshot_glossary.py`, `tests/test_metrics_counters.py`, `tests/test_context_prompt_i18n.py`, `tests/test_translation_strategy.py`, `tests/test_term_db.py`) | `test-results/junit.xml` (14 days) |
| quality-refinement-regression | 1 | yes | push, pull_request | `pytest tests/ -x -q` in `contract-and-fast-tests` (sweeps `tests/test_hy_mt_quality_refinement.py`) | `test-results/junit.xml` (14 days) |
| golden-sample-regression | 2 | yes | pull_request | `pytest tests/test_golden_regression.py` in `golden-sample-regression` job | none |

### Acceptance Criteria coverage

| gate | test-plan.md rows covered | ACs satisfied |
|---|---|---|
| contract-validate | all contract rows | AC-1 (glossary-match contract), AC-3 (term-db source-of-truth contract), AC-6 (cache-key contract) |
| change-gate | all test-plan rows for this change | all ACs |
| unit-tests | test-plan rows: AC-1 `TestGlossaryEnforcement` + `TestGlossaryMatchRate`; AC-2 `TestFewShotInjection`; AC-3 `TestGlossarySourceOfTruth`; AC-4 `TestCritiqueLoop`; AC-5 `TestCritiqueLoopBounds`; AC-6 `TestCacheKeyGlossaryDigest`; AC-8 `TestCritiqueMetrics` | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8 |
| quality-refinement-regression | test-plan row: AC-4/AC-7 `tests/test_hy_mt_quality_refinement.py` (extended with `test_critique_loop_invoked_within_translate_texts`) | AC-4, AC-7 |
| golden-sample-regression | test-plan row: AC-7 `tests/test_golden_regression.py` | AC-7 |

## Workflow Changes Applied

One step in the existing `contract-and-fast-tests` job was modified.

**Before (`contract-driven-gates.yml` line 47):**
```
- name: Change gate (Tier 1 — blocks merge)
  run: echo "No active change gates — all changes archived."
```

**After:**
```
- name: Change gate (Tier 1 — blocks merge)
  run: cdd-kit gate p2-prompt-fewshot-glossary
```

The header comment on line 3 was also updated from `# Active change gates: none (archived: ...)` to include `p2-prompt-fewshot-glossary` in the active list.

No new jobs were added. The existing `contract-and-fast-tests` job sweeps `tests/` with `pytest tests/ -x -q`, which automatically covers `tests/test_fewshot_glossary.py` (new) and all extended existing test files. The existing `golden-sample-regression` job covers AC-7 regression on PR without modification.

## Required Check Policy

Both of the following GitHub required status checks must pass before merge is permitted:

- `contract-and-fast-tests` (Tier 1): runs `contract-validate`, `change-gate`, `unit-tests`, and `quality-refinement-regression` gates. Blocks merge on any failure.
- `golden-sample-regression` (Tier 2, PR-only): runs `tests/test_golden_regression.py`. Blocks merge on PR on any regression in existing golden output.

Branch protection must list both job `name` values exactly as above. No new branch protection rules are required beyond what is already in place; existing `contract-and-fast-tests` and `golden-sample-regression` rules cover this change.

## Promotion Policy

This change is promoted when both required status checks pass (`contract-and-fast-tests` and `golden-sample-regression`), all `cdd-kit gate p2-prompt-fewshot-glossary` validations are green, and no regressions are detected in the full test suite. Promotion is blocked if any of the following are open: failing required checks, unresolved contract drift, or newly attributed flaky-test failures.

## Rollback Policy

This change is a pure behavioral change to the translation pipeline with no DDL, no schema migration, and no new endpoint. Rollback is a standard git revert of the feature commits.

1. Revert the implementation commits on `main`.
2. The reverted state passes all pre-existing tests unchanged (no database state to undo).
3. No cache warm-up or invalidation step is required: the cache-key digesting introduced by AC-6 is additive; reverting it causes old (no-digest) keys to be used again, which is safe.
4. No feature flag or env-var toggle is required for rollback.

## Artifact Retention

| artifact | job | retention |
|---|---|---|
| `test-results/junit.xml` | `contract-and-fast-tests` | 14 days |
| `test-results/full-regression.xml` | `full-regression` | 14 days |

Golden-sample and renderer-equivalence jobs do not produce separate XML artifacts for this change; their pass/fail is the gate signal.

## Merge Eligibility

**mergeable** when:
- `contract-and-fast-tests` passes (required status check — Tier 1).
- `golden-sample-regression` passes (required status check — Tier 2, PR only).
- No quarantined-flaky tests are newly attributed to this change.

**blocked** when any required check above fails or when `cdd-kit gate p2-prompt-fewshot-glossary` reports open tasks or unresolved contract drift.

**informational-risk:** `full-regression`, `renderer-equivalence`, `text-expansion-benchmark`, and `layout-detector-dependency-gate` are not modified by this change and are not AC-linked; their results are informational for this change. A new failure in those jobs must be investigated before merge but is escalated to blocker only if the failure is causally linked to this change's commits.
