# Change Classification

## Change Types
- primary: new-feature
- secondary:

## Risk Level
- medium

## Impact Radius
- cross-module

## Lane
- feature

## Tier
- 2

## Architecture Review Required
- yes
- reason: COMET/xCOMET introduces a new subsystem boundary — a neural quality-evaluation step with a new model-loading/inference runtime and new pip dependencies. Decisions needed before implementation: (1) sync inline vs. async/background scoring (latency on job completion), (2) where scores are stored and their data shape (per-block score keyed to block/IR id), (3) device/resource policy and enable/disable + offline-degradation behavior, (4) module boundary — in-process library call vs. separate client/service.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | |
| proposal.md | no | |
| spec.md | no | |
| design.md | yes | Architecture Review Required: yes — spec-architect authors design.md |
| qa-report.md | no | only if QA finds blocking issues |
| regression-report.md | no | |
| visual-review-report.md | no | |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: contracts/api/api-contract.md — new GET /jobs/{id}/quality endpoint, response schema, error cases; contracts/api/openapi.yml regenerated
- CSS/UI: none
- Env: contracts/env/env-contract.md — QE model name/path, device, enable flag
- Data shape: contracts/data/data-shape-contract.md — per-block QualityScore shape keyed to block/IR id
- Business logic: contracts/business/business-rules.md — QE behavior rule, enable/disable default, safe-degradation
- CI/CD: contracts/ci/ci-gate-contract.md — only if new gate added

## Required Tests
- unit: QE scorer module (mock COMET model), per-block score structure, enable/disable flag behavior
- contract: test_env_contract.py (new QE env vars), openapi export --check
- integration: translate job → QE hook invoked → scores stored; GET /jobs/{id}/quality returns scores
- E2E: not required (no user journey surface)
- visual: not required
- data-boundary: unknown job id → 404; job not yet complete → defined response; COMET model unavailable → safe degradation
- resilience: QE failure must not block translation job completion
- fuzz/monkey: not required for this tier
- stress: not required for this tier
- soak: not required for this tier

## Required Agents
1. contract-reviewer
2. test-strategist
3. spec-architect
4. ci-cd-gatekeeper
5. implementation-planner
6. backend-engineer
7. dependency-security-reviewer
8. qa-reviewer

## Inferred Acceptance Criteria
- AC-1: After a translation job completes, the pipeline invokes the COMET/xCOMET model and produces one quality score per translated block.
- AC-2: GET /jobs/{id}/quality returns HTTP 200 with a payload containing per-block COMET scores, each score associated with its block/IR identifier.
- AC-3: GET /jobs/{id}/quality returns a well-formed error (404) for an unknown job id, and a defined response for a job that has not yet completed or has no scores.
- AC-4: The new endpoint and its response shape are declared in contracts/api/api-contract.md and reflected in contracts/api/openapi.yml (cdd-kit openapi export --check passes).
- AC-5: The per-block score data shape is declared in contracts/data/data-shape-contract.md.
- AC-6: New env vars (model name/path, device, enable flag) are declared in contracts/env/env-contract.md, .env.example.template, and validated by test_env_contract.py.
- AC-7: QE scoring is gated by an enable/disable flag and degrades safely (job still completes, endpoint returns a defined "scoring unavailable/disabled" response) when the model is absent or scoring fails — translation output is never blocked by QE failure.
- AC-8: The full test suite passes, including new unit/contract/data-boundary tests for QE scoring and the new endpoint.

## Tasks Not Applicable
- not-applicable: 2.2, 4.2, 3.3, 3.4, 3.5, 5.1, 5.2, 6.3, 6.4

(2.2: no CSS/UI contract surface; 4.2: no frontend; 3.3: no E2E user journey; 3.4: no monkey tests at Tier 2; 3.5: no stress/soak at Tier 2; 5.1: no UI/UX review; 5.2: no visual review; 6.3: no informational gates; 6.4: no nightly/weekly/manual gates)

## Clarifications or Assumptions
- Assumption: QE scoring runs as a post-translation step on the existing job, not as a separate async queue/worker. If async background processing is chosen during design, re-evaluate to Tier 1.
- Assumption: /jobs/{id}/quality is read-only (GET); it returns previously computed scores rather than triggering scoring on request.
- Open question for spec-architect: COMET is typically reference-free when used for MT output (source+hypothesis only). Confirm input shape per block.
- Open question: enable-by-default vs. opt-in, and behavior when model is unavailable (offline/no GPU).
- Gate note: cdd-kit gate tier-floor may false-positive on "endpoint", "integration" vocabulary. Use tier-floor-override with rationale (Tier 2, additive read-only endpoint, no migration/auth/payments).

## Context Manifest Draft

### Affected Surfaces
- Translation pipeline post-processing (new QE scoring step)
- API surface (new GET /jobs/{id}/quality endpoint)
- Job state / data shape (per-block quality scores)
- Runtime config / dependencies (new ML model + pip packages + env vars)

### Allowed Paths
- specs/changes/p2-comet-qe/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/ci/ci-gate-contract.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/metrics.py
- app/backend/config.py
- app/backend/requirements.txt
- app/backend/environment.yml
- app/backend/main.py
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_metrics_counters.py
- tests/test_metrics_endpoint.py
- tests/test_model_config_api.py
- tests/contract/
- .github/workflows/contract-driven-gates.yml

### Agent Work Packets

#### contract-reviewer
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

#### test-strategist
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_metrics_counters.py
- tests/contract/

#### spec-architect
- specs/changes/p2-comet-qe/
- specs/context/project-map.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/config.py
- app/backend/main.py

#### ci-cd-gatekeeper
- specs/changes/p2-comet-qe/
- contracts/ci/ci-gate-contract.md
- contracts/api/openapi.yml
- app/backend/requirements.txt
- app/backend/environment.yml
- .github/workflows/contract-driven-gates.yml

#### implementation-planner
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/config.py

#### backend-engineer
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/config.py
- app/backend/main.py
- app/backend/requirements.txt
- app/backend/environment.yml
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_metrics_counters.py
- tests/contract/

#### dependency-security-reviewer
- specs/changes/p2-comet-qe/
- app/backend/requirements.txt
- app/backend/environment.yml
- contracts/env/env-contract.md

#### qa-reviewer
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- tests/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/services/quality_evaluator.py
  reason: New QE service module expected to be created during implementation; not yet present. Parent dir app/backend/services/ is in scope; new file write is in-scope by parent.
  status: approved
