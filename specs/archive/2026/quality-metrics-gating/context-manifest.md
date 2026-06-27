# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend translation-quality subsystem (QE, LLM judge, critique loop)
- Long-document translation path (`translate_document()`)
- Runtime configuration / env (feature flags + rescore threshold)

## Allowed Paths
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
- docs/improvement-plan.md
- .cdd/code-map.yml
- app/backend/services/job_manager.py
- app/backend/processors/pdf_processor.py
- tests/test_critique_gate.py
- tests/test_translate_document_parity.py

## Required Contracts
-

## Required Tests
-

## Agent Work Packets
<!-- One sub-section per required agent. Each path list must be a subset of Allowed Paths above.
     Add or remove sub-sections to match Required Agents in change-classification.md.
     These sub-sections are documentation only — gate enforces Allowed Paths, not individual packets. -->

### change-classifier
- specs/changes/<change-id>/
- specs/context/project-map.md
- specs/context/contracts-index.md

### <implementation-agent>
<!-- Replace with actual agent name, e.g. backend-engineer, frontend-engineer -->
- specs/changes/<change-id>/
- contracts/
- src/
- tests/

### <review-agent>
<!-- Replace with actual agent name, e.g. contract-reviewer, qa-reviewer -->
- specs/changes/<change-id>/
- contracts/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - contracts/api/openapi.yml
  reason: conditional — approve only if contract-reviewer confirms per-segment QE/judge scores extend GET /jobs/{id}/quality or GET /judge response schemas
  status: pending

- request-id: CER-002
  requested_paths:
    - app/backend/services/job_manager.py
  reason: AC-2 rescore routing and AC-5 per-block JudgeResult/JobQualityRecord persistence live in the post-translate hook at job_manager.py:416-442
  status: approved

- request-id: CER-003
  requested_paths:
    - app/backend/processors/pdf_processor.py
  reason: AC-6 layout-judge wiring requires the PDF page rasterization call site in pdf_processor.py
  status: approved

## Approved Expansions
- app/backend/services/job_manager.py (CER-002)
- app/backend/processors/pdf_processor.py (CER-003)
