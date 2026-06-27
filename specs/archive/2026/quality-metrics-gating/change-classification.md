# Change Classification

## Change Types
- primary: business-logic-change (quality-gating semantics: per-segment QE routing, critique adoption gate, judge granularity, long-doc parity)
- secondary: env-change (`QE_ENABLED` default flip false→true, new `QE_RESCORE_THRESHOLD`), feature-enhancement (`translate_document()` parity)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module
- rationale: touches `quality_evaluator.py`, `quality_judge.py`, `translation_service.py`, and `config.py`; `QE_ENABLED` default-on changes runtime behavior for every translation job (lazy-loads COMET → latency/VRAM), and the critique gate + judge-granularity changes alter existing output behavior. Reversible via feature flags; no migration / auth / payments / external-API break.

## Tier
- 2

## Architecture Review Required
- yes
- reason: non-obvious design + data-flow decisions: scoring-gate semantics (which score authoritative, tie-handling at `≥`), the no-QE fallback heuristic contract, per-segment/per-block judge output shape, MLLM layout-scoring integration into the existing Gemma judge, and the `translate_document()` data-flow rewiring (terms + critique + overlap-as-context). These must be decided before implementation.

## Required Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current behavior captured in change-request Known Context and design.md baseline |
| proposal.md | no | improvement-plan §階段 4 already decides scope |
| spec.md | no | behavior fits in design.md + implementation-plan |
| design.md | yes | arch review required (scoring-gate semantics, MLLM integration, long-doc data-flow) |
| qa-report.md | yes | QE default-on is an approved-with-risk latency/VRAM tradeoff needing durable prose evidence |
| regression-report.md | yes | three existing behaviors change: critique adoption (last-wins → score-gated), judge whole-doc → per-segment, QE default off → on |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | not user-input-fuzzing surface |
| stress-soak-report.md | no | promote to yes only if blocking latency/VRAM regression found |

## Required Contracts
- API: conditional — `contract-reviewer` confirms whether per-segment QE / per-block judge scores extend existing `GET /jobs/{id}/quality` and `GET /judge` response schemas in `contracts/api/api-contract.md`; if so, update contract + run `cdd-kit openapi export` (CER-001)
- CSS/UI: none
- Env: yes — `contracts/env/env-contract.md`, `contracts/env/env.schema.json`, `contracts/env/.env.example.template`: `QE_ENABLED` default false→true; add `QE_RESCORE_THRESHOLD`
- Data shape: yes — `contracts/data/data-shape-contract.md`: per-segment QE score structure, per-block judge score structure, PDF MLLM layout score (1-5) field
- Business logic: yes — `contracts/business/business-rules.md`: new BRs for QE rescore-threshold routing, critique adoption gate (`adopt iff revised ≥ original`), no-QE fallback heuristic, per-segment judge scoring, long-doc parity guarantees
- CI/CD: no new gate; `.env.example`/`env.schema` sync gate must stay green

## Required Tests
- unit: yes — per-segment QE call path; threshold parsing/default; critique gate score comparison incl. tie (`==`); no-QE fallback heuristic; `translate_document()` terms + critique + overlap-context wiring
- contract: yes — env contract (`QE_ENABLED` default true, `QE_RESCORE_THRESHOLD`); business-rule presence; data-shape of quality/judge results
- integration: yes — critique loop end-to-end keeps better revision and discards worse; `translate_document()` large-DOCX path applies terms + critique + overlap context (at real entry point, not wrapper — avoids wrong-entry-point tautology per CLAUDE.md)
- E2E: optional — full job pipeline with QE on
- visual: none
- data-boundary: yes — quality/judge result payload with per-segment arrays + MLLM layout score; empty/missing-segment and unscored-segment boundaries
- resilience: yes — QE unavailable / COMET lazy-load failure → critique gate degrades to heuristic; pipeline still completes; judge disabled path unaffected
- fuzz/monkey: no
- stress: yes (consideration) — QE default-on + critique doubling LLM calls on large docs; measure added latency/VRAM
- soak: optional — long-running large-DOCX jobs via `translate_document()`

## Required Agents
- spec-architect — writes `design.md`: scoring-gate semantics, per-segment/MLLM judge integration, long-doc data-flow parity, no-QE fallback contract
- implementation-planner — turns design + contracts + tests into the execution packet before any implementation
- backend-engineer — implements 4.1–4.4 across `quality_evaluator.py`, `quality_judge.py`, `translation_service.py`, `config.py`
- test-strategist — AC to test mapping; avoids selection/wiring/entry-point tautology traps (CLAUDE.md learnings)
- contract-reviewer — env + business + data contracts (+ conditional API response-schema check)
- e2e-resilience-engineer — QE-unavailable / model-load-failure degradation path (4.3 fallback)
- stress-soak-engineer — QE default-on + critique-doubling latency/VRAM profile on large docs
- qa-reviewer — release readiness; documents approved-with-risk for `QE_ENABLED` default flip

## Inferred Acceptance Criteria

- AC-1: CometKiwi QE evaluates each segment individually (per-segment `evaluate()` call path), not a single whole-document score. (4.1)
- AC-2: Segments scoring below `QE_RESCORE_THRESHOLD` are routed to re-translation. (4.1)
- AC-3: `QE_ENABLED` defaults to `true` in `config.py` and `contracts/env/env-contract.md`. (4.1)
- AC-4: `QE_RESCORE_THRESHOLD` env var exists with a documented default and validation, declared in the env contract/schema/template. (4.1)
- AC-5: The LLM judge emits per-segment/per-block scores instead of one whole-document score. (4.2)
- AC-6: For PDF pages, an MLLM-as-judge layout score (1-5) is produced reusing the Gemma infra in `quality_judge.py`, additively, with `JUDGE_ENABLED` still defaulting to `false`. (4.2)
- AC-7: The critique loop adopts a revision only when revised score ≥ original score; otherwise the original is kept. (4.3)
- AC-8: When QE is unavailable, the critique gate falls back to a length/fluency heuristic and the pipeline still completes. (4.3)
- AC-9: `translate_document()` applies terms substitution, reaching parity with the short-doc path. (4.4)
- AC-10: `translate_document()` runs the critique loop. (4.4)
- AC-11: `translate_document()` uses the 50-token overlap as a context window (not only for dedup). (4.4)

## Tasks Not Applicable
- 2.2 (CSS/UI contract): no frontend change
- 4.2 (Frontend implementation): no frontend change; frontend quality display is an explicit non-goal
- 4.3 (Env/deploy): no deploy config changes beyond env vars already covered in 2.3
- 5.1 (UI/UX review): no UI surface
- 5.2 (Visual review): no CSS/web UI

## Context Manifest Draft

### Affected Surfaces
- Backend translation-quality subsystem (QE, LLM judge, critique loop)
- Long-document translation path (`translate_document()`)
- Runtime configuration / env (feature flags + rescore threshold)

### Allowed Paths
- specs/changes/quality-metrics-gating/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/quality_evaluator.py
- app/backend/services/quality_judge.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/doc_chunker.py
- app/backend/services/context_prompts.py
- app/backend/utils/translation_helpers.py
- app/backend/config.py
- contracts/env/env-contract.md
- contracts/env/env.schema.json
- contracts/env/.env.example.template
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/api/api-contract.md
- tests/test_quality_evaluation.py
- tests/test_quality_judge.py
- tests/test_judge_api.py
- tests/test_context_window_segments.py
- tests/test_doc_chunker.py
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/contract/samples/job_quality_available.json
- .cdd/code-map.yml

### Context Expansion Requests
- CER-001: contracts/api/openapi.yml — pending; approve only if contract-reviewer confirms per-segment QE/judge scores extend existing GET /jobs/{id}/quality or GET /judge response schemas
