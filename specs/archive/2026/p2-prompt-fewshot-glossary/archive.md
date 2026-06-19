# Archive: p2-prompt-fewshot-glossary

## Change Summary

Added LLM prompt few-shot injection and glossary enforcement to the translation pipeline, plus a translate-then-critique self-refinement loop. The motivation was two business requirements: (1) guarantee 100% match rate for user-defined glossary terms in all translated output (BR-41), and (2) allow the model to self-critique and revise each translated segment before delivery (BR-44). The feature was implemented at the Phase-2 seam of `translation_service.translate_texts()` with deterministic post-translation glossary substitution (not prompt-only) ensuring the 100% guarantee is reliable under adversarial LLM behavior.

## Final Behavior

- Every LLM translation prompt now includes curated few-shot examples (`build_fewshot_block()`) and term_db glossary block (`build_glossary_block()`); zero-shot fallback when bank is empty (AC-2, BR-42).
- After each translation attempt, glossary terms are deterministically substituted via `apply_glossary_substitution()`, guaranteeing 100% match regardless of LLM output (AC-1, BR-41, BR-43).
- A translate-then-critique loop refines each segment up to `CRITIQUE_MAX_ITERATIONS` (default 3) or `CRITIQUE_TIMEOUT_SECONDS` (default 60 s). On exception or timeout, the loop degrades to the last valid draft — the job never fails due to the critique loop (AC-4, AC-5, BR-44).
- Cache variant key incorporates a SHA-256 glossary-state digest and a `_crit` suffix, partitioning pre-rollout from post-rollout cache entries (AC-6, BR-45).
- `/api/metrics` response now includes `critique_loop_invocations`, `critique_iterations_total`, and `glossary_match_rate` (AC-8, BR-46).

## Final Contracts Updated

- `contracts/business/business-rules.md` — BR-41–BR-46 added; Decision Tables M and N; schema-version 0.7.2→0.8.0
- `contracts/api/api-contract.md` — MetricsResponse +3 optional fields; schema-version 0.4.1→0.4.2
- `contracts/api/openapi.yml` — regenerated
- `contracts/env/env-contract.md` — CRITIQUE_LOOP_ENABLED, CRITIQUE_MAX_ITERATIONS, CRITIQUE_TIMEOUT_SECONDS added; schema-version 0.4.0→0.4.1

## Final Tests Added / Updated

New file:
- `tests/test_fewshot_glossary.py` — 25 tests across 8 classes: TestFewShotInjection, TestGlossaryEnforcement, TestGlossaryMatchRate, TestGlossarySourceOfTruth, TestCritiqueLoop, TestCritiqueLoopBounds, TestCacheKeyGlossaryDigest, TestCritiqueMetrics

Extended:
- `tests/test_metrics_counters.py` — 7 new tests (BR-46 counters)
- `tests/test_translation_strategy.py` — 1 new cache-variant digest test + updated `endswith` → `in` checks
- `tests/test_hy_mt_quality_refinement.py` — TestCritiqueLoopInvocation (AC-4)
- `tests/test_sentence_mode_consistency.py` — signature test updated for new `terms` parameter

Full suite: 621 passed, 4 skipped (pre-existing), 0 failures.

## Final CI/CD Gates

| gate | tier | outcome |
|---|---|---|
| contract-validate | 1 | pass |
| change-gate (`cdd-kit gate`) | 1 | pass |
| unit-tests (pytest sweeps test_fewshot_glossary.py + 4 extended files) | 1 | pass |
| quality-refinement-regression | 1 | pass |
| golden-sample-regression | 2 | pass (full suite green) |

## Production Reality Findings

From qa-reviewer (approved-with-risk):
- **VR-1 (P3):** `/api/metrics` response-shape sample not enrolled in `tests/contract/response-samples.json`. `cdd-kit validate --contracts` reports "response shape: skipped" — the 3 new optional fields are schema-declared but not body-sample-asserted. Additive-only, low break risk. Harness unenrolled repo-wide (ADR 0007). Owner: backend-engineer + test-strategist.
- **VR-2 (P3):** `glossary_match_rate` is a module-level float (last-request scalar); under concurrent jobs it races. Correctness is not affected (deterministic substitution is per-request). Documented in design.md decision 5.
- **VR-3 (accepted):** `_crit` cache suffix always appended even when `CRITIQUE_LOOP_ENABLED=False`; confirmed intentional per BR-45 / design.md rollback section.

## Lessons Promoted to Standards

None promoted. BR-41–BR-46 encode all product behavior (already in `contracts/business/business-rules.md`). VR-1 (response-shape sample gap) is P3 advisory — repo-wide unenrolled per ADR 0007, no enforcing gate, do-not-promote. VR-2 (glossary_match_rate race) is a per-change implementation detail, do-not-promote.

## Follow-up Work

- P3: Enroll `/api/metrics` in `tests/contract/response-samples.json` to move response-shape gate from "skipped" to "passed" (VR-1). Target: next Tier-2 change touching API response bodies.
- P3: Document `glossary_match_rate` module-float race in design.md or switch to per-job-scoped metric (VR-2).

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
