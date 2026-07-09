# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- `app/backend/processors/orchestrator.py` — `_sample_file_text`, `_detect_document_context` (primary)
- Legacy `.xls` sampling / LibreOffice conversion reuse — `app/backend/processors/xlsx_processor.py`, `app/backend/processors/libreoffice_helpers.py`
- `.docx` table-text sampling — `app/backend/processors/docx_processor.py`, `app/backend/parsers/docx_parser.py`
- `.pptx` table/graphic-frame sampling — `app/backend/processors/pptx_processor.py`, `app/backend/parsers/pptx_parser.py`
- Context prompt assembly / observability — `app/backend/services/context_prompts.py`, `app/backend/utils/logging_utils.py`, `app/backend/config.py`
- Business rule BR-109 — `contracts/business/business-rules.md`

## Allowed Paths
- specs/changes/doc-context-sampling-fix/
- specs/context/project-map.md
- specs/context/contracts-index.md
- .cdd/code-map.yml
- app/backend/processors/orchestrator.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/services/context_prompts.py
- app/backend/utils/logging_utils.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0016-context-out-of-band-system-channel.md
- tests/test_orchestrator_context_detection.py
- tests/test_context_prompt_i18n.py
- tests/test_context_prefix_bleed.py
- tests/test_orchestrator_phase0.py
- tests/test_docx_parser.py
- tests/test_libreoffice_helpers.py
- tests/conftest.py

## Required Contracts
- contracts/business/business-rules.md (BR-109 sub-rule for valid-sample coverage + observability)
- contracts/CHANGELOG.md (schema-version bump entry)

## Required Tests
- tests/test_orchestrator_context_detection.py (extend for xls / table-only docx / pptx sampling + INFO logging)
- tests/test_context_prompt_i18n.py (regression: preamble still assembled correctly once sample is non-empty)
- new unit + data-boundary tests for `_sample_file_text` per-format branches and graceful no-preamble degradation

## Agent Work Packets

### change-classifier
- specs/changes/doc-context-sampling-fix/
- specs/context/project-map.md
- specs/context/contracts-index.md

### bug-fix-engineer
- specs/changes/doc-context-sampling-fix/
- .cdd/code-map.yml
- app/backend/processors/orchestrator.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/services/context_prompts.py
- app/backend/utils/logging_utils.py
- app/backend/config.py
- tests/test_orchestrator_context_detection.py
- tests/conftest.py

### backend-engineer
- specs/changes/doc-context-sampling-fix/
- .cdd/code-map.yml
- app/backend/processors/orchestrator.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/services/context_prompts.py
- app/backend/utils/logging_utils.py
- app/backend/config.py
- tests/test_orchestrator_context_detection.py

### implementation-planner
- specs/changes/doc-context-sampling-fix/
- .cdd/code-map.yml
- app/backend/processors/orchestrator.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- contracts/business/business-rules.md
- docs/adr/0016-context-out-of-band-system-channel.md
- tests/test_orchestrator_context_detection.py

### test-strategist
- specs/changes/doc-context-sampling-fix/
- .cdd/code-map.yml
- app/backend/processors/orchestrator.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prompt_i18n.py
- tests/test_context_prefix_bleed.py
- tests/test_orchestrator_phase0.py
- tests/test_docx_parser.py
- tests/test_libreoffice_helpers.py
- tests/conftest.py

### ci-cd-gatekeeper
- specs/changes/doc-context-sampling-fix/
- tests/test_orchestrator_context_detection.py

### contract-reviewer
- specs/changes/doc-context-sampling-fix/
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0016-context-out-of-band-system-channel.md

### qa-reviewer
- specs/changes/doc-context-sampling-fix/
- tests/test_orchestrator_context_detection.py
- tests/test_context_prompt_i18n.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - tests/test_xlsx_processor.py
    - tests/test_pptx_parser.py
  reason: project-map.md truncates the tests directory, so a test file exercising `_sample_file_text` or the pptx/xlsx sampling surfaces may exist that the classifier could not see. Raise a new CER before reading any tests/ file not listed in Allowed Paths.
  status: withdrawn
  note: never exercised — test-strategist and bug-fix-engineer kept every new fixture self-contained inside tests/test_orchestrator_context_detection.py, so no unlisted tests/ file was read.

- request-id: CER-002
  requested_paths:
    - .cdd/code-map.yml
  reason: to confirm the exact `_sample_file_text` / `_detect_document_context` seam signatures and downstream readers before wiring (per the "no-shell planning agents can assert nonexistent seams" learning).
  status: approved

## Approved Expansions
- CER-002 — `.cdd/code-map.yml` granted up front and added to Allowed Paths and to the planning/implementation work packets. Main Claude has independently verified on disk that every source and test path named in this manifest exists.
