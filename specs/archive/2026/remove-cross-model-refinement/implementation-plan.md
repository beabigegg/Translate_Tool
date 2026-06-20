---
change-id: remove-cross-model-refinement
schema-version: 0.1.0
last-changed: 2026-06-20
---

# Implementation Plan: remove-cross-model-refinement

## Objective
Delete the dead cross-model refinement path (HY-MT/TranslateGemma draft -> Qwen polish, the two-pass `REFINEMENT_*` self-refine, and the cloud-disabled `CROSS_MODEL_REFINEMENT_ENABLED` gate) from the backend without changing any observable behavior. The cloud (PANJIT / OpenAI-compatible) translation path must be byte-for-byte unchanged: it already runs with `refine_model=None`, so removing the never-taken refine branches must not alter dispatch, prompts, caching, or output.

## Execution Scope

### In Scope
- Remove the three refinement config constants and every live consumer in `app/`.
- Remove the `refine_model` field, its assignment logic, and the legacy HY-MT/TranslateGemma Ollama routing entries from `model_router.py`.
- Remove the `refine_translation` / `_build_refine_prompt` / `_build_refine_system_prompt` definitions and the `LLMClient.refine_translation` protocol method + its two implementations.
- Thread out the `refine_client` / `refine_model` / `refiner_num_ctx` parameters through orchestrator, the docx/pptx/xlsx processors, and `translation_service.translate_texts`.
- Retire `tests/test_hy_mt_quality_refinement.py`; update other tests whose assertions reference removed symbols/signatures.

### Out of Scope
- No cloud-side translate-then-critique feature (Non-goal, change-request.md).
- Do not touch the critique loop (`CRITIQUE_*`, BR-44/BR-45) — it is a separate live feature; do not confuse "self-refinement" wording in critique docs with `REFINEMENT_ENABLED`.
- No layout-detection, API endpoint, data-shape, or CI gate changes.
- Do not refactor unrelated routing/dispatch code while editing these files.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config.py | Delete `REFINEMENT_ENABLED`, `REFINEMENT_MIN_CHARS`, `CROSS_MODEL_REFINEMENT_ENABLED` + comments | backend-engineer |
| IP-2 | ollama_client.py | Delete `refine_translation`, `_build_refine_prompt`, `_build_refine_system_prompt` | backend-engineer |
| IP-3 | base_llm_client.py + openai_compatible_client.py | Remove `refine_translation` from `LLMClient` protocol and its OpenAI-compatible impl | backend-engineer |
| IP-4 | model_router.py | Remove `refine_model` field + assignment; remove HY-MT/TranslateGemma routing rows + orphaned model-name defaults | backend-engineer |
| IP-5 | orchestrator.py | Remove `refine_model`/`refiner_num_ctx` params, the refine_client build block, and all refine_client usages | backend-engineer |
| IP-6 | translation_service.py | Remove `refine_client` param + Phase 2 block + refiner cache lookup | backend-engineer |
| IP-7 | translation_helpers.py | Delete `_maybe_refine` and its config imports (verify no remaining caller first) | backend-engineer |
| IP-8 | docx/pptx/xlsx processors | Remove `refine_client` param + pass-through | backend-engineer |
| IP-9 | job_manager.py | Remove `refine_model=group.refine_model` kwarg at call site | backend-engineer |
| IP-10 | tests | Retire `test_hy_mt_quality_refinement.py`; fix orphaned references in other test files | backend-engineer |
| IP-11 | contracts | env/business contract impact (refine references in business-rules.md proof column) | contract-reviewer (NOT backend-engineer) |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-8 | acceptance criteria this plan satisfies |
| change-classification.md | Required Tests / Required Contracts | test families + env/business contract scope |
| context-manifest.md | Allowed Paths | read/write boundary |
| test-plan.md | Execution Ladder + AC->test mapping | phases to run (filled by test-strategist) |
| ci-gates.md | Required Gates table | verification commands (filled by ci-cd-gatekeeper) |
| contracts/env/env-contract.md | constant inventory | env-contract implication (see IP-1 note) |
| contracts/business/business-rules.md | lines 211-225 proof column | refine test-file references (contract-reviewer) |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/config.py | edit | Delete lines 107-112 block: `REFINEMENT_ENABLED` (108), `REFINEMENT_MIN_CHARS` (109), `CROSS_MODEL_REFINEMENT_ENABLED` (110-112) + leading comments. Leave `CONTEXT_DETECTION_ENABLED` (115) intact. |
| app/backend/clients/ollama_client.py | edit | Delete `refine_translation` (510-531), `_build_refine_prompt` (533-541), `_build_refine_system_prompt` (543-592). Keep `_smart_retry` (594+) and `_build_merged_prompt` (490-508). |
| app/backend/clients/base_llm_client.py | edit | Remove `refine_translation` protocol stub (38-47). |
| app/backend/clients/openai_compatible_client.py | edit | Remove `refine_translation` impl (167-187). |
| app/backend/services/model_router.py | edit | Remove `refine_model` field (RouteGroup, 71); in `resolve_route_groups` cloud branch drop `refine_model=None` kwarg (200); in legacy branch delete the refine_model if/else (212-217) and the `refine_model=refine_model` kwarg (223). Remove `_OLLAMA_ROUTING_TABLE` HY-MT/TGEMMA rows (43-46); remove `TGEMMA_DEFAULT_MODEL` (25) and `HYMT_DEFAULT_MODEL` import (22) iff grep shows no remaining use. See R-2 before deleting rows. |
| app/backend/processors/orchestrator.py | edit | Remove `CROSS_MODEL_REFINEMENT_ENABLED` import (15); remove `refine_model`/`refiner_num_ctx` params (358-359); delete refine_client build block (494-506); delete the deferred-context `refine_client` branch (544-553); delete the Phase-2-refiner term-inject block (667-677); drop `refine_client=refine_client` from the 4 processor calls (697, 728, 747, 761). |
| app/backend/services/translation_service.py | edit | Remove `CROSS_MODEL_REFINEMENT_ENABLED` + `REFINEMENT_MIN_CHARS` imports (12, 17); remove `refine_client` param (87) + docstring line (100); remove refiner-cache lookup (138-147); delete the entire Phase 2 block (~362-430). Verify the post-Phase-2 return path is unaffected. |
| app/backend/utils/translation_helpers.py | edit | Delete `_maybe_refine` (26-41) and remove `REFINEMENT_ENABLED`/`REFINEMENT_MIN_CHARS` imports (14-15). Grep first: if `_maybe_refine` has a live caller, report blocked. |
| app/backend/processors/docx_processor.py | edit | Remove `refine_client` param (481) and `refine_client=refine_client` arg (517). |
| app/backend/processors/pptx_processor.py | edit | Remove `refine_client` param (193) and arg (271). |
| app/backend/processors/xlsx_processor.py | edit | Remove `refine_client` param (52) and arg (147). |
| app/backend/services/job_manager.py | edit | Remove `refine_model=group.refine_model` kwarg (340). |
| tests/test_hy_mt_quality_refinement.py | delete | Entire file retired (AC-5) — but only after R-1 cleared. |
| tests/test_llm_client_protocol.py | edit | Remove `refine_translation` from protocol-signature/method-list assertions (48-50, 75, 135) and refiner mock setup (186-189). |
| tests/test_sentence_mode_consistency.py | edit | Remove `refine_client` from the `translate_texts` expected-signature assertion (265, 276). |
| tests/test_term_audit.py | edit | Remove `refine_model=None` from `RouteGroup(...)` construction (462, 516). |
| tests/test_ollama_client_dynamic_strategy.py | check | Uses HY-MT model string as a fixture (37, 45); only edit if removing routing rows breaks it. |

## Deletion Order (must follow to avoid import errors)
1. Delete `tests/test_hy_mt_quality_refinement.py` first (heaviest consumer of soon-to-vanish symbols; keeps later collect runs clean). Precondition: R-1 cleared by contract-reviewer.
2. IP-5/IP-6/IP-7/IP-8/IP-9: remove all *usages* (orchestrator, translation_service, translation_helpers, processors, job_manager) — callers before callees.
3. IP-2/IP-3: remove the `refine_translation` family from clients + protocol (now unreferenced).
4. IP-4: remove `refine_model` field + routing rows from model_router.
5. IP-1 last: delete the config constants (now no importer remains).
6. Then fix the remaining test references (IP-10 edits to the other test files).

Rationale: a constant or method deleted while a live `from ... import` still references it raises `ImportError` at collect. Removing importers first keeps every intermediate state importable.

## Post-Deletion Verification Greps (backend-engineer MUST run)
Per the shared-module promotion learning (verify all consumer imports before marking done). All must return zero hits in `app/` and `tests/` (AC-6):
- `rg -n 'CROSS_MODEL_REFINEMENT_ENABLED' app/ tests/`
- `rg -n 'REFINEMENT_ENABLED|REFINEMENT_MIN_CHARS' app/ tests/`
- `rg -n 'refine_translation' app/ tests/`
- `rg -n 'refine_client' app/ tests/`
- `rg -n 'refine_model' app/ tests/`
- `rg -n '_build_refine_prompt|_build_refine_system_prompt' app/ tests/`
- `rg -n 'refiner_num_ctx' app/ tests/`
- `rg -n 'refine_cached_keys|refiner_cached' app/ tests/` (R-5 leftover bookkeeping)
- `rg -n 'HY-MT|TranslateGemma|TGEMMA_DEFAULT_MODEL' app/ tests/`
Any remaining live hit (outside `specs/archive/`, `docs/`, `scripts/`) -> report blocked, do not paper over.

## Contract Updates
- API: none (no endpoint change; rely on `cdd-kit validate --contracts` conformance to confirm no drift).
- CSS/UI: none.
- Env: `CROSS_MODEL_REFINEMENT_ENABLED`, `REFINEMENT_ENABLED`, `REFINEMENT_MIN_CHARS` are NOT currently inventoried in `contracts/env/env-contract.md` (only `CRITIQUE_LOOP_ENABLED` exists there) and are absent from `.env.example.template`. So there is no env-contract row to delete. IMPLICATION (for contract-reviewer): `CROSS_MODEL_REFINEMENT_ENABLED` reads `os.environ.get("CROSS_MODEL_REFINEMENT_ENABLED", ...)` — it is an *undocumented* env var. Removing it is a net positive (closes an inventory gap), but contract-reviewer must confirm no env-contract validator expects it and that `tests/test_env_contract.py` still passes. backend-engineer must NOT edit env-contract.md.
- Data shape: none.
- Business logic: `contracts/business/business-rules.md` lines 211-225 list `tests/test_hy_mt_quality_refinement.py` as the proof file for several BR-44/BR-45 glossary/critique scenarios. Deleting that test file orphans those references. RESOLUTION is owned by contract-reviewer (IP-11): repoint those rows to the surviving critique/glossary test (e.g. `tests/test_translation_strategy.py` / `tests/test_fewshot_glossary.py`) or confirm coverage elsewhere. backend-engineer must NOT delete the test file until contract-reviewer has repointed/cleared these rows. See R-1.
- CI/CD: none.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_env_contract.py | passes; no import error for removed constants |
| AC-2 | tests/test_provider_fallback.py | cloud dispatch unchanged; no refine branch |
| AC-3 | tests/test_ollama_client_dynamic_strategy.py | passes without refine methods |
| AC-3 (protocol) | tests/test_llm_client_protocol.py | passes after signature-list edit |
| AC-4 | tests/test_model_router.py | groups have no refine_model; HY-MT/TGEMMA rows gone; default routing intact |
| AC-5 | tests/test_hy_mt_quality_refinement.py | absent; no collection error |
| AC-6 | (greps above) | zero live hits in app/ and tests/ |
| AC-7 | tests/test_translation_strategy.py | cloud (PANJIT) translation behavior unchanged |
| AC-8 | tests/test_term_audit.py | RouteGroup construction passes without refine_model |

(`cdd-kit test select` reads the `test file / command` column above only when test-plan.md has no mapping; each entry is a bare existing target.) Test phases — floor: collect, targeted, changed-area; full at end/CI (see test-plan.md ladder + references/sdd-tdd-policy.md). Generate evidence via `cdd-kit test select` then `cdd-kit test run --phase <phase>`; the gate validates `test-evidence.yml`. Contract phase applies (env + business contract touched, IP-11): run `cdd-kit validate`. Final gate: `cdd-kit gate remove-cross-model-refinement` (AC-8, includes API conformance).

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- backend-engineer must NOT touch `contracts/` — env/business contract edits are contract-reviewer's (IP-11). Do not delete `tests/test_hy_mt_quality_refinement.py` until contract-reviewer has cleared its business-rules.md references (R-1).
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- R-1 (HIGH): `business-rules.md` lines 211-225 cite `tests/test_hy_mt_quality_refinement.py` as the proof file for surviving BR-44/BR-45 glossary+critique scenarios. The change-request only anticipated deleting the file. Deleting it without repointing those rows orphans contract references and fails the gate. Owner: contract-reviewer. Must be resolved before IP-10's file deletion lands.
- R-2 (MEDIUM): Removing the HY-MT/TranslateGemma rows from `_OLLAMA_ROUTING_TABLE` changes the *legacy Ollama-local* routing result for Vietnamese/German/Japanese/Korean (they fall through to `_OLLAMA_DEFAULT_ROUTE` = Qwen). The cloud/PANJIT path is unaffected (it uses `_resolve_from_config`), so the byte-for-byte cloud guarantee holds. But this is a behavior change for any Ollama-local deployment. change-request.md explicitly authorizes removing these rows; confirm with test-strategist that `test_model_router.py` legacy-path assertions are updated, not silently broken.
- R-3 (LOW): `LLMClient.refine_translation` is a protocol method removed from base + both impls; `test_llm_client_protocol.py` enumerates protocol methods and will fail until edited (IP-3/IP-10). Expected test-update, not a waiver.
- R-4 (LOW): `HYMT_DEFAULT_MODEL` (config.py:26) and `TGEMMA_DEFAULT_MODEL` (model_router.py:25) become orphaned once routing rows go. Delete only after greps confirm no other live use (`scripts/`, `docs/` are out of scope and may retain references). If retained, note as harmless dead default in qa-report.
- R-5 (LOW): The Phase 2 deletion in `translation_service.py` removes `refine_cached_keys`/`refiner_cached` bookkeeping; confirm via grep that no surviving code references them after deletion.
