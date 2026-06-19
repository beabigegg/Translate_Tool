---
change-id: p2-prompt-fewshot-glossary
schema-version: 0.1.0
last-changed: 2026-06-19
---

# Implementation Plan: p2-prompt-fewshot-glossary

## Objective

Deliver three coordinated, additive behaviors to the existing batch translation
pipeline (no new endpoint, storage engine, or IR field), per `design.md`:

1. Few-shot example injection + `term_db`-sourced glossary block in
   `context_prompts.py` builders, with documented zero-shot fallback (BR-42/BR-43).
2. A bounded translate-then-critique self-refinement loop hosted in
   `translation_service.translate_texts` at the existing Phase-2 seam, degrading
   to the last valid draft on critique failure/timeout (BR-44, Table M).
3. A deterministic post-translation glossary substitution pass on the final draft
   guaranteeing 100% match for matched `term_db` terms (BR-41, Table N), with the
   cache variant carrying a glossary-state digest + critique marker (BR-45) and
   three new in-process metrics counters (BR-46).

Backend-engineer owns all code. TDD order is mandatory: write failing tests in
`tests/test_fewshot_glossary.py` first, then implement source changes.

## Scope

This plan covers backend service-layer changes only:

- `context_prompts.py`: new pure few-shot + glossary block builders and a static
  curated few-shot bank constant (Decision 6).
- `translation_service.translate_texts`: critique loop + deterministic glossary
  substitution + match-rate computation at the Phase-2 seam (~lines 234-271)
  (Decisions 2, 3, 7).
- `translation_strategy.build_strategy`: extend `cache_variant` with glossary
  digest + critique marker (Decision 4).
- `config.py`: add `CRITIQUE_MAX_ITERATIONS`, `CRITIQUE_TIMEOUT_SECONDS`,
  `CRITIQUE_LOOP_ENABLED` (Decision 3).
- `metrics.py`: add `critique_loop_invocations`, `critique_iterations_total`,
  `glossary_match_rate` (Decision 5, BR-46).
- `term_db.py`: read-only reuse of `get_document_terms` (no change).
- New test file `tests/test_fewshot_glossary.py` plus extensions to four existing
  test files per `test-plan.md` "Test Update Contract".

### Out of Scope / Non-goals

- New REST endpoint, request/response schema, or API-contract change
  (change-classification: "no new endpoint"). Do not touch `api/`.
- New cache column or schema v2 — the digest rides the existing `cache_variant`
  channel (Decision 4). Do not modify `translation_cache.py` schema.
- New term/IR storage, schema, or `data-shape-contract.md` field. `term_db` is
  read-only here.
- Frontend, env-deploy infra, CI job topology (ci-gates.md modifies one existing
  workflow step only; ci-cd-gatekeeper owns it, not backend-engineer).
- Refactoring the existing Phase-1/Phase-2 batching, dedup, or refinement code
  beyond what the loop placement requires. Do not opportunistically restructure.
- Constrained decoding, LLM-retry-for-glossary, or prompt-only enforcement —
  explicitly rejected in Decision 1/3.
- Hardcoded term lists anywhere (forbidden by BR-43).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | tests | Write failing `tests/test_fewshot_glossary.py` with all 7 new test classes (test-plan.md) BEFORE any source change | backend-engineer |
| IP-2 | prompt builders | Add static few-shot bank constant + pure few-shot block builder + `term_db`-sourced glossary block builder in `context_prompts.py`; zero-shot fallback when bank empty (BR-42/BR-43, Decision 6) | backend-engineer |
| IP-3 | config | Add `CRITIQUE_MAX_ITERATIONS=3`, `CRITIQUE_TIMEOUT_SECONDS=60`, `CRITIQUE_LOOP_ENABLED` (env-overridable) to `config.py` (BR-44, Decision 3) | backend-engineer |
| IP-4 | critique loop | Host ≥1-iteration bounded critique loop at the Phase-2 seam in `translate_texts`; revised draft lands in `tmap`; degrade-to-draft on exception/timeout, never raise/fail job (BR-44, Table M, Decisions 2/3/7) | backend-engineer |
| IP-5 | glossary enforcement | Deterministic post-translation substitution on final draft for matched `term_db` terms; compute last-request `glossary_match_rate` (BR-41, Table N, Decisions 1/5) | backend-engineer |
| IP-6 | cache variant | Extend `build_strategy` `cache_variant` with glossary-state digest (SHA-256 short hex of sorted `source\x00target` pairs) + critique marker (BR-45, Decision 4) | backend-engineer |
| IP-7 | metrics | Add 3 counters + `get_metrics()` surfacing + `reset()` coverage in `metrics.py`, BR-20 lifetime semantics (BR-46, Decision 5) | backend-engineer |
| IP-8 | regression | Extend 4 existing test files per test-plan.md Test Update Contract; keep golden + refinement suites green (AC-7) | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| design.md | Decision 1 (glossary enforcement = deterministic substitution) | IP-5 mechanism constraint |
| design.md | Decision 2 + 7 (loop at service level, per translatable unit, Phase-2 seam ~234-271) | IP-4 placement constraint |
| design.md | Decision 3 (caps, degrade-to-draft, fail-soft) | IP-3/IP-4 loop bounds |
| design.md | Decision 4 (cache_variant digest, no schema change) | IP-6 cache key |
| design.md | Decision 5 (glossary_match_rate = last-request scalar) | IP-5/IP-7 metric semantics |
| design.md | Decision 6 (static in-repo few-shot bank, zero-shot fallback) | IP-2 bank source |
| business-rules.md | BR-41..BR-46; Table M; Table N | all IPs — contract acceptance |
| test-plan.md | AC→test mapping table + 7 new test classes + Test Update Contract + Notes | IP-1/IP-8 test authoring |
| ci-gates.md | Required Gates table | verification commands |
| context-manifest.md | Allowed Paths; CER-001/CER-002 approved | read boundary |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| tests/test_fewshot_glossary.py | create | Write FIRST (failing). 7 classes per test-plan.md lines 39-86. Mock at LLM client boundary only; use in-memory SQLite `TermDB` fixture (do NOT mock TermDB reads). Patch `CRITIQUE_MAX_ITERATIONS`/`CRITIQUE_TIMEOUT_SECONDS`. |
| app/backend/services/context_prompts.py | modify | Add static `_FEWSHOT_BANK` constant + few-shot block builder + glossary block builder (consumes `List[Term]`, not DB). Keep leaf-module purity: no new `app.backend` imports beyond `models.term` type if needed (prefer `TYPE_CHECKING`). Zero-shot fallback string documented. |
| app/backend/config.py | modify | Add `CRITIQUE_MAX_ITERATIONS` (int, default 3), `CRITIQUE_TIMEOUT_SECONDS` (int/float, default 60), `CRITIQUE_LOOP_ENABLED` (bool). Follow existing env-override pattern near `REFINEMENT_ENABLED`/`CROSS_MODEL_REFINEMENT_ENABLED` (lines ~106-110). |
| app/backend/services/translation_service.py | modify | At Phase-2 seam (`translate_texts`, ~234-271): run critique loop ≥1 iteration per unit, bounded by caps, fail-soft (catch exception/timeout, WARNING log, keep last valid draft). Apply deterministic glossary substitution to final draft; compute `glossary_match_rate`; call new metrics hooks. Reuse existing `tmap`. Import new metrics functions alongside existing `record_translation` (line 12). |
| app/backend/services/translation_strategy.py | modify | In `build_strategy` (~248-291): append glossary-state digest + critique marker to `cache_variant`. Keep module pure/stateless (no IO) — digest computed from a passed-in term set, not a DB read. |
| app/backend/services/metrics.py | modify | Add 3 module counters init 0; `record_critique_loop_invocation()`, `record_critique_iteration(n)` (or per-iter), `set_glossary_match_rate(float)`; surface all 3 in `get_metrics()`; extend `reset()`. No IO on import (BR-20). |
| app/backend/services/term_db.py | read-only | Reuse `get_document_terms` (lines 128-142) on the approved/BR-29 gate. No change. |
| tests/test_metrics_counters.py | modify | Extend per test-plan Test Update Contract: assert 3 new counters (AC-8/BR-46). |
| tests/test_translation_strategy.py | modify | Add `test_build_strategy_includes_glossary_digest_in_cache_variant` (AC-6). |
| tests/test_hy_mt_quality_refinement.py | modify | Add `test_critique_loop_invoked_within_translate_texts` (mock-call count ≥1, AC-4). |
| tests/test_context_prompt_i18n.py | run-as-regression | No body change; must still pass after new injections land (AC-2/AC-7). |

## Contract References

All rules below are already written in `contracts/business/business-rules.md`
(contract-reviewer owns edits, not backend-engineer). Implementation must satisfy:

- BR-41 (glossary-match-guarantee) + Table N — deterministic substitution, 100% match → IP-5.
- BR-42 (fewshot-injection-required) — ≥1 example pair in every prompt, zero-shot fallback → IP-2.
- BR-43 (glossary-source-of-truth) — terms exclusively from `term_db`; no hardcoded term lists → IP-2/IP-5.
- BR-44 (critique-loop-policy) + Table M — ≥1 iteration, `CRITIQUE_MAX_ITERATIONS`/`CRITIQUE_TIMEOUT_SECONDS` caps, degrade-to-draft, never fail job → IP-3/IP-4.
- BR-45 (critique-loop-cache-key) — glossary digest + critique marker in cache key; stale pre-glossary entries miss → IP-6.
- BR-46 (critique-loop-metrics) + BR-20 lifetime — 3 counters, in-process, reset-safe → IP-7.

## Test Execution Plan

Bounded ladder. Implementation agents generate evidence with `cdd-kit test run`;
the gate validates `test-evidence.yml`. AC→test mapping lives in `test-plan.md`
("Acceptance Criteria → Test Mapping"); do not duplicate it here. Run phases in
order; the required floor is `collect`, `targeted`, `changed-area`.

1. `cdd-kit test select` — derive targets from `test-plan.md` (falls back to the table below).
2. `collect` — pytest collection succeeds (all new/extended test files import-clean).
3. `targeted` — run `tests/test_fewshot_glossary.py` (all 7 classes) + the 3 extended unit files.
4. `changed-area` — run the changed-area sweep (`tests/test_translation_strategy.py`, `tests/test_metrics_counters.py`, `tests/test_context_prompt_i18n.py`, `tests/test_term_db.py`).
5. `full` — required at Tier 2 for the golden + refinement regression (AC-7): `tests/test_golden_regression.py`, `tests/test_hy_mt_quality_refinement.py` must pass unchanged in behavior.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_fewshot_glossary.py::TestGlossaryEnforcement | matched term appears verbatim in final output after substitution |
| AC-1 | tests/test_fewshot_glossary.py::TestGlossaryMatchRate | match_rate == 1.0 when terms present, 0.0 when none match |
| AC-2 | tests/test_fewshot_glossary.py::TestFewShotInjection | ≥1 source→target pair present in prompt string every call; absent only when bank empty |
| AC-2 | tests/test_context_prompt_i18n.py | prior prompt tests still pass |
| AC-3 | tests/test_fewshot_glossary.py::TestGlossarySourceOfTruth | glossary block sourced from in-memory TermDB; empty DB → empty block |
| AC-3 | tests/test_term_db.py | read path unchanged |
| AC-4 | tests/test_fewshot_glossary.py::TestCritiqueLoop | loop runs ≥1/request; revised draft recorded in tmap |
| AC-4 | tests/test_hy_mt_quality_refinement.py | critique loop invoked within translate_texts (mock count ≥1) |
| AC-5 | tests/test_fewshot_glossary.py::TestCritiqueLoopBounds | loop stops at max iterations; degrades to draft on exception/timeout; job not failed |
| AC-6 | tests/test_fewshot_glossary.py::TestCacheKeyGlossaryDigest | cache key differs after glossary state changes; pre-glossary entry is a miss |
| AC-6 | tests/test_translation_strategy.py | cache_variant embeds glossary digest |
| AC-7 | tests/test_golden_regression.py | no golden-output regression |
| AC-7 | tests/test_hy_mt_quality_refinement.py | refinement suite passes |
| AC-8 | tests/test_metrics_counters.py | 3 new counters increment / init zero / reset-safe |
| AC-8 | tests/test_fewshot_glossary.py::TestCritiqueMetrics | invocations + iterations + match-rate surfaced in get_metrics() |

## Constraints

- TDD order (mandatory): IP-1 first — write `tests/test_fewshot_glossary.py`
  with all 7 classes failing — then implement IP-2..IP-7. Do not implement source
  before the failing tests exist.
- Mock boundary: mock only at the LLM client boundary
  (`translate_blocks_batch`, `OllamaClient`, `translate_once`) for critique /
  few-shot tests. Do NOT mock `TermDB` reads — use an in-memory SQLite TermDB
  fixture (same pattern as `tests/test_term_db.py`) so AC-3 is proven against the
  real read path (test-plan.md Notes).
- Config patchability: `CRITIQUE_MAX_ITERATIONS` and `CRITIQUE_TIMEOUT_SECONDS`
  must be `unittest.mock.patch`-able on the config/strategy module; tests must
  not depend on production defaults.
- Import rules: no new top-level packages. `context_prompts.py` stays a
  dependency-free leaf module — no DB import, no import cycle; reference `Term`
  via `TYPE_CHECKING` only if a type hint is needed. `translation_strategy.py`
  stays pure/stateless (no client/IO) — digest is computed from a passed-in term
  set, never a DB read inside the module.
- Env-var naming: new flags follow the existing `UPPER_SNAKE_CASE` env-override
  pattern in `config.py` (see `REFINEMENT_ENABLED`, `CROSS_MODEL_REFINEMENT_ENABLED`,
  ~lines 106-110); prefix `CRITIQUE_*`.
- Metrics: new counters obey BR-20 — no IO on import, zero-initialized,
  `reset()`-safe; instrumentation must never break translation (wrap hooks like
  existing `record_translation` try/except at call sites).
- Fail-soft: critique-call exception/timeout → catch, log WARNING, keep last
  valid draft, do not raise, do not transition the job to `failed` (BR-44).
- Glossary enforcement is deterministic substitution on the final draft only — no
  prompt-only persuasion, no constrained decoding, no LLM-retry (Decision 1).
- Do not modify `translation_cache.py` schema or any API/IR contract; the digest
  rides `cache_variant` only (Decision 4).

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- Code-map note: `.cdd/code-map.yml` is generated by cdd-kit 3.3.0 and current
  (sources-digest present); line ranges cited above were read directly and are
  accurate as of this plan. If source shifts before implementation, re-derive the
  Phase-2 seam range in `translate_texts` from the code map rather than trusting
  the cited line numbers.
- Cache invalidation by design (Decision 4): every pre-glossary cache entry
  becomes a miss at rollout. This is intended (BR-45). No flush needed; do not add
  a flush step.
- `glossary_match_rate` is a module float (last-request). Concurrent jobs may
  race the scalar; acceptable per Decision 5 (observability sentinel, not a
  per-request ledger). Do not introduce per-request history.
- Loop cost multiplier: per-unit critique bounded by `CRITIQUE_MAX_ITERATIONS`
  per segment (Decision 7). Keep the default at 3; do not raise it without a new
  cost review.
- Few-shot bank correctness: any domain term inside a curated example must agree
  with `term_db` (BR-43). Curate the static bank to avoid contradicting registered
  terms.
