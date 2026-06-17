---
change-id: p1-prompt-i18n-numctx
schema-version: 0.1.0
last-changed: 2026-06-17
risk: medium
tier: 3
---

# Test Plan: p1-prompt-i18n-numctx

## Acceptance Criteria → Test Mapping

| criterion id | test family | test name | test file path | tier |
|---|---|---|---|---|
| AC-1 | unit | test_template_selected_for_en_zhtw_ja | tests/test_context_prompt_i18n.py | 1 |
| AC-2 | unit | test_unlisted_lang_falls_back_to_en | tests/test_context_prompt_i18n.py | 1 |
| AC-3 | unit | test_immediate_and_deferred_use_same_template | tests/test_context_prompt_i18n.py | 1 |
| AC-4 | unit | test_general_num_ctx_env_overrides_independently | tests/test_context_prompt_i18n.py | 1 |
| AC-5 | unit | test_translation_num_ctx_env_overrides_independently | tests/test_context_prompt_i18n.py | 1 |
| AC-6 | unit | test_num_ctx_fallback_chain_to_ollama_then_default | tests/test_context_prompt_i18n.py | 1 |
| AC-7 | unit | test_only_ollama_num_ctx_set_backward_compat | tests/test_context_prompt_i18n.py | 1 |
| AC-8 | contract | cdd-kit validate (env.schema.json) | n/a (command) | 1 |

Notes for AC-4..AC-7: set env vars then `importlib.reload(app.backend.config)` (constants
evaluate once at import); restore env + reload in teardown to avoid cross-test leakage.

## Test Families Required

Mark all that apply: **unit** / **contract** / **integration** (396-test baseline via full phase)

## Test Execution Ladder

| phase | required | command source | target | max failures | result artifact |
|---|---:|---|---|---:|---|
| collect | yes | cdd-kit test select | tests/test_context_prompt_i18n.py | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | tests/test_context_prompt_i18n.py | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | tests/ | 1 | test-evidence.yml |
| contract | yes (env affected) | cdd-kit validate | env.schema.json | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | tests/ (396 baseline) | 1 | test-evidence.yml |

## Test Update Contract

The approved place to record that an existing test must change because the
accepted spec or contract changed. This is not a waiver: a still-valid test that
fails must be fixed, not relisted here.

| existing test | action | reason |
|---|---|---|
| (none) | n/a | No existing test asserts the hardcoded zh-TW prompt or single-source NUM_CTX; backward compat preserved |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Context-detection trigger conditions; `build_strategy` / `StrategyDecision` shape.
- `translate_texts` / `translate_blocks_batch` signatures.
- UI / API routes.

## Notes

- New file `tests/test_context_prompt_i18n.py` holds all 7 unit tests (prompt i18n + NUM_CTX).
- AC-3 verifies both call sites resolve via the shared helper; assert on the helper return
  (and that the deferred path imports the same helper), not on a live LLM call.
- NUM_CTX tests must reload `app.backend.config` after mutating env (import-time constants).
