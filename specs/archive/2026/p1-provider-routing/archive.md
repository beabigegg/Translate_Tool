# Archive — p1-provider-routing

## Change Summary

`p1-provider-routing` replaced the hardcoded `_OLLAMA_ROUTING_TABLE` dict in `model_router.py` with a config-driven lookup against `routing.rules` in `config/providers.yml`. It also fixed `resolve_route_groups()` to resolve each `target_lang` in a batch independently instead of routing the entire batch by `targets[0]`. The change is the second P1 improvement after `p1-cloud-providers`, which introduced the providers.yml registry; this change activates the `routing:` section of that registry for per-language dispatch.

## Final Behavior

- `_resolve_from_config()` checks `routing.rules[target_lang]` first; on a miss (or when `routing.rules` is absent), falls back to `routing.default` — no exception (BR-19).
- `resolve_route_groups()` cloud branch iterates all `target_lang` values independently and groups by `(model, profile_id, model_type, provider)` tuple, producing 1–N RouteGroups for mixed-language batches (BR-18).
- Legacy Ollama path (`provider_config is None`) is unchanged; `_OLLAMA_ROUTING_TABLE` remains as a backward-compatible fallback (BR-4, Table D row 4).
- `config/providers.yml` `routing.rules` covers Vietnamese, German, Japanese, Korean — all languages previously in the hardcoded dict — so no language silently falls back without explicit intent.
- Korean cloud path routes to `panjit gpt-oss:120b`; legacy Ollama path still routes Korean to TranslateGemma.

## Final Contracts Updated

- `contracts/business/business-rules.md` schema-version 0.3.0 (was 0.2.0)
  - BR-4 revised: "language-keyed map" wording; legacy `_OLLAMA_ROUTING_TABLE` scoped to no-`provider_config` fallback
  - BR-18 added: per-target-language-dispatch rule
  - BR-19 added: unmapped-language-fallback rule
  - Table D added: 4-row config-driven per-language routing decision table

## Final Tests Added / Updated

Source: `agent-log/backend-engineer.yml`

- `TestProviderRoutingRules` (4 tests) — AC-1, AC-2, AC-5 (routing.rules consumed; config-only rule change; default fallback)
- `TestResolveRouteGroupsPerLanguage` (4 tests) — AC-3, AC-4 (per-target independent resolution; mixed batch grouping)
- `TestLegacyOllamaPath` (3 tests) — AC-6 regression (legacy Ollama path unmodified)
- Total: 361 passed, 0 failed (350 baseline + 11 new)
- All 5 ladder phases passed: collect, targeted, changed-area, contract, full

## Final CI/CD Gates

Source: `ci-gates.md`

- `contract-validate` (Tier 1, required) — `cdd-kit validate --contracts`
- `secret-scan` (Tier 1, required) — grep for literal API keys in `*.yml`
- `routing-unit-tests` (Tier 1, required) — `pytest tests/test_model_router.py -x -q`
- `full-test-suite` (Tier 1, required) — `pytest tests/ -x -q`
- `full-regression` (Tier 2, informational) — `pytest tests/ -q`
- `.github/workflows/contract-driven-gates.yml` updated: `cdd-kit gate p1-provider-routing` added alongside `cdd-kit gate p1-cloud-providers`

## Production Reality Findings

- **BR-4 shape discrepancy**: Both `implementation-planner` and `backend-engineer` independently flagged that the original BR-4 prose described `routing.rules` as "a list of `{lang, model, provider, profile}` entries", but the test-plan fixture and implementation used a language-keyed map. Contract-reviewer reconciled BR-4 to the correct map shape; the discrepancy was introduced when the rule was originally written without an implementation reference. Resolution: test-plan.md fixture shape is the executable spec; prose must match it.
- **CER-001 consumer check**: implementation-planner confirmed that the real callers of `resolve_route_groups()` are `api/routes.py` and `job_manager.py` (not `orchestrator.py` or `translation_service.py` as initially suspected). Both were already multi-group safe — no consumer change was needed.
- **Korean routing**: No panjit-equivalent of TranslateGemma exists. Cloud path routes Korean to `panjit gpt-oss:120b`; legacy Ollama path retains `translategemma:4b`. Decision documented in BR-4 / Table D row 4.

## Lessons Promoted to Standards

All durable rules from this change are product/system behavior and were written directly into `contracts/business/business-rules.md` (schema-version 0.3.0) during the change:
- BR-4 revised wording → `contracts/business/business-rules.md`
- BR-18 per-target-language-dispatch → `contracts/business/business-rules.md`
- BR-19 unmapped-language-fallback → `contracts/business/business-rules.md`
- Table D config-driven per-language routing → `contracts/business/business-rules.md`

No new CLAUDE.md guidance entries are needed: the CER-001 consumer-check pattern and the map-vs-list fixture discipline are already implicit in CDD workflow; no novel agent behavior guidance emerged.

## Follow-up Work

- `p1-observability-metrics` depends on `p1-provider-routing` (now complete) — unblocked.
- 5 remaining P1 changes in `specs/changes/`: `p1-sentence-mode-fix`, `p1-term-state-machine`, `p1-prompt-i18n-numctx`, `p1-font-lru-cache`, `p1-observability-metrics`.

---

*This archive is historical evidence. Current requirements live in contracts/ and active project guidance.*
