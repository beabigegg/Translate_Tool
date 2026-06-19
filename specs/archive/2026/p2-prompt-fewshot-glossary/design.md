# Design: p2-prompt-fewshot-glossary

## Architecture Summary
This change adds three coordinated behaviors to the existing batch translation pipeline without introducing a new endpoint, storage engine, or IR field. (1) `context_prompts.py` gains pure builder functions that inject few-shot example pairs and a `term_db`-sourced glossary block into the constructed prompt (BR-42/BR-43). (2) A translate-then-critique self-refinement loop runs at the per-request orchestration level inside `translation_service.translate_texts`, reusing the existing Phase-2 refinement seam, bounded by `CRITIQUE_MAX_ITERATIONS`/`CRITIQUE_TIMEOUT_SECONDS` and degrading to the last valid draft on failure (BR-44). (3) The 100% glossary-match guarantee (BR-41) is enforced by a deterministic post-translation substitution pass applied to the final draft — not by prompt persuasion. Cache correctness is preserved by folding a glossary-state digest and a critique-pass marker into the existing `cache_variant` channel (BR-45), and three new in-process counters expose loop and match observability (BR-46). The control-flow change is additive: existing golden-regression and refinement suites must continue to pass (AC-7).

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Prompt builders | `app/backend/services/context_prompts.py` | add few-shot + glossary block builders (pure, leaf-module-safe); zero-shot fallback |
| Critique loop + enforcement | `app/backend/services/translation_service.py` | host per-request critique loop in/after Phase-2 seam; call deterministic glossary substitution on final draft; compute match rate |
| Cache-variant digest | `app/backend/services/translation_strategy.py` | extend `build_strategy` cache_variant with glossary-state digest + critique marker |
| Glossary read path | `app/backend/services/term_db.py` | read-only; reuse `get_document_terms` (approved/BR-29 gate); no schema change |
| Loop config | `app/backend/config.py` | add `CRITIQUE_MAX_ITERATIONS=3`, `CRITIQUE_TIMEOUT_SECONDS=60`, `CRITIQUE_LOOP_ENABLED` |
| Metrics | `app/backend/services/metrics.py` | add `critique_loop_invocations`, `critique_iterations_total`, `glossary_match_rate` (BR-20 lifetime) |
| Few-shot bank | `app/backend/services/context_prompts.py` (in-repo static constant) | curated example bank, independent of `term_db` per BR-43 |

## Key Decisions

### 1. Glossary enforcement mechanism
**Decision:** Deterministic post-translation substitution on the final draft. For each `term_db` term whose `source_text` (case-insensitive) appears in the source, assert `target_text` is present verbatim in the output; if absent, substitute it in.
**Rationale:** BR-41 demands a 100% match rate with zero mismatches. Substitution is the only mechanism that gives a deterministic guarantee independent of model behavior. Per Table N, it is a no-op when the LLM already produced the canonical term.
**Rejected:** Prompt-only injection — cannot guarantee 100% (probabilistic). Constrained decoding — not exposed by Ollama/OpenAI-compatible clients; couples to provider internals. LLM-retry — unbounded cost, still no guarantee.

### 2. Critique loop placement
**Decision:** Service level — inside `translation_service.translate_texts`, occupying/extending the existing Phase-2 cross-model refinement seam (lines ~234-302).
**Rationale:** `translation_strategy.py` is a pure, stateless decision module (no client/IO); placing a loop with LLM round-trips there would break its boundary. `translate_texts` already owns the client, the `tmap`, caching, and the refinement pass — the natural data-flow owner. The revised draft lands in `tmap` (AC-4, test-plan `test_revised_draft_recorded_in_tmap`).
**Rejected:** `translation_strategy.py` — would force IO into a pure module. Processor layer — duplicates the loop across docx/pdf/pptx/xlsx callers.

### 3. Loop termination and cost cap
**Decision:** `CRITIQUE_MAX_ITERATIONS=3`, `CRITIQUE_TIMEOUT_SECONDS=60` (both config, mock-patchable per test-plan). Loop runs ≥1 iteration always (BR-44, Table M). On critique-call exception or timeout, catch, log WARNING, keep last valid draft, do not raise, do not fail the job.
**Rationale:** BR-44 + Table M mandate a bounded, fail-soft loop; the resilience family (`TestCritiqueLoopBounds`) asserts degrade-to-draft on both exception and timeout.
**Rejected:** Unbounded convergence loop — violates the cost cap and Tier-2 cost-containment requirement.

### 4. Cache key design
**Decision:** No cache schema change. Thread a glossary-state digest plus a critique-pass marker through the existing `cache_variant` field, which already flows into `cache_model_key` as `::scenario=<variant>` and into `_make_key`. Digest = SHA-256 of the sorted, newline-joined `source_text\x00target_text` pairs of the terms matched for this request, truncated to a short hex prefix.
**Rationale:** BR-45 requires the key to incorporate glossary state and the critique marker; the `cache_variant` channel already varies the key with zero schema migration. `build_strategy` is the single place the variant is composed (test `test_build_strategy_includes_glossary_digest_in_cache_variant`).
**Consequence:** All pre-glossary cache entries carry a different (or absent) variant, so every prior entry becomes a miss at rollout. This is intended and required — stale pre-glossary/pre-critique results must not be served. No flush is needed; stale rows age out naturally and never match.
**Rejected:** New cache column / schema v2 — unnecessary migration for a value already expressible in the key.

### 5. glossary_match_rate definition
**Decision:** Last-request scalar. After enforcement, `glossary_match_rate = matched_terms / terms_present_in_source` for the most recent request (1.0 when zero terms present, since there is nothing to miss). Stored as a module float, surfaced by `get_metrics()`.
**Rationale:** BR-46 permits either; last-request is cheaper, needs no per-request denominator history, and directly answers "did the last request honor the guarantee." Post-substitution it is always 1.0 when terms are present, making it a regression sentinel for the substitution step.
**Rejected:** Running mean — dilutes a single guarantee breach across history, weakening BR-41 observability.

### 6. Few-shot example bank
**Decision:** Static in-repo curated constant in `context_prompts.py`, keyed by scenario, selected independent of `term_db`. Any domain term appearing inside an example must still agree with `term_db` (BR-43). Empty/unavailable bank → documented zero-shot fallback template (BR-42), never silent omission.
**Rationale:** BR-43 explicitly permits a separate curated bank; a static constant keeps `context_prompts.py` a dependency-free leaf module (no DB coupling, no import cycle) and is trivially testable (`TestFewShotInjection`).
**Rejected:** DB table — new storage/schema for static curated data. Hardcoded inline term lists — forbidden by BR-43.

### 7. Per-unit vs. per-request loop
**Decision:** Per translatable unit (per segment/text in `texts_to_translate`), matching the existing Phase-2 refinement granularity which already iterates per `(tgt, text)`. "Per request" in BR-44 is satisfied because every request runs the loop ≥1 iteration over its units.
**Rationale:** Reuses the established refinement iteration and caching shape; segment granularity is what enables per-segment cache reuse. Cost multiplier is bounded by `CRITIQUE_MAX_ITERATIONS` per segment, consistent with the existing per-segment refine cost.
**Rejected:** Whole-document single pass — loses per-segment cache hits and the existing batching/dedup benefits.

## Rollback Strategy
Revert is code-only and low-risk; no migration to undo. Set `CRITIQUE_LOOP_ENABLED=false` to disable the loop at runtime while leaving prompt/glossary injection intact, or revert the change set entirely. The cache requires no flush in either direction: on rollback, the glossary digest disappears from `cache_variant`, so post-rollback lookups again miss the glossary-tagged entries and recompute against the reverted (pre-glossary) variant — correctness is self-healing because the variant channel partitions entries. New metrics counters are in-process only (BR-20) and vanish on restart. The deterministic substitution pass is the only behavior that changes delivered output; reverting it returns output to raw model text, which is the prior contract.
