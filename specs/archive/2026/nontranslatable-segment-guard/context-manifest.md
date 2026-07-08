# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Translation body (non-table) path — input passthrough guard
- Translation result handling — output meta/refusal guard + `tmap` mapping
- LLM clients — existing short-token bypass reference
- Business rules contract — body-path passthrough + refusal-guard rule

## Allowed Paths
- specs/changes/nontranslatable-segment-guard/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/utils/translation_helpers.py
- app/backend/services/translation_service.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/utils/text_utils.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_nontranslatable_segment_guard.py
- tests/test_context_window_segments.py
- tests/test_openai_compatible_client.py
- docs/TEST_DOC/

Note: `tests/test_nontranslatable_segment_guard.py` is NEW.
`contracts/data/data-shape-contract.md` is CONDITIONAL — touched only if the fix
introduces a new `translation_status` value (default plan reuses `passthrough`/`failed`).
The 8D PDF in `docs/TEST_DOC/` is the reproduction fixture SOURCE; its trivial segments
are copied into the test as string fixtures.

## Required Contracts
- contracts/business/business-rules.md
- (conditional) contracts/data/data-shape-contract.md

## Required Tests
- tests/test_nontranslatable_segment_guard.py (NEW)
- tests/test_context_window_segments.py

## Agent Work Packets

### implementation-planner
- specs/changes/nontranslatable-segment-guard/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- app/backend/utils/translation_helpers.py
- app/backend/services/translation_service.py
- app/backend/utils/text_utils.py

### bug-fix-engineer
- specs/changes/nontranslatable-segment-guard/
- app/backend/utils/translation_helpers.py
- app/backend/services/translation_service.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/utils/text_utils.py
- contracts/business/business-rules.md
- tests/test_nontranslatable_segment_guard.py
- tests/test_context_window_segments.py
- docs/TEST_DOC/

### test-strategist
- specs/changes/nontranslatable-segment-guard/
- app/backend/utils/translation_helpers.py
- app/backend/services/translation_service.py
- app/backend/utils/text_utils.py
- tests/test_nontranslatable_segment_guard.py
- tests/test_context_window_segments.py
- tests/test_openai_compatible_client.py

### contract-reviewer
- specs/changes/nontranslatable-segment-guard/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/services/translation_service.py

### qa-reviewer
- specs/changes/nontranslatable-segment-guard/
- contracts/business/business-rules.md
- tests/test_nontranslatable_segment_guard.py
- tests/test_context_window_segments.py

## Context Expansion Requests
- none — all candidate paths are present in project-map.md / contracts-index.md; the
  change-request supplies the exact line pointers (translation_service.py:887,
  translation_helpers.py:182/188), so no read outside the packet is needed to plan.
