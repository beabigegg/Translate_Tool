# Change Classification

## Change Types
- primary: refactor (dead-code-removal)
- secondary: env-contract-change (config constants may be env-sourced)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- module-level

## Tier
- 2

## Architecture Review Required
- no

## Required Artifacts

Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

| artifact | create? |
|---|---|
| design.md | no |
| qa-report.md | no |
| visual-review-report.md | no |

## Required Contracts
- API: no (no endpoint changes)
- CSS/UI: no
- Env: yes — verify whether CROSS_MODEL_REFINEMENT_ENABLED / REFINEMENT_ENABLED / REFINEMENT_MIN_CHARS are inventoried env vars; if so, remove from env-contract + .env.example.template
- Data shape: no
- Business logic: yes — verify no documented rule references cross-model/HY-MT/two-pass refinement; if present, retire it
- CI/CD: no

## Required Tests
- unit: assert cloud RouteGroup has no refine_model field; orchestrator builds no refine_client on cloud path
- contract: re-run env-contract test after constant removal; re-run API conformance
- integration: test_model_router.py + translation-strategy tests confirm cloud (PANJIT) path unchanged

## Required Agents
1. `implementation-planner` — ordered deletion plan (config → ollama_client → model_router → orchestrator → test retirement)
2. `contract-reviewer` — env/business/api/data contract impact
3. `test-strategist` — coverage: suite proves cloud path unchanged, no orphaned test references
4. `ci-cd-gatekeeper` — ci-gates.md
5. `backend-engineer` — perform all removals; grep consumers; delete test file
6. `qa-reviewer` — release readiness; full suite green; no dead references remain

## Inferred Acceptance Criteria
- AC-1: CROSS_MODEL_REFINEMENT_ENABLED, REFINEMENT_ENABLED, REFINEMENT_MIN_CHARS removed from config.py (and env-contract if env-sourced)
- AC-2: orchestrator.py has no refine_client build block and no refine_client usage; cloud translation path executes identically to before
- AC-3: ollama_client.py no longer defines refine_translation(), _build_refine_prompt(), _build_refine_system_prompt()
- AC-4: RouteGroup has no refine_model field; no HY-MT or TranslateGemma routing entries
- AC-5: tests/test_hy_mt_quality_refinement.py deleted; no other test references removed symbols
- AC-6: Repo-wide search for refine_translation, refine_client, refine_model, CROSS_MODEL_REFINEMENT, HY-MT, TranslateGemma returns no live references in app/ or tests/
- AC-7: Full backend test suite passes; cloud (PANJIT) translation behavior unchanged
- AC-8: cdd-kit gate passes including env and API conformance

## Tasks Not Applicable
- 1.3 (no design.md / architecture review)
- 2.1 (API contract — no endpoint change)
- 2.2 (CSS/UI contract — no UI)
- 2.4 (Data shape contract — no persisted field changes)
- 2.6 (CI/CD contract — no gate change)
- 3.3 (E2E/resilience — not required)
- 3.4 (data-boundary/monkey — not required)
- 3.5 (stress/soak — not required)
- 4.2 (Frontend — no UI change)
- 4.3 (Env/deploy — no deploy change)
- 5.1 (UI/UX review — no UI)
- 5.2 (Visual review — no UI)
