# Change Classification

## Change Types
- primary: bug-fix
- secondary: business-logic-change (translation done/fail counting and failure-marker behavior)

## Lane
- bug-fix

## Bug Symptom Type
- data

## Diagnostic Only
- no

## Bug Evidence
- symptom: SENTENCE_MODE batch path behaves inconsistently with the per-sentence path on failure marking, done/fail counting, and stop handling.
- expected behavior: SENTENCE_MODE produces a consistent block-level failure placeholder including original text, increments done/fail per segment with early stop, and honors stop_flag mid-batch and after batch via `if stopped: break`.
- actual behavior: inline sentence-level markers joined with no block placeholder; `done += len(texts_to_translate) + dedup_saved` applied once after batch even when stopped; `translate_blocks_batch` called with no stop_flag and no break out of outer targets loop.
- root cause pointer: `app/backend/services/translation_service.py` SENTENCE_MODE branch; `app/backend/utils/translation_helpers.py:385`; `app/backend/utils/translation_verification.py:49`.

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

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | defect behavior documented in Bug Evidence above |
| proposal.md | no | target behavior defined (match per-sentence path) |
| spec.md | no | no new user-facing behavior |
| design.md | no | consistency fix within existing branch; no architecture review |
| qa-report.md | no | routine pass/fail in agent-log/qa-reviewer.yml |
| regression-report.md | no | record in agent-log unless regression found |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | not Tier 0/1 |
| stress-soak-report.md | no | explicit non-goal |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: review only — `contracts/business/business-rules.md`; confirm corrected SENTENCE_MODE behavior matches documented counting/failure-marker rule or update it.
- CI/CD: none

## Required Tests
- unit: yes
- contract: none
- integration: yes
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- bug-fix-engineer
- implementation-planner
- backend-engineer
- test-strategist
- contract-reviewer
- qa-reviewer

## Inferred Acceptance Criteria
- AC-1: On batch failure in SENTENCE_MODE, the value stored in tmap for the affected block is a block-level placeholder of the form `[Translation failed|{tgt}] {original_text}` (including the original text), matching the non-SENTENCE_MODE path.
- AC-2: In SENTENCE_MODE, `done` and `fail` counts are incremented per segment within the loop, so a mid-batch stop produces the same counts as the non-SENTENCE_MODE path on identical input (no over-count from post-batch bulk increment).
- AC-3: `translate_blocks_batch` is invoked with the stop_flag in SENTENCE_MODE and halts in-progress batch work when the stop_flag is set mid-batch.
- AC-4: After a SENTENCE_MODE batch completes (or stops), an `if stopped: break` exits the outer targets loop so no further targets are processed once a stop was requested.
- AC-5: Failed blocks in SENTENCE_MODE remain identifiable and retriable via `verify_and_fill_tmap`, consistent with docx/xlsx/pptx processor behavior.
- AC-6: The `translate_texts` function signature is unchanged and all existing callers work without modification.
- AC-7: API HTTP routes and response schemas are unchanged; 389-passing baseline maintained plus new regression tests.

## Tasks Not Applicable
- not-applicable: 1.3, 2.2, 2.3, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 5.1, 5.2

## Clarifications or Assumptions
- `SENTENCE_MODE` env var already exists in `app/backend/config.py`; no new var.
- Metrics endpoint (`metrics.py`) needs verification only, not code changes.
- PDF processor `verify_and_fill_dict` is explicitly out of scope.

## Context Manifest Draft

### Affected Surfaces
- Backend translation pipeline (SENTENCE_MODE batch path)

### Allowed Paths
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

### Agent Work Packets

#### bug-fix-engineer
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

#### implementation-planner
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- app/backend/config.py
- contracts/business/business-rules.md

#### backend-engineer
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- app/backend/config.py

#### test-strategist
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- app/backend/utils/translation_verification.py
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py

#### contract-reviewer
- specs/changes/p1-sentence-mode-fix/
- contracts/business/business-rules.md

#### qa-reviewer
- specs/changes/p1-sentence-mode-fix/
- app/backend/services/translation_service.py
- tests/test_translation_strategy.py
- tests/test_translation_profiles_scenarios.py
- tests/test_metrics_counters.py

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/processors/docx_processor.py
    - app/backend/processors/xlsx_processor.py
    - app/backend/processors/pptx_processor.py
  reason: Confirm verify_and_fill_tmap call-site contract if integration-test wiring is unclear.
  status: pending
