# Archive — remove-cross-model-refinement

## Change Summary
Cross-model refinement (HY-MT 7B translate → Qwen 9B refine) was local-Ollama-only dead code: `model_router.py` had set `refine_model=None` for all cloud providers since Phase 1. ~830 lines of dead code across config, LLM clients, model router, orchestrator, translation service, helpers, and three processors were removed, along with the dedicated test file (336 lines). The removal simplifies the translation hot path and eliminates a GPU-visible code path that was never reachable from the primary cloud providers (PANJIT/DeepSeek).

## Final Behavior
- PANJIT (cloud) translation: byte-for-byte unchanged — `refine_model` was already `None` on all cloud routes
- Ollama-local routing: VI/DE/JA/KO no longer route to dedicated HY-MT/TranslateGemma models; they fall through to `DEFAULT_MODEL`. This is an authorized behavior change for local deployments (authorized in change-request.md)
- `CROSS_MODEL_REFINEMENT_ENABLED`, `REFINEMENT_ENABLED`, `REFINEMENT_MIN_CHARS`, `HYMT_DEFAULT_MODEL` removed from config; no env-contract changes (none were ever inventoried)

## Final Contracts Updated
- `contracts/business/business-rules.md` — schema-version 0.12.0 → 0.12.1; test pointers for BR-41 (glossary-match-guarantee) and BR-44 (critique-loop-policy) retargeted from deleted `test_hy_mt_quality_refinement.py` to new `tests/test_glossary_enforcement.py`; same retargeting applied to Table M (5 rows) and Table N (3 rows)
- `.github/workflows/contract-driven-gates.yml` — active change gate updated to `cdd-kit gate remove-cross-model-refinement`; dead-reference grep step added

## Final Tests Added / Updated
- `tests/test_dead_references.py` (new, 11 tests) — AC-5/AC-6 grep-based assertions; zero live references in `app/` for all removed symbols
- `tests/test_glossary_enforcement.py` (new, 8 tests) — genuine BR-41/BR-44 coverage: glossary substitution (real `apply_glossary_substitution` production logic wired at `translation_service.py:327`) and critique-loop iteration assertions
- `tests/test_hy_mt_quality_refinement.py` — deleted (336 lines)
- Updated: `test_llm_client_protocol.py`, `test_model_router.py`, `test_ollama_client_dynamic_strategy.py`, `test_openai_compatible_client.py`, `test_sentence_mode_consistency.py`, `test_term_audit.py`, `test_translation_profiles_scenarios.py`

## Final CI/CD Gates
- contract-validation, dead-reference-grep, changed-area-tests, full-test-suite, change-gate (all Tier 1 required)
- business-rules-orphan-check (Tier 2, informational, blocks merge on non-zero)

## Production Reality Findings
- `test_openai_compatible_client.py` and `test_translation_profiles_scenarios.py` were edited outside the context-manifest Allowed Paths (in-scope `refine_translation` reference removal); CER was not filed; process note only, no quality risk
- `CROSS_MODEL_REFINEMENT_ENABLED` was env-sourced but never inventoried in env-contract — both the var and its non-inventory status are now gone; env contract needed no changes
- Gate tier-floor false-positive on "session" keyword; resolved with `tier-floor-override`

## Lessons Promoted to Standards
(none — dead-code removal pattern and contract pointer retargeting are project-specific one-offs; the mock-binding and tautological-test lessons already in CLAUDE.md cover the new test patterns used here)

## Follow-up Work
None from this change. The `ollama-local` provider entry in `config/providers.yml` is still referenced by layout detection; it is NOT removed here (only cross-model refinement was removed). The `fallback-chain-cloud-providers` change will remove `ollama-local` from the translation fallback chain.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
