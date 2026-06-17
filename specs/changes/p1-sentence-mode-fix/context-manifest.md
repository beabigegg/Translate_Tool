# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend translation pipeline (SENTENCE_MODE batch path)

## Allowed Paths
- specs/changes/p1-sentence-mode-fix/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- app/backend/config.py
- app/backend/services/translation_strategy.py
- app/backend/services/metrics.py
- contracts/business/business-rules.md
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py

## Required Contracts
- contracts/business/business-rules.md (review only; edit if counting/failure-marker rule must change)

## Required Tests
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py
- (new) tests/test_sentence_mode_consistency.py

## Agent Work Packets

### change-classifier
- specs/changes/p1-sentence-mode-fix/
- specs/context/project-map.md
- specs/context/contracts-index.md

### bug-fix-engineer
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- app/backend/config.py
- app/backend/services/translation_strategy.py
- app/backend/services/metrics.py
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py

### implementation-planner
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- app/backend/config.py
- contracts/business/business-rules.md

### backend-engineer
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- app/backend/config.py

### test-strategist
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py

### contract-reviewer
- specs/changes/p1-sentence-mode-fix/
- contracts/business/business-rules.md

### qa-reviewer
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/processors/docx_processor.py
    - app/backend/processors/xlsx_processor.py
    - app/backend/processors/pptx_processor.py
  reason: Confirm verify_and_fill_tmap call-site contract if integration-test wiring is unclear.
  status: withdrawn
  resolution: Not needed — backend-engineer confirmed via translation_verification.py that verify_and_fill_tmap uses the tmap KEY for retry; processor call-sites did not need reading.

## Approved Expansions
-
