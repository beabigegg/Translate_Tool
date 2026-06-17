---
change-id: p1-llm-client-abstraction
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-llm-client-abstraction

## Objective
Introduce `LLMClient` as a `typing.Protocol` so `translation_service.py` and
`translation_helpers.py` depend only on a six-method provider surface
(`translate_once`, `translate_batch`, `refine_translation`, `health`,
`list_models`, `unload`). Make `OllamaClient` a structural subtype by adding
three thin alias methods, and remove every direct consumer reach-through into
`OllamaClient` private methods (`_build_no_system_payload`, `_call_ollama`,
`_is_translation_dedicated`). Behavior-preserving refactor: no translation
output change, no public-API break, no new dependency. See `design.md` Summary
and the Protocol signature table (Key Decisions).

## Execution Scope

### In Scope
- New file: `app/backend/clients/base_llm_client.py` (the Protocol).
- Modify: `app/backend/clients/ollama_client.py` (add 3 alias methods only).
- Modify: `app/backend/services/translation_service.py` (rewire to Protocol).
- Modify: `app/backend/utils/translation_helpers.py` (remove private call; type hints).
- Modify: `app/backend/clients/__init__.py` (re-export `LLMClient`).
- New test file: `tests/test_llm_client_protocol.py` (written FIRST, TDD).

### Out of Scope
- No new provider (OpenAICompatible / Panjit / DeepSeek) — owned by `p1-cloud-providers`.
- No rename/removal/signature change of any existing `OllamaClient` public method (AC-4).
- No translation-behavior change; no edits to existing regression-test assertions (AC-5).
- No governed `contracts/` artifact, API route/schema, env var, or frontend file (AC-7 — see change-classification.md).
- No new third-party dependency; only `typing.Protocol` from stdlib (AC-6).
- Do not touch other `OllamaClient` callers (`routes.py`, `docx_processor.py`, `resource_utils.py`, `orchestrator.py`) — they keep using frozen names.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-0 | tests | Write `tests/test_llm_client_protocol.py` with all rows from test-plan.md mapping; every test must FAIL before implementation | backend-engineer |
| IP-1 | clients | Create `base_llm_client.py` defining `LLMClient(Protocol)` `@runtime_checkable`, 6 methods per design.md signature table; import stdlib `typing` only | backend-engineer |
| IP-2 | clients | Add 3 alias methods to `OllamaClient`: `health()`, `list_models()`, `unload()` delegating to frozen behavior; keep all existing methods unchanged | backend-engineer |
| IP-3 | services | Rewire `translation_service.py`: type hints `OllamaClient`→`LLMClient`; replace deferred-context-detection private calls with public Protocol flow; replace `unload_model()` with `unload()` | backend-engineer |
| IP-4 | utils | Rewire `translation_helpers.py`: remove `client._is_translation_dedicated()` branch in `_maybe_refine`; type hints→`LLMClient` | backend-engineer |
| IP-5 | clients | `clients/__init__.py` re-export `LLMClient` | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | "Protocol method signatures" table (Key Decisions) | exact 6 method signatures + return types |
| design.md | "Name resolution: add aliases, do not rename" | alias delegation targets for IP-2 |
| design.md | "Private payload logic stays inside OllamaClient" + Open Risks §1 | IP-3 context-detection rewrite constraint + parity risk |
| design.md | Open Risks §2 | IP-4 `_is_translation_dedicated` removal verification |
| change-classification.md | AC-1..AC-7 | acceptance criteria the change must satisfy |
| change-classification.md | "Tasks Not Applicable" + AC-7 | non-goals (no contract/API/env/UI/CI change) |
| test-plan.md | "Acceptance Criteria → Test Mapping" table | exact test node ids to author in IP-0 |
| test-plan.md | Stop Rules | failure-handling discipline during runs |
| ci-gates.md | "Required Gates" table | verification commands |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `tests/test_llm_client_protocol.py` | create | All node ids from test-plan.md mapping table. AC-3/AC-6/AC-7 rows open source files as text and use `re.search`/`ast` — no module import needed. AC-2 uses `@runtime_checkable` `isinstance`. Tests must fail before IP-1..IP-5. |
| `app/backend/clients/base_llm_client.py` | create | `from __future__ import annotations`; `from typing import List, Optional, Protocol, Tuple, runtime_checkable`. `@runtime_checkable class LLMClient(Protocol):` with the 6 methods (bodies `...`). Signatures per design.md table. Docstring on `unload` noting best-effort VRAM eviction returning `(ok, message)`. NO import of `ollama_client` (avoids cycle — design.md Import Graph). |
| `app/backend/clients/ollama_client.py` | modify | ADD ONLY 3 methods on `OllamaClient`: `health(self)->Tuple[bool,str]: return self.health_check()`; `list_models(self)->List[str]: return list_ollama_models(self.base_url)`; `unload(self)->Tuple[bool,str]: return self.unload_model()`. `list_ollama_models` is module-level (line 917) and `self.base_url` exists (line 109). Do NOT modify, rename, or remove `health_check` (317), `unload_model` (895), `translate_once` (442), `translate_batch` (733), `refine_translation` (510), or any `_`-private method. Optional: declare `class OllamaClient(LLMClient)` — structural subtyping makes this optional; if added, import `LLMClient` from `base_llm_client`. |
| `app/backend/services/translation_service.py` | modify | (a) import `LLMClient` from `app.backend.clients.base_llm_client`; change param type hints `client: OllamaClient`→`LLMClient` and `refine_client: Optional[OllamaClient]`→`Optional[LLMClient]` (lines 58, 62). Keep `OllamaClient` import only if still otherwise referenced; otherwise drop it. (b) line 210 `client.unload_model()`→`client.unload()`. (c) Lines 223-225 deferred-context-detection: remove `refine_client._build_no_system_payload(...)` + `refine_client._call_ollama(...)`; reissue the detection prompt through the public Protocol surface per design.md "Private payload logic stays inside OllamaClient". See Known Risks for the parity constraint. The `_OC._build_refine_system_prompt(...)` / `refine_client.system_prompt = ...` follow-up (lines 229-231) is OllamaClient-config wiring set by orchestrator and out of the Protocol surface — leave its mechanism intact, only the detection call itself moves to a public method. |
| `app/backend/utils/translation_helpers.py` | modify | In `_maybe_refine` (line 26), delete the `if client._is_translation_dedicated(): return translation` branch (lines 36-37). Routing is internal to `OllamaClient.translate_batch`/`translate_once` (ollama_client.py line 739) — verify no other consumer-side logic depended on it (design.md Open Risks §2). Update `client`-typed hints to `LLMClient`; import from `base_llm_client`. Do not change refinement thresholds/logic otherwise. |
| `app/backend/clients/__init__.py` | modify | `from app.backend.clients.base_llm_client import LLMClient` + `__all__ = ["LLMClient"]`. Currently empty (0 lines). |

## Contract Updates
- API: none (AC-7).
- CSS/UI: none (AC-7, no frontend).
- Env: none (AC-7).
- Data shape: none (AC-7).
- Business logic: none — translation rules unchanged (AC-5/AC-7).
- CI/CD: none — existing gates suffice; see ci-gates.md "Promotion Policy".

Note: `LLMClient` Protocol is an internal code-level interface, NOT one of the 6
governed contract artifacts (change-classification.md note line 53). No
`contracts/` edit.

## Test Execution Plan
Required floor every run: collect, targeted, changed-area. Author tests in IP-0
BEFORE any implementation; confirm they fail, then implement IP-1..IP-5 until
green. Full mapping lives in test-plan.md — do not duplicate it here.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (Protocol + signatures) | tests/test_llm_client_protocol.py::test_protocol_defines_six_methods | pass after IP-1 |
| AC-1 (signatures match table) | tests/test_llm_client_protocol.py::test_protocol_method_signatures | pass after IP-1 |
| AC-2 (structural subtype) | tests/test_llm_client_protocol.py::test_ollama_client_satisfies_protocol | pass after IP-2 |
| AC-2 (runtime isinstance) | tests/test_llm_client_protocol.py::test_ollama_client_isinstance_llm_client | pass after IP-2 |
| AC-3 (no _build_no_system_payload) | tests/test_llm_client_protocol.py::test_translation_service_no_private_payload_call | pass after IP-3 |
| AC-3 (no _call_ollama) | tests/test_llm_client_protocol.py::test_translation_service_no_private_ollama_call | pass after IP-3 |
| AC-4 (frozen public API intact) | tests/test_llm_client_protocol.py::test_ollama_client_frozen_public_api_intact | pass after IP-2 |
| AC-4 (alias delegation) | tests/test_llm_client_protocol.py::test_ollama_client_alias_methods_delegate | pass after IP-2 |
| AC-5 (context-detection via public method) | tests/test_llm_client_protocol.py::test_context_detection_uses_public_method | pass after IP-3 |
| AC-5 (regression, context parity guard) | tests/test_hy_mt_quality_refinement.py | pass unchanged |
| AC-5 (regression) | tests/test_ollama_client_dynamic_strategy.py | pass unchanged |
| AC-5 (regression) | tests/test_translation_strategy.py | pass unchanged |
| AC-5 (regression) | tests/test_translation_profiles_scenarios.py | pass unchanged |
| AC-5 (regression) | tests/test_model_router.py | pass unchanged |
| AC-6 (stdlib only) | tests/test_llm_client_protocol.py::test_base_module_stdlib_only | pass after IP-1 |
| AC-7 (no governed contract modified) | tests/test_llm_client_protocol.py::test_no_governed_contract_modified | pass throughout |

Gate commands (from ci-gates.md, run before PR): `pytest tests/test_llm_client_protocol.py -v`,
then `pytest tests/ -v`, then `cdd-kit validate --contracts` and
`cdd-kit gate p1-llm-client-abstraction`. The `private-method-grep` gate checks
zero `_build_no_system_payload`/`_call_ollama` in `translation_service.py`.

## Recommended Execution Order (TDD)
1. IP-0 — write `tests/test_llm_client_protocol.py`; run it; confirm all rows FAIL.
2. IP-1 — create `base_llm_client.py`; AC-1, AC-6 tests go green.
3. IP-2 — add 3 alias methods to `OllamaClient`; AC-2, AC-4 tests go green.
4. IP-3 — rewire `translation_service.py` (type hints, `unload()`, context-detection via public method); AC-3 + `test_context_detection_uses_public_method` go green.
5. IP-4 — rewire `translation_helpers.py` (remove `_is_translation_dedicated()` branch).
6. IP-5 — `clients/__init__.py` re-export `LLMClient`.
7. Run `pytest tests/test_llm_client_protocol.py` — all Protocol tests green.
8. Run `pytest tests/` — full regression green (AC-5). `test_hy_mt_quality_refinement.py` is the context-detection parity guard.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Do NOT touch frozen `OllamaClient` method names or any out-of-scope caller; AC-4 break fails the gate.

## Known Risks
- HIGHEST: the deferred-context-detection rewrite (translation_service.py lines 219-234). The old path used `_build_no_system_payload` → `_call_ollama`, which issues a RAW detection prompt with NO system prompt and NO translation sanitization. Routing through a public method that applies a system prompt or `_sanitize_translation` could drift the detected-context string. design.md Key Decision routes this through a public Protocol method; the engineer MUST confirm the public call reproduces the "no system prompt, raw prompt → response" behavior (e.g. issue against a transiently-cleared `system_prompt`, or use `refine_translation` whose payload path is acceptable). `test_hy_mt_quality_refinement.py` + `test_context_detection_uses_public_method` are the guards. If parity cannot be achieved through the existing public surface without a behavior change, stop and report `blocked` rather than adding a new private hook or altering output.
- Removing `_is_translation_dedicated()` from `_maybe_refine` assumes the gated routing is fully internalized in `OllamaClient.translate_batch`/`translate_once` (it is — ollama_client.py line 739). Verify no other consumer branch depended on it before deleting (design.md Open Risks §2); the dynamic-strategy and profiles regression files are the guard.
- `list_models()` alias must call module-level `list_ollama_models(self.base_url)` (not a method) — ensure the symbol is in scope within `ollama_client.py`.
- Code-map note: `.cdd/code-map.yml` is current (generated 2026-06-17); line numbers above are from it and verified against direct reads.
