---
change-id: fallback-chain-cloud-providers
schema-version: 0.1.0
last-changed: 2026-06-20
---

# Implementation Plan: fallback-chain-cloud-providers

## Objective

Make the translation fallback chain reflect the cloud-only reality: `fallback_chain`
becomes `[panjit, deepseek]`, `ollama-local` is removed from translation fallback
traversal (but retained as a `layout_assist_only` provider entry), and DeepSeek is a
second fallback that is active only when `DEEPSEEK_ENABLED=true`. When PANJIT fails and
DeepSeek is disabled, the orchestrator must fail gracefully without attempting a local
translation model. No new env vars and no new Python packages.

## Execution Scope

### In Scope
- `config/providers.yml` — fallback_chain edit (AC-1).
- `app/backend/processors/orchestrator.py` — remove the `ollama-local` break-guard in
  the fallback traversal (AC-5).
- `config.py` — read-only confirmation of `enabled: "false"` coercion (no edit; see below).
- `model_router.py` — read-only confirmation it does not read `fallback_chain` (no edit; see below).
- Env + business contract sync (owned by contract-reviewer; already classified) — implementation
  agent only consumes them, does not author them.
- Updating the stale test fixture in `tests/test_provider_fallback.py` (Test Update Contract).

### Out of Scope (do not touch)
- DeepSeek API key UI — belongs to `settings-page-cloud-redesign`.
- `app/backend/parsers/layout_detector.py` and the Ollama layout-detection path (AC-7).
- Any other `providers.yml` routing rules (`routing:` block, per-language rules).
- The `provider_id=None` legacy path that returns `winning_provider == "ollama-local"`
  (`test_ollama_used_when_no_cloud_provider`) — this is a different scenario from AC-5/AC-8; do not change or delete it.
- Introducing new env vars or Python dependencies.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | `config/providers.yml:59` — `fallback_chain: [panjit, ollama-local]` → `fallback_chain: [panjit, deepseek]` | backend-engineer |
| IP-2 | backend | `orchestrator.py:438-440` — remove the `if _fb_id == "ollama-local": break` guard so traversal no longer special-cases ollama-local | backend-engineer |
| IP-3 | backend (read-only) | confirm `config.py:473-476` coerces `enabled: "false"` → Python `False`; no edit needed | backend-engineer |
| IP-4 | backend (read-only) | confirm `model_router.py` does not read `fallback_chain`; no edit needed | backend-engineer |
| IP-5 | tests | `tests/test_provider_fallback.py:352` — update `_PANJIT_PROVIDERS_CONFIG` stale `fallback_chain: ["panjit", "ollama-local"]` → `["panjit", "deepseek"]` | backend-engineer |

## Step Ordering (backend-engineer) — execute in this order

1. **IP-1** — edit `config/providers.yml:59`. (Config first so the runtime data shape matches the new rule.)
2. **IP-2** — edit `orchestrator.py:438-440`, removing the break-guard. (Code change consumes the new config.)
3. **IP-3 / IP-4** — read-only confirmations (`config.py`, `model_router.py`). Record findings in the agent log; make no edits. If either turns out to require an edit, stop and report `blocked` (it should not — see notes below).
4. **IP-5** — update the stale test fixture at `tests/test_provider_fallback.py:352`. (Done before running the test ladder so the existing wiring tests reflect post-change config.)
5. Run the Test Execution Plan ladder below.

Rationale for order: providers.yml is the source of truth for the chain; orchestrator
must not be edited to expect `deepseek` before the config actually lists it, and the test
fixture must be updated before the targeted phase runs or `TestOrchestratorProviderWiring`
will assert against an obsolete chain.

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | AC-1..AC-8 mapping table; Test Update Contract; Test Execution Ladder | tests to run/write; fixture update |
| ci-gates.md | Required Gates table (contract-validation, env-schema-sync, targeted-tests, full-test-suite, change-gate) | verification commands |
| change-classification.md | §Inferred Acceptance Criteria (AC-1..AC-8); Tier 2 | scope + acceptance |
| contracts/business/business-rules.md | fallback-chain rule (updated by contract-reviewer) | implementation constraint — chain ordering |
| contracts/env/env-contract.md | `DEEPSEEK_ENABLED` declaration + §Deployment Sync Policy | env var semantics; default `false` |
| config.py:473-476 | `enabled` string→bool coercion | confirms disabled-deepseek is skipped |

design.md: not required for this change (classification: design.md create=no).

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| config/providers.yml | edit line 59 | `[panjit, ollama-local]` → `[panjit, deepseek]`. Leave `ollama-local` provider entry (lines 23-27, `role: layout_assist_only`) and the `deepseek` entry (`enabled: ${DEEPSEEK_ENABLED:-false}`) untouched. |
| app/backend/processors/orchestrator.py | edit lines 438-440 | Remove the two-line `if _fb_id == "ollama-local": break` guard inside the `for _fb_id in _chain:` loop. Keep the surrounding loop, the `_prov.get("enabled") is True` check (line 442) which already excludes a disabled deepseek, and the health-probe gating that produces graceful failure (AC-6). Do NOT touch line 429's `_provider_id != "ollama-local"` outer condition. |
| app/backend/config.py | read-only | Confirm only. Lines 473-476 already coerce `"false"`/`"0"`/`"no"` → `False`, so a disabled deepseek resolves to `enabled=False` and is skipped at orchestrator:442. No edit. |
| app/backend/services/model_router.py | read-only | Confirm only. No `fallback_chain` reference (grep clean). No edit. |
| tests/test_provider_fallback.py | edit line 352 | Update `_PANJIT_PROVIDERS_CONFIG["fallback_chain"]` to `["panjit", "deepseek"]` per Test Update Contract. New test classes (TestFallbackChainConfig, TestOrchestratorFallbackTraversal, TestLayoutDetectorUnchanged) are authored by test-strategist per test-plan.md — backend-engineer makes failing tests pass, does not duplicate them. |

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: `DEEPSEEK_ENABLED` (default `false`) added to `contracts/env/env-contract.md`,
  `contracts/env/.env.example.template`, `contracts/env/env.schema.json` — owned by
  contract-reviewer (classification §Required Contracts). Implementation consumes; the
  env-schema-sync gate verifies presence in template + schema.
- Data shape: none.
- Business logic: fallback-chain rule in `contracts/business/business-rules.md` updated to
  `[panjit, deepseek]` with DeepSeek conditional-activation note — owned by contract-reviewer.
- CI/CD: ci-gates.md records workflow steps (env-schema-sync, targeted-tests, change-gate);
  no contract change required from the implementation agent.

## Test Execution Plan

Required phases (floor): `collect`, `targeted`, `changed-area`; plus `contract` (this change
updates contracts) and `full` at CI per test-plan.md Test Execution Ladder. Generate evidence
with `cdd-kit test run`; the gate validates `test-evidence.yml`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_provider_fallback.py::TestFallbackChainConfig::test_fallback_chain_is_panjit_deepseek | chain equals `[panjit, deepseek]`, ollama-local absent |
| AC-2 | tests/test_provider_fallback.py::TestFallbackChainConfig::test_ollama_local_role_is_layout_assist_only | ollama-local entry retained, role layout_assist_only |
| AC-3 (disabled) | tests/test_provider_fallback.py::TestFallbackChainConfig::test_deepseek_excluded_when_disabled | deepseek not in active chain when DEEPSEEK_ENABLED=false |
| AC-3 (enabled) | tests/test_provider_fallback.py::TestFallbackChainConfig::test_deepseek_included_when_enabled | deepseek active when DEEPSEEK_ENABLED=true |
| AC-4 | tests/test_env_contract.py::TestEnvContractDeclared::test_deepseek_enabled_declared | DEEPSEEK_ENABLED declared in env-contract.md |
| AC-5 | tests/test_provider_fallback.py::TestOrchestratorFallbackTraversal::test_ollama_local_branch_absent_from_orchestrator | break-guard string absent from orchestrator source |
| AC-5/AC-8 | tests/test_provider_fallback.py::TestOrchestratorFallbackTraversal::test_fallback_order_selection_at_orchestrator_seam | deepseek resolved as fallback, not ollama-local (selection-style) |
| AC-6 | tests/test_provider_fallback.py::TestOrchestratorFallbackTraversal::test_panjit_fail_deepseek_disabled_graceful | PANJIT fail + deepseek disabled → graceful failure, no Ollama/localhost contacted |
| AC-7 | tests/test_provider_fallback.py::TestLayoutDetectorUnchanged::test_layout_detector_source_unmodified | layout_detector.py landmark string stable |

Targeted phase command (per ci-gates.md / test-plan.md):
`pytest tests/test_provider_fallback.py tests/test_env_contract.py -x -q`

## Tier / tasks.yml frontmatter note

Change is correctly tiered **Tier 2** (classification §Tier). Per the CLAUDE.md tier-floor
lesson, the gate's tier-floor heuristic will likely fire on vocabulary present in these
artifacts — `api key`, `api_key`, `endpoint`, `integration`, `enabled`/env-var phrasing —
and may try to force a higher floor even though there is no migration and no new secret here
(`DEEPSEEK_ENABLED` already exists in contracts + schema). The `tasks.yml` frontmatter must
carry a `tier-floor-override` set to `2` with written rationale: "No migration, no new env
var/secret; api_key/endpoint/integration tokens are pre-existing provider-routing vocabulary,
not a new auth or migration surface." Verify the override is present before running
`cdd-kit gate`, or the gate will false-positive on tier floor.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- IP-3 and IP-4 are confirm-only. If either reveals a needed edit, stop and report `blocked` rather than editing config.py or model_router.py opportunistically.

## Known Risks

- **Disabled-deepseek skip relies on bool coercion.** orchestrator:442 uses
  `_prov.get("enabled") is True` (identity check). This passes only because config.py:473-476
  coerces the `"false"` string to a real `bool`. If that coercion is ever weakened, a disabled
  deepseek string would slip the `is True` check. The AC-3-disabled and AC-6 tests guard this;
  do not relax the coercion.
- **Empty chain after removal.** With deepseek disabled, the traversal loop finds no enabled
  fallback and `_cloud_client` stays `None`; the orchestrator then proceeds without a cloud
  fallback. AC-6 asserts this is a graceful failure with no local-model attempt — confirm the
  test asserts no Ollama/localhost endpoint is contacted (not merely that an exception is raised).
- **Outer guard at line 429.** `_provider_id != "ollama-local"` (line 429) is intentionally left
  in place; removing the inner break (line 439-440) must not be confused with this outer condition.
- **code-map.yml staleness.** `.cdd/code-map.yml` is dated 2026-06-17; orchestrator.py has since
  been edited (working tree shows `M app/backend/main.py` and others). Line numbers in this plan
  were re-verified against the live file (orchestrator.py:438-440, providers.yml:59,
  test_provider_fallback.py:352) and are current as of 2026-06-20.
