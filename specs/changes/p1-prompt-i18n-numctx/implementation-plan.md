---
change-id: p1-prompt-i18n-numctx
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-prompt-i18n-numctx

## Objective

Deliver two co-located, independent fixes inside the existing config / orchestrator /
translation_service surface:

- Part A: context-detection prompt becomes `target_lang`-aware via an i18n template
  table (en / zh-TW / ja, English fallback), applied identically on the immediate
  (`orchestrator._detect_document_context`) and deferred (`translation_service`) paths.
- Part B: `OLLAMA_NUM_CTX` splits into independently overridable `GENERAL_NUM_CTX` and
  `TRANSLATION_NUM_CTX` env vars with a `specific → OLLAMA_NUM_CTX → default` fallback
  chain (defaults 4096 / 3072), backward-compatible with deployments setting only
  `OLLAMA_NUM_CTX`. Env contract files updated; `cdd-kit validate` passes.

No public API, route, UI, or data-structure change. `build_strategy` / `StrategyDecision`,
`translate_texts`, and `translate_blocks_batch` signatures are unchanged.

## Execution Scope

### In Scope
- IP-1: add `_CONTEXT_DETECTION_PROMPTS` table + `_get_context_detection_prompt(target_lang)`
  helper in `orchestrator.py` (single source of truth for both paths).
- IP-2: thread `target_lang` into `_detect_document_context` and update both call sites
  (immediate path in `process_files`; deferred path in `translation_service.translate_texts`).
- IP-3: rewrite `config.py` lines 31-37 NUM_CTX resolution for independent env overrides.
- IP-4: update `env-contract.md`, `.env.example.template`, `env.schema.json`; re-run
  `cdd-kit validate`.

### Out of Scope
- Context-detection trigger conditions (`CONTEXT_DETECTION_ENABLED`, `QWEN_CONTEXT_FLOW_ENABLED`).
- `build_strategy` / `StrategyDecision` shape; `detect_translation_scenario` behavior.
- Any change to `OLLAMA_NUM_CTX` legacy semantics (must remain a fallback).
- Refactoring `translate_texts`, `translate_blocks_batch`, or the deferred-context
  system-prompt swap logic beyond replacing the hardcoded prompt string.
- Locale fuzzy matching / region collapsing: exact-match else `en` (per classification
  Clarifications; `zh-CN` and other zh variants default to `en`).
- Reading/modifying `ollama_client.py` (CER-001 is pending and not required: NUM_CTX is
  consumed via `MODEL_TYPE_OPTIONS` which already reads the module-level constants).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | orchestrator i18n table + helper | Add `_CONTEXT_DETECTION_PROMPTS` dict (keys `en`, `zh-TW`, `ja`) and `_get_context_detection_prompt(target_lang)` with exact-match-else-`en` fallback | backend-engineer |
| IP-2 | both prompt call sites | Add `target_lang` param to `_detect_document_context`; route both immediate and deferred prompts through the IP-1 helper | backend-engineer |
| IP-3 | config NUM_CTX resolution | Replace lines 31-37 with independent `GENERAL_NUM_CTX` / `TRANSLATION_NUM_CTX` env resolution + `OLLAMA_NUM_CTX` fallback + defaults | backend-engineer |
| IP-4 | env contract files | Add two vars + fallback-chain docs to `env-contract.md`, `.env.example.template`, `env.schema.json`; document `OLLAMA_NUM_CTX` as backward-compat fallback | backend-engineer / contract-reviewer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-8 | acceptance scope |
| change-classification.md | Required Contracts → Env | env file update obligations |
| change-classification.md | Clarifications (exact-match-else-en; defaults 4096/3072) | template + default constraints |
| change-request.md | Known Context (file:line pointers) | exact edit locations |
| test-plan.md | AC→test mapping table | tests to write/run |
| ci-gates.md | Required Gates table | verification commands |
| contracts/env/env-contract.md | env inventory table + Deployment Sync Policy | IP-4 row format + 3-file sync rule |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/processors/orchestrator.py | edit | Add module-level `_CONTEXT_DETECTION_PROMPTS` and `_get_context_detection_prompt`. Existing zh-TW string (lines 297-301) becomes the `zh-TW` template value; author `en` (default/fallback) and `ja` templates with the same instruction semantics. Each template ends with the sample appended (`...只輸出描述...\n\n{sample}` shape). |
| app/backend/processors/orchestrator.py | edit | `_detect_document_context` (lines 291-311): add `target_lang: str` parameter; build prompt via `_get_context_detection_prompt(target_lang).format(sample=sample)` (or string-concat the helper-returned prefix + sample). Update docstring (drop "Chinese prompt"). |
| app/backend/processors/orchestrator.py | edit | Immediate call site (line 536): pass target_lang as `targets[0] if targets else ""` (same value already used for deferred at line 549) into `_detect_document_context(...)`. |
| app/backend/services/translation_service.py | edit | Deferred path (lines 245-248): replace the hardcoded zh-TW `_detect_prompt` literal with a call to the IP-1 helper, keyed on the already-resolved `_ctx_target` (line 244): `_detect_prompt = _get_context_detection_prompt(_ctx_target).format(sample=_ctx_sample)`. Import the helper from `app.backend.processors.orchestrator`. Confirm no new circular import (orchestrator already imports services; helper is leaf-level — if import cycle arises, place the table+helper in a small leaf module instead and import from both — note as a risk). |
| app/backend/config.py | edit | Lines 31-37: resolve `GENERAL_NUM_CTX` = `int(os.environ["GENERAL_NUM_CTX"])` if set else `int(OLLAMA_NUM_CTX env)` if set else `4096`; `TRANSLATION_NUM_CTX` analogous with default `3072`. Keep `OLLAMA_NUM_CTX` module constant for downstream imports (it is imported by `ollama_client.py` per code-map line 105). Preserve `MODEL_TYPE_OPTIONS` references to the two constants (lines 39-44+). |
| contracts/env/env-contract.md | edit | Add two rows to the inventory table (scope backend, all envs, required no, secret no, defaults 4096 / 3072, validation "positive int", restart required yes, failure behavior describing fallback). Note `OLLAMA_NUM_CTX` remains a backward-compat fallback. |
| contracts/env/.env.example.template | edit | Add an Ollama context-window section with `OLLAMA_NUM_CTX` (legacy), `GENERAL_NUM_CTX=4096`, `TRANSLATION_NUM_CTX=3072` commented/example values. |
| contracts/env/env.schema.json | edit | Add `GENERAL_NUM_CTX`, `TRANSLATION_NUM_CTX`, and (if absent) `OLLAMA_NUM_CTX` string properties with descriptions noting the fallback chain. |
| tests/test_context_prompt_i18n.py | create | New unit test file (see test-plan.md). |

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: add `GENERAL_NUM_CTX` (default 4096) and `TRANSLATION_NUM_CTX` (default 3072) to all
  three env files; document fallback chain (specific → `OLLAMA_NUM_CTX` → default) and
  `OLLAMA_NUM_CTX` as backward-compat fallback. Follow `env-contract.md` Deployment Sync
  Policy (all three files in this change). Re-run `cdd-kit validate`.
- Data shape: none (`StrategyDecision` / `build_strategy` unchanged — non-goal).
- Business logic: `contracts/business/business-rules.md` — review only. Update only if an
  existing rule documents the context-detection prompt language; otherwise no change
  (contract-reviewer confirms; record decision in agent-log).
- CI/CD: none.

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_context_prompt_i18n.py | helper returns matching localized template for en / zh-TW / ja |
| AC-2 | tests/test_context_prompt_i18n.py | unlisted lang (ko, fr) returns the en template |
| AC-3 | tests/test_context_prompt_i18n.py | immediate and deferred paths select the same template for a given target_lang |
| AC-4 | tests/test_context_prompt_i18n.py | GENERAL_NUM_CTX env set → general value matches, translation unaffected |
| AC-5 | tests/test_context_prompt_i18n.py | TRANSLATION_NUM_CTX env set → translation value matches, general unaffected |
| AC-6 | tests/test_context_prompt_i18n.py | specific unset → OLLAMA_NUM_CTX; both unset → 4096 / 3072 |
| AC-7 | tests/test_context_prompt_i18n.py | only OLLAMA_NUM_CTX set → both constants equal it (backward compat) |
| AC-8 | cdd-kit validate | env-contract conformance passes with new vars |

Required phases: collect, targeted, changed-area (always), plus contract (env affected) and
full (final/CI). Implementation agents generate evidence with `cdd-kit test run`; full ladder
lives in test-plan.md.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Config NUM_CTX is module-level at import time; tests must reload `config` after setting
  env (e.g. `importlib.reload`) since constants are evaluated once on import.

## Known Risks

- Import-cycle risk: `translation_service` importing the helper from `orchestrator` while
  `orchestrator` already imports from `services`. If a cycle surfaces, move
  `_CONTEXT_DETECTION_PROMPTS` + `_get_context_detection_prompt` into a small leaf module
  (e.g. `app/backend/services/context_prompts.py`) and import from both call sites. This is
  the only allowed deviation from the named edit locations; record it in agent-log.
- `OLLAMA_NUM_CTX` is imported by `ollama_client.py` (code-map line 105) and re-derived as
  `OLLAMA_NUM_CTX = GENERAL_NUM_CTX` today; keep the constant defined to avoid ImportError.
- Tier-floor false-positive risk on env vocab ("config"/"endpoint"): if `cdd-kit gate`
  false-positives, apply `tier-floor-override` with written rationale (these are non-secret
  integer tuning vars).
- `.cdd/code-map.yml` was read partial (first page); all edit targets were confirmed against
  full ranges read directly from source, so map staleness does not affect this plan.
