---
change-id: qa-judge-provider-consistency
schema-version: 0.1.0
last-changed: 2026-07-07
---

# Implementation Plan: qa-judge-provider-consistency

## Objective
Make the judge/QA re-translation callback (`_translate_fn` in
`job_manager.py`) execute against the judge's own provider
(`JUDGE_CLOUD_PROVIDER_ID` when `JUDGE_PROVIDER="cloud"`, else the local
Ollama judge client), never `last_client` / `model_router`'s main-translation
winner. All client construction stays in `quality_judge.py` via a new
`translation_client` property built on a generalized
`_build_cloud_client(model=...)`. Remove the
`last_client is None → OllamaClient(DEFAULT_MODEL)` fallback from the judge
re-translation path. Add BR-98 + one Table U row to `business-rules.md` and a
`(BR-98)` cross-reference in `env-contract.md`. No new config surface.

## Execution Scope

### In Scope
- `app/backend/services/quality_judge.py`: new `translation_client` property;
  generalize `_build_cloud_client()` to accept an optional `model=` override.
- `app/backend/services/job_manager.py`: rewrite `_translate_fn` (L493-510) to
  call `_judge.translation_client.translate_once(...)`.
- `contracts/business/business-rules.md`: add BR-98 (after BR-97) + one Table U row.
- `contracts/env/env-contract.md`: add `(BR-98)` cross-ref to the
  `JUDGE_PROVIDER` (L45) and `JUDGE_CLOUD_PROVIDER_ID` (L48) rows; no new var,
  no default change.
- Tests: extend `tests/test_quality_judge.py` and
  `tests/test_orchestrator_judge.py` (see Test Execution Plan).

### Out of Scope
- `model_router.py` main bulk-translation routing / fallback chain (non-goal).
- BR-97's deepseek-skip gate condition (untouched — only assertions strengthened per test-plan).
- The in-line critique loop / `_critique_gate_adopt` in `translation_service.py`
  (sibling `batch-critique-qe-scoring`).
- Cancellation / timeout / `run_judge_loop` hang recovery (sibling
  `qa-judge-hang-recovery` — depends on this change; see Known Risks).
- `snapshot_cb` progress param on `run_judge_loop` (sibling
  `translation-progress-detail-ui`; see Known Risks).
- `judge_layout()` / image scoring path (BR-95, always-local, untouched).
- BR-92 rescore resolution (sibling `br92-rescore-resolution`).
- Introducing any new env var / config key (design Decision 2 forbids it).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | quality_judge.py | Generalize `_build_cloud_client()` signature to `_build_cloud_client(self, model=None)`, defaulting to `self.model`; scoring call site `self._client = self._build_cloud_client()` (L85) must stay behavior-identical (passes no `model`, resolves to `self.model`). | backend-engineer |
| IP-2 | quality_judge.py | Add a `translation_client` property (lazily built, cached once) returning the judge's translation-role client on the SAME provider as scoring: cloud → `_build_cloud_client(model=<providers.yml models.translate for JUDGE_CLOUD_PROVIDER_ID, else JUDGE_MODEL>)`; ollama → `OllamaClient(base_url=OLLAMA_BASE_URL, model=JUDGE_MODEL)`. Never returns `None`. | backend-engineer |
| IP-3 | job_manager.py | Rewrite `_translate_fn` (L493-510): drop `_cli = last_client` / `OllamaClient(DEFAULT_MODEL)` fallback; call `_judge.translation_client.translate_once(f"{feedback_prefix}{src_text}", tgt, src_lang)`. Keep the `_judge_retranslate_count`/`status_detail` and target-resolution lines as-is. | backend-engineer |
| IP-4 | job_manager.py | Do NOT remove the `OllamaClient` (L16) or `DEFAULT_MODEL` (L20) imports — still used at L338 (type annotation), L617, L628. Confirm no other reference to `last_client` inside the judge block breaks. | backend-engineer |
| IP-5 | business-rules.md | Add BR-98 row (design.md Decision 4 exact text) after BR-97 (L109); add one Table U row (§Table U). | contract-reviewer |
| IP-6 | env-contract.md | Append `(BR-98)` cross-ref to `JUDGE_PROVIDER` (L45) and `JUDGE_CLOUD_PROVIDER_ID` (L48) description prose. No value/default/default-example changes. | contract-reviewer |
| IP-7 | tests | Author/extend unit + integration tests per Test Execution Plan; strengthen `test_judge_skipped_when_provider_is_deepseek` (Test Update Contract). | test-strategist / backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Decision 1 (translate-role model), Decision 3 (client in quality_judge.py), Decision 4 (BR-98 exact text + Table U row) | implementation constraints + contract wording |
| change-request.md | Non-goals, Constraints (already-panjit no-op) | scope guardrails |
| change-classification.md | AC-1..AC-7 | acceptance criteria |
| test-plan.md | AC→test mapping table; Notes (mock-boundary, last_client-always-None) | tests to write + patch target |
| test-plan.md | Test Update Contract | strengthen deepseek-skip test |
| business-rules.md | BR-97 (L109), Table U (L357) | insertion anchors |
| env-contract.md | JUDGE_PROVIDER (L45), JUDGE_CLOUD_PROVIDER_ID (L48) | cross-ref insertion anchors |
| providers.yml.example | `panjit.models.translate: gpt-oss:120b` (L13-14) | translation-role model resolution |
| ci-gates.md | Required Gates table (lint/build/unit/contract) | verification gates |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/services/quality_judge.py` (L89-114 `_build_cloud_client`) | edit | Change signature to `def _build_cloud_client(self, model=None)`; use `model or self.model` for the `OpenAICompatibleClient(model=...)` arg. Scoring call at L85 is unchanged and MUST stay behavior-identical (no `model` → resolves `self.model`). Keep lazy imports of `OpenAICompatibleClient`/`load_providers_config` inside the method. |
| `app/backend/services/quality_judge.py` (new, after L114) | add | `translation_client` property. Cloud branch: resolve `models.translate` from the `JUDGE_CLOUD_PROVIDER_ID` provider entry in `load_providers_config()`, fall back to `JUDGE_MODEL` when key/entry absent, then `self._build_cloud_client(model=<resolved>)`. Ollama branch: `OllamaClient(base_url=OLLAMA_BASE_URL, model=JUDGE_MODEL)`. Cache on first access (e.g. `self._translation_client`). Never `None`. Reuse existing config symbols only (no new env var). |
| `app/backend/services/job_manager.py` (L493-510 `_translate_fn`) | edit | Replace the `_cli = last_client` / `if _cli is None: _cli = OllamaClient(model=DEFAULT_MODEL)` block and `_cli.translate_once(...)` with `ok, result = _judge.translation_client.translate_once(f"{feedback_prefix}{src_text}", tgt, src_lang)`. Keep L495-496 counter/status, L502-506 feedback+target resolution, and `return result if ok else src_text`. |
| `app/backend/services/job_manager.py` (imports L16, L20) | no change | `OllamaClient` / `DEFAULT_MODEL` remain used at L338, L617, L628 — do not remove. |
| `contracts/business/business-rules.md` (after L109) | edit | Insert BR-98 inventory row using design.md Decision 4 exact text; test ref `tests/test_orchestrator_judge.py`. |
| `contracts/business/business-rules.md` (§Table U, ~L374) | edit | Add row: `Judge pass runs, re-translation invoked \| client resolves to JUDGE_CLOUD_PROVIDER_ID provider, independent of last_client (BR-98) \| tests/test_orchestrator_judge.py`. |
| `contracts/env/env-contract.md` (L45, L48) | edit | Append `(BR-98)` cross-ref to the two `JUDGE_*` description cells. Use a Bash string-anchored replace if the contract-write hook blocks Edit on this file. No value changes. |
| `tests/test_quality_judge.py` | edit | Add unit tests (see Test Execution Plan). Patch `app.backend.clients.openai_compatible_client.OpenAICompatibleClient` (definition module), never a `quality_judge` attribute. |
| `tests/test_orchestrator_judge.py` | edit | Add integration tests + strengthen deepseek-skip test; make the fake judge's `run_judge_loop` invoke the passed `translate_fn` so the real closure body runs. |

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: `env-contract.md` review-only — append `(BR-98)` cross-ref to
  `JUDGE_PROVIDER` (L45) and `JUDGE_CLOUD_PROVIDER_ID` (L48). No new variable,
  no default/example/scope change (design Decision 2).
- Data shape: none.
- Business logic: `business-rules.md` — add BR-98
  (judge-retranslation-provider-consistency, design.md Decision 4 exact text)
  after BR-97; add one Table U row. BR-97 and BR-72..BR-77 semantics unchanged.
- CI/CD: none.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_quality_judge.py::test_translation_client_resolves_cloud_provider_and_translate_model | client built on JUDGE_CLOUD_PROVIDER_ID provider with `models.translate` model |
| AC-1 | tests/test_orchestrator_judge.py::test_translate_fn_uses_judge_translation_client_not_last_client | `_translate_fn` calls `_judge.translation_client.translate_once`, never `last_client` |
| AC-2 | tests/test_orchestrator_judge.py::test_translate_fn_request_params_unchanged_when_last_client_already_panjit | constructed base_url/model/prompt equal old panjit client params (no-op) |
| AC-3 | tests/test_quality_judge.py::test_translation_client_reuses_existing_config_symbols_only | only JUDGE_* + providers.yml read; no new config symbol |
| AC-4 | tests/test_quality_judge.py::test_translation_client_model_may_differ_from_scoring_client_same_provider | translation model may differ from scoring model, same provider/base_url |
| AC-4 | tests/test_quality_judge.py::test_translation_client_falls_back_to_judge_model_when_translate_key_absent | absent `models.translate` → model == JUDGE_MODEL |
| AC-5 | tests/test_orchestrator_judge.py::test_judge_skipped_when_provider_is_deepseek | run_judge_loop not called AND `translation_client` never accessed (strengthened) |
| AC-5 | tests/test_orchestrator_judge.py::test_judge_still_fires_when_provider_is_panjit | judge pass runs for panjit |
| AC-6 | contracts/business/business-rules.md via `cdd-kit validate --contracts` | BR-98 present + Table U row consistent |
| AC-7 | tests/test_orchestrator_judge.py::test_translate_fn_no_ollama_default_fallback_when_judge_runs | no `OllamaClient(DEFAULT_MODEL)` construction when judge runs |
| AC-7 | tests/test_quality_judge.py::test_translation_client_never_none | property never returns None (cloud + ollama branches) |

Required test phases: `collect`, `targeted`, `changed-area` (floor); add
`contract` (BR-98 affects `business-rules.md`). Generate evidence with
`cdd-kit test run`; full ladder in test-plan.md §Test Execution Ladder.
Patch-boundary + always-None-`last_client` caveats: see test-plan.md §Notes.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- Use design.md Decision 4 for BR-98's exact text — do not reword.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- **Sequencing vs `qa-judge-hang-recovery`**: that sibling edits the same
  `_translate_fn` / `run_judge_loop` call-site region and depends on this change
  landing first. Do NOT implement both in one PR without careful ordering — land
  this change first, then rebase hang-recovery onto it.
- **Sibling `translation-progress-detail-ui`**: adds an additive `snapshot_cb`
  parameter to `run_judge_loop` — a different, unrelated signature addition. It
  should compose cleanly (no shape conflict with the `translate_fn` closure
  change here); confirm no overlap when implementing.
- **`_build_cloud_client()` scoring call site**: generalizing the signature to
  `model=None` must NOT change the scoring client — verify `self._client`
  construction (L85) still resolves `self.model` (== JUDGE_MODEL) exactly.
- **`models.translate` absent**: if an operator points `JUDGE_CLOUD_PROVIDER_ID`
  at a provider lacking `models.translate`, the property must fall back to
  `JUDGE_MODEL` (covered by the AC-4 fallback test) — make the fallback
  explicit, not incidental.
- **Mock boundary**: `translation_client` / `_build_cloud_client` lazily import
  `OpenAICompatibleClient` inside the method; patch
  `app.backend.clients.openai_compatible_client.OpenAICompatibleClient`, never a
  `quality_judge` module attribute (test-plan.md §Notes).
- **Anti-tautology**: the existing `test_orchestrator_judge.py` harness mocks
  `run_judge_loop` to return a canned result WITHOUT invoking the callback; new
  integration tests must give it a `side_effect` that actually calls
  `translate_fn`, or the closure body is never exercised.
- **code-map freshness**: line ranges were taken from direct source reads within
  Allowed Paths (`.cdd/code-map.yml` not consulted this pass); re-verify exact
  line numbers before editing, as sibling changes may shift them.
