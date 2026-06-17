---
change-id: p1-cloud-providers
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-cloud-providers

## Objective

Make OpenAI-compatible cloud LLM endpoints the primary translation path by adding
`OpenAICompatibleClient` (implements the existing `LLMClient` Protocol over
`/v1/chat/completions` via `requests`), externalizing provider + routing config
into a new `config/providers.yml` loaded by `config.py` with `${VAR:-default}` env
interpolation, replacing the hardcoded `model_router._ROUTING_TABLE` with
config-driven resolution, walking an ordered `fallback_chain` on primary failure,
and recording the provider that actually produced the result on `JobStatus.provider`
and `/route-info`. Ollama is demoted to a fallback (`ollama-local`) but remains the
default path when `providers.yml` is absent / unreadable / all-disabled
(backward-compatible). Delivers AC-1..AC-8 (see change-classification.md).

## Execution Scope

### In Scope
- New `OpenAICompatibleClient` Protocol impl (`app/backend/clients/openai_compatible_client.py`) + export in `app/backend/clients/__init__.py`.
- New `config/providers.yml` + committed secret-free `config/providers.yml.example`.
- `config.py`: `load_providers_config()` with `${VAR}` / `${VAR:-default}` interpolation; unresolved var disables provider (BR-17).
- `model_router.py`: remove `_ROUTING_TABLE` / `_DEFAULT_ROUTE`; config-driven `(model, provider, profile_id, model_type)` resolution; carry `provider` in route decision; preserve existing public signatures (`resolve_route`, `resolve_route_groups`, `get_route_info`).
- Fallback chain in orchestrator (`process_files`): per-job ordered walk, max one attempt per provider, first success wins, record winning provider ID.
- Additive `provider: Optional[str] = None` on `JobRecord` (job_manager) and `JobStatus` (schemas); plumb through `job_status` route and `/route-info` (`RouteInfoEntry`).
- Contract docs are already updated by contract-reviewer — implementation must conform, not re-edit (see Contract Updates).
- New/updated tests per test-plan.md (TDD: failing first).

### Out of Scope (do NOT implement here)
- Multi-target per-language precise routing / `routing.rules` consumption (`p1-provider-routing`). Schema must tolerate `routing.rules` but this change consumes only `routing.default` + `fallback_chain`.
- Observability / metrics endpoint (`p1-observability-metrics`).
- `DeepLClient` (P3-8).
- Async HTTP — stay sync on `requests` (`httpx` is NOT a dependency).
- Any frontend change, DB schema change, or new env var in code beyond those already in `.env` / `.env.example.template` (AC-8).
- Refactoring any file not in the File-Level Plan. No opportunistic cleanup of `OllamaClient` or other `OllamaClient` import sites.

## Execution Order (TDD — failing tests first)

Backend-engineer MUST follow this order. Do not write any source change before the `targeted` phase records the new tests failing.

1. Create `config/providers.yml` and `config/providers.yml.example` (secret-free) — schema per design.md Key Decisions (`providers:` list of `{id,type,enabled,base_url,api_key,models,role?}`, `routing.default {model,provider,profile}`, `fallback_chain` ordered ID list; `routing.rules` schema-tolerated, not consumed). Two providers active: `panjit`, `ollama-local`; `deepseek` present but `enabled: false`. `providers.yml.example` uses `${VAR}` placeholders only; the working `providers.yml` is NOT committed with real keys.
2. Confirm `contracts/env/.env.example.template` already declares the 5 vars (it does — lines 22-28). No edit needed.
3. Write FAILING tests (do not implement yet): `tests/test_openai_compatible_client.py`, `tests/test_provider_fallback.py` (both new); extend `tests/contract/test_llm_client_protocol.py`, `tests/test_model_router.py`, `tests/test_model_config_api.py` with the class/test names listed in test-plan.md "Test names per file".
4. Run `cdd-kit test run p1-cloud-providers --phase collect --command "<test-plan.md collect command>"` then `--phase targeted --command "<test-plan.md targeted command>"`; targeted MUST record failures before implementation.
5. Implement IP-1..IP-8 below (order: client -> config loader -> router -> job_manager/schemas/routes -> orchestrator fallback).
6. Run `--phase changed-area`, `--phase contract`, `--phase full` (commands in test-plan.md ladder); all must pass. Full target: 306+ passing, no new failures.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | clients | Create `OpenAICompatibleClient` implementing all 6 `LLMClient` methods via `requests` POST `/v1/chat/completions` (non-streamed); `translate_batch` = sequential `translate_once`; `refine_translation` = one completion with source+draft; `health`/`list_models` probe `/v1/models`; `unload()` no-op `(True, "no-op")`. API key from constructor (sourced from env via config), never literal in source. Set explicit timeouts (see Known Risks). Export in `clients/__init__.py`. | backend-engineer |
| IP-2 | config | Add `load_providers_config()` to `config.py`: read `config/providers.yml`, expand `${VAR}` / `${VAR:-default}` via `os.environ.get` + literal fallback, return parsed provider list. Missing/unresolved required var -> provider disabled (do NOT raise, do NOT emit literal `${VAR}`). File absent / unreadable / malformed / all-disabled -> return signal that callers fall back to Ollama-only (AC-3, BR-13, BR-17). | backend-engineer |
| IP-3 | services/model_router | Remove `_ROUTING_TABLE` and `_DEFAULT_ROUTE`. Resolve `(model, provider, profile_id, model_type)` from `ProviderConfig` (`routing.default`). Add `provider` to `RouteDecision` and `RouteGroup` and to `get_route_info()` per-target dicts. Preserve public signatures of `resolve_route`, `resolve_route_groups`, `get_route_info` and the insertion-order grouping + cross-model refiner skeleton (AC-4, AC-7). | backend-engineer |
| IP-4 | services/job_manager | Add `provider: Optional[str] = None` to `JobRecord` (after `term_summary`, line ~56). Set it from the orchestrator's winning provider on success; leave `None` on failure (BR-16). Surface `provider` in any status dict path. | backend-engineer |
| IP-5 | api/schemas | Add `provider: Optional[str] = None` to `JobStatus` and `provider: Optional[str] = None` to `RouteInfoEntry` (additive, backward-compatible — AC-6, AC-7). | backend-engineer |
| IP-6 | api/routes | In `job_status` (lines 183-241): read `job.provider` under lock, pass to `JobStatus(...)`. In `route_info` (lines 95-99): `get_route_info` now returns `provider`, passed through `RouteInfoEntry(**entry)` unchanged (AC-6, AC-7). | backend-engineer |
| IP-7 | processors/orchestrator | Replace the hardcoded `OllamaClient(...)` construction at `process_files` (currently `orchestrator.py:395` — VERIFY line on read, it may shift) with a provider-resolving build: consult `load_providers_config()` + the route group's resolved provider to build `OpenAICompatibleClient` or `OllamaClient`. On primary failure (connection/timeout/auth per BR-15) walk `fallback_chain`, one attempt each, first success wins; record winning provider ID for `JobRecord.provider`. If config absent/all-disabled, build `OllamaClient` exactly as today and record provider `"ollama-local"`. Return the winning provider ID up to `job_manager`. | backend-engineer |
| IP-8 | tests | Author/extend the 5 test files per test-plan.md (failing-first); cover Protocol conformance, request/response, config loading + interpolation, secret non-emission, config-driven routing, fallback chain, offline/timeout/auth, provider attribution, JobStatus provider shape + None default. | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| design.md | Key Decisions: providers.yml schema, env-var interpolation, fallback chain semantics, OpenAICompatibleClient, model_router refactor | implementation constraints |
| design.md | Migration / Rollback | absent/disabled-config fallback + secret handling |
| test-plan.md | AC→test mapping + "Test names per file" + Test Execution Ladder | exact tests to write + phase commands |
| test-plan.md | Test Update Contract | which existing tests to update vs extend |
| ci-gates.md | Required Gates table + secret-scan gate | verification commands / merge eligibility |
| contracts/business/business-rules.md | BR-4, BR-12..BR-17, Table C | routing + fallback + attribution + secret semantics |
| contracts/api/api-contract.md | JobStatus (provider), RouteInfoEntry (provider) | API field shape |
| contracts/env/env-contract.md + .env.example.template (lines 22-28) | PANJIT_LLM_BASE_URL, PANJIT_API, DEEPSEEK_BASE_URL, DEEPSEEK_API, DEEPSEEK_ENABLED | env var names / secret rules |
| app/backend/clients/base_llm_client.py | `LLMClient` Protocol (6 methods) | client method surface |
| app/backend/clients/ollama_client.py | `OllamaClient` (reference impl pattern, `requests` usage) | implementation pattern only — do not edit |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| config/providers.yml | create | provider registry (panjit + ollama-local enabled, deepseek `enabled: false`); references env vars via `${VAR}`. NOT committed with real keys. |
| config/providers.yml.example | create | secret-free template, `${VAR}` placeholders only; this file IS committed. |
| app/backend/clients/openai_compatible_client.py | create | `LLMClient` impl over `requests` + `/v1/chat/completions`; `unload()` no-op; explicit timeouts. |
| app/backend/clients/__init__.py | modify | export `OpenAICompatibleClient` (currently empty file). |
| app/backend/config.py | modify | add `load_providers_config()` + `${VAR:-default}` expansion; provider dataclass/struct. No edit to existing constants. |
| app/backend/services/model_router.py | modify | remove `_ROUTING_TABLE`/`_DEFAULT_ROUTE` (lines 29-36); config-driven resolve; add `provider` to `RouteDecision` (40-46), `RouteGroup` (49-57), `get_route_info` dict (115-131). Keep public signatures. |
| app/backend/services/job_manager.py | modify | add `provider` to `JobRecord` (~line 56); set winning provider from `process_files` return in `_run_job` (290-319). |
| app/backend/api/schemas.py | modify | add `provider` to `JobStatus` (14-30) and `RouteInfoEntry` (120-125). |
| app/backend/api/routes.py | modify | `route_info` (95-99) passthrough; `job_status` (183-241) read `job.provider` under lock + pass to `JobStatus`. |
| app/backend/processors/orchestrator.py | modify | replace hardcoded `OllamaClient(...)` at ~line 395 with provider-resolved client + fallback walk; return winning provider ID (changes `process_files` return tuple — update `job_manager` caller accordingly). |
| tests/test_openai_compatible_client.py | create | Protocol conformance, translate/refine/health/list/unload, config loading + interpolation, secret non-emission (test-plan.md names). |
| tests/test_provider_fallback.py | create | fallback chain, offline/timeout/auth, attribution, JobStatus provider shape (test-plan.md names). |
| tests/test_model_router.py | modify | add config-driven routing class; update/remove hardcoded-table cases (Test Update Contract). |
| tests/test_model_config_api.py | modify | add `/route-info` provider-field assertions. |
| tests/contract/test_llm_client_protocol.py | modify | add `OpenAICompatibleClient` to conformance set + JobStatus provider-field class. |

> Note: changing the `process_files` return tuple (IP-7) requires touching its only in-scope caller, `job_manager._run_job` (line 290). Both files are in scope. Do not change any other caller; there are none for the provider field.

## Contract Updates

All contract files below are ALREADY updated by contract-reviewer (version 0.2.0). Implementation must conform to them; do NOT re-edit contract prose.

- API: `contracts/api/api-contract.md` — `JobStatus.provider` and `RouteInfoEntry.provider` (AC-6, AC-7). Conform.
- CSS/UI: none (no frontend).
- Env: `contracts/env/env-contract.md` + `.env.example.template` lines 22-28 — 5 vars documented; secrets stay in `.env` only (BR-17). Conform.
- Data shape: `JobStatus` gains optional `provider` (additive, default null). Conform.
- Business logic: `contracts/business/business-rules.md` BR-4, BR-12..BR-17, Table C — config-driven routing + fallback + attribution + secret rules. Implement to satisfy.
- CI/CD: none.

## Test Execution Plan

Targets below are bare files (selector-valid). Required phases: collect, targeted, changed-area, plus contract + full (triggers apply — see test-plan.md ladder + ci-gates.md). Backend-engineer records evidence via `cdd-kit test run p1-cloud-providers --phase <phase> --command "..."`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/contract/test_llm_client_protocol.py | `OpenAICompatibleClient` satisfies Protocol + isinstance passes |
| AC-1, AC-2 | tests/test_openai_compatible_client.py | translate_once/batch/refine return `(ok, ...)`; mocked Panjit + DeepSeek responses parse |
| AC-3 | tests/test_openai_compatible_client.py | `${VAR:-default}` interpolation; unresolved var disables provider; no literal key in request body |
| AC-4 | tests/test_model_router.py | routing reads providers.yml; hardcoded table gone; `provider` present in route decision |
| AC-5 | tests/test_provider_fallback.py | primary offline/timeout/auth -> next provider; first success wins; all-fail -> job fails |
| AC-6 | tests/test_provider_fallback.py + tests/contract/test_llm_client_protocol.py | winning/fallback provider recorded on JobStatus; `provider` optional, defaults None |
| AC-7 | tests/test_model_config_api.py | `/route-info` returns `provider` matching routing decision |
| AC-8 | tests/contract/test_llm_client_protocol.py | JobStatus schema additive/backward-compatible; no frontend/DB/new-env assertions hold |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Use `requests` only — `httpx` is not a dependency (confirmed: `requests` used throughout `ollama_client.py`, `wikidata_lookup.py`).
- No hardcoded API keys in source; all keys come from `.env` via `config.py`. Working `config/providers.yml` must not be committed with real keys; only `config/providers.yml.example` is committed.
- `unload()` must be a no-op for `OpenAICompatibleClient` (cloud providers have no unload concept).
- Fallback: max one attempt per provider per job; record provider ID at the point of first success (BR-14, BR-16).
- If `providers.yml` is absent / unreadable / malformed / all-disabled, fall back to the existing `OllamaClient` path unchanged and record provider `"ollama-local"` (BR-13, Table C row 5).
- Do NOT start implementation before the `targeted` phase records the new tests failing.
- Do NOT refactor anything outside the File-Level Plan (no scope creep).

## Known Risks

- `orchestrator.py:395` is the client injection point per design.md, but line numbers shift as you edit. VERIFY the exact `OllamaClient(...)` construction site on read (it is inside `process_files`, after the `extraction_only` setup). Do not assume the literal line.
- Sync HTTP fallback: a hanging primary consumes its full read timeout before the chain advances. Set explicit, bounded timeouts in `OpenAICompatibleClient` (e.g. ~120s connect-equivalent + ~300s read for long translations; reuse `config.TimeoutConfig` shape where sensible) and document the chosen values in a code comment so fallback latency stays bounded.
- `routing.rules` is schema-tolerated but unconsumed here; it is owned by `p1-provider-routing`. Parse-and-ignore it; do not implement rule matching, or you create drift with the downstream change.
- `process_files` return-tuple change (IP-7) is a cross-file contract between orchestrator and job_manager — keep both edits in the same change; the full-regression gate will catch a mismatch.
- `.cdd/code-map.yml` was present and current (digest `f3b6b10…`, generated 2026-06-17) and was used to scope line ranges; no stale-map risk.
- secret-scan gate (ci-gates.md) greps for literal `PANJIT_API`/`DEEPSEEK_API` values >=20 chars — ensure providers.yml uses `${VAR}` only or the gate blocks merge.
