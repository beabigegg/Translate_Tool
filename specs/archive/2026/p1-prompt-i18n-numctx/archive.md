---
change-id: p1-prompt-i18n-numctx
archived: 2026-06-17
final-status: done
---

# Archive — p1-prompt-i18n-numctx

## Change Summary

This change addressed two independent localization and configuration gaps. The context-detection prompt used by both the immediate path (`orchestrator._detect_document_context`) and the deferred path (`translation_service`) was hardcoded in zh-TW. A shared `_get_context_detection_prompt(target_lang)` helper was added to a new leaf module (`app/backend/services/context_prompts.py`) supporting en/zh-TW/ja templates with en fallback for unlisted languages. Separately, the single `OLLAMA_NUM_CTX` env var was split into `GENERAL_NUM_CTX` (default 4096) and `TRANSLATION_NUM_CTX` (default 3072) with a `specific → OLLAMA_NUM_CTX → default` fallback chain, preserving backward compatibility for existing deployments.

## Final Behavior

- `_detect_document_context` accepts a `target_lang` parameter and selects the matching language template from the shared helper.
- Both call sites (orchestrator immediate path, translation_service deferred path) use the same `_get_context_detection_prompt` from `context_prompts.py`.
- Unlisted target languages fall back to the English template (no zh-TW forced).
- `GENERAL_NUM_CTX` and `TRANSLATION_NUM_CTX` can be tuned independently via env vars; setting only `OLLAMA_NUM_CTX` continues to apply to both (AC-7 backward compat).

## Final Contracts Updated

- `contracts/env/env-contract.md` v0.2.0 — added GENERAL_NUM_CTX (default 4096), TRANSLATION_NUM_CTX (default 3072), OLLAMA_NUM_CTX (fallback only, no default); fallback chain documented.
- `contracts/env/.env.example.template` — commented entries for all three vars with defaults.
- `contracts/env/env.schema.json` — string properties with positive-int pattern for all three vars.

Evidence: `agent-log/backend-engineer.yml` → `contracts-touched`, `agent-log/contract-reviewer.yml` → `findings`.

## Final Tests Added / Updated

- `tests/test_context_prompt_i18n.py` — 7 unit tests covering AC-1..AC-7:
  - `test_template_selected_for_en_zhtw_ja` (AC-1)
  - `test_unlisted_lang_falls_back_to_en` (AC-2)
  - `test_immediate_and_deferred_use_same_template` (AC-3)
  - `test_general_num_ctx_env_overrides_independently` (AC-4)
  - `test_translation_num_ctx_env_overrides_independently` (AC-5)
  - `test_num_ctx_fallback_chain_to_ollama_then_default` (AC-6)
  - `test_only_ollama_num_ctx_set_backward_compat` (AC-7)
- AC-8 covered by `cdd-kit validate` (14 env vars checked, gate passes).
- Full suite: 403 passed / 0 failed (396 baseline + 7 new).

Evidence: `agent-log/qa-reviewer.yml` → `ac-coverage`, `test-evidence.yml`.

## Final CI/CD Gates

| gate | result |
|---|---|
| contract-validate (`cdd-kit validate --contracts`) | passed — 14 env vars, 22 endpoints |
| pytest full suite | passed — 403/0/0 |
| full regression | passed — 403/0/0 |
| test-evidence.yml phases | collect / targeted / changed-area / full — all passed |
| cdd-kit gate | PASSED |

No new CI workflow steps added; existing `contract-and-fast-tests` + `full-regression` jobs cover this change.

## Production Reality Findings

One deviation from the implementation plan: the helper was placed in `app/backend/services/context_prompts.py` (leaf module) rather than inline in `orchestrator.py` as originally planned in IP-1. The `translation_service → orchestrator → docx_processor → translation_service` circular import was discovered during backend-engineer phase and resolved via the approved fallback (leaf module with zero `app.backend` imports). Both orchestrator and translation_service import from `context_prompts.py`. The `_CONTEXT_DETECTION_PROMPTS` dict is re-exported from orchestrator for any callers using `from orchestrator import _CONTEXT_DETECTION_PROMPTS`.

The NUM_CTX tests require `importlib.reload(app.backend.config)` after mutating `os.environ` because `GENERAL_NUM_CTX` / `TRANSLATION_NUM_CTX` are evaluated once at module import time. This was anticipated in the test plan.

No gate failures, no regressions.

## Lessons Promoted to Standards

None. All durable behaviors (env contract structure, Deployment Sync Policy, fallback chain) are already captured in `contracts/env/env-contract.md`. The circular-import resolution (leaf module) is a one-off implementation detail; the importlib.reload test pattern is test-local. No new cross-change guidance warrants a CLAUDE.md entry.

## Follow-up Work

None recorded.

---

*This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.*
