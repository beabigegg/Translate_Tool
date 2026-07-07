# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- PDF renderer — side-by-side + ReportLab-fallback text-region rendering (wrap gap)
- PDF parser — table detection + cell bbox correction (shared upstream defect)
- Shared PDF layout IR — `bbox_reflow` consumed identically by both modes
- Business-rules contract — BR-40 cascade-path-restriction

## Allowed Paths
- specs/changes/pdf-text-overflow-fix/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/utils/font_utils.py
- app/backend/utils/bbox_utils.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- app/backend/processors/pdf_processor.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_font_utils.py
- tests/test_coordinate_renderer.py
- tests/test_inline_renderer.py
- tests/test_pdf_parser.py
- tests/test_pdf_layout_table_fixes.py
- tests/test_pdf_layout_refactor.py
- tests/test_pdf_generator.py
- tests/test_pdf_render_warnings.py
- tests/test_text_region_renderer.py
- tests/test_renderer_convergence.py
- tests/fixtures/golden/pdf/
- tests/fixtures/test.pdf
- tests/fixtures/test_multiline.pdf
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json

## Required Contracts
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Required Tests
- tests/test_font_utils.py
- tests/test_coordinate_renderer.py
- tests/test_inline_renderer.py
- tests/test_pdf_parser.py
- tests/test_pdf_layout_table_fixes.py
- tests/test_pdf_layout_refactor.py
- tests/test_pdf_generator.py
- tests/test_pdf_render_warnings.py
- tests/test_text_region_renderer.py
- tests/test_renderer_convergence.py
- tests/fixtures/golden/pdf/

## Agent Work Packets

### change-classifier
- specs/changes/pdf-text-overflow-fix/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/pdf-text-overflow-fix/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/parsers/pdf_parser.py
- app/backend/utils/font_utils.py
- app/backend/models/translatable_document.py
- app/backend/config.py

### contract-reviewer
- specs/changes/pdf-text-overflow-fix/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### test-strategist
- specs/changes/pdf-text-overflow-fix/
- tests/test_font_utils.py
- tests/test_coordinate_renderer.py
- tests/test_inline_renderer.py
- tests/test_pdf_parser.py
- tests/test_pdf_layout_table_fixes.py
- tests/test_pdf_layout_refactor.py
- tests/test_pdf_generator.py
- tests/test_pdf_render_warnings.py
- tests/test_text_region_renderer.py
- tests/test_renderer_convergence.py
- tests/fixtures/golden/pdf/

### implementation-planner
- specs/changes/pdf-text-overflow-fix/
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/parsers/pdf_parser.py
- app/backend/utils/font_utils.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Context Expansion Requests
- request-id: CER-003
  requested_paths:
    - contracts/env/env-contract.md
    - contracts/env/.env.example.template
    - contracts/env/env.schema.json
  reason: Scope amendment (AC-9/10/11) — implementation-planner adopted a new PDF_TABLE_ROW_GROWTH_ENABLED config flag (kill-switch for the HIGH-risk overlay-background-collision issue in BR-100's row-growth pre-pass). Not originally scoped since change-classification.md's initial "Env: none" predates this decision.
  status: approved

- request-id: CER-001
  requested_paths:
    - tests/test_text_region_renderer.py
  reason: project-map.md truncates the test-file list; this is the wrap/single-path test file for render_text_region, needed by spec-architect/test-strategist to extend wrap coverage to side-by-side/fallback.
  status: approved

- request-id: CER-002
  requested_paths:
    - specs/archive/2026/p3-table-structure/design.md
  reason: change-request.md cites this archived design's explicit "renderer-side follow-up if PDF table re-rendering is added later" deferral as the boundary for the TABLE_RECOGNITION non-goal.
  status: rejected — `.cdd/context-policy.json`'s `forbiddenPaths` baseline lists `specs/archive/**` as a HARD, non-overridable block, identical in kind to the `specs/changes/*` cross-change block already rejected elsewhere this session. No CER can approve a read under `specs/archive/**`. Main Claude briefs spec-architect in-prompt with the archived design's relevant finding instead (already captured via this session's own Explore investigation: `specs/archive/2026/p3-table-structure/design.md:41` — "D3 tab/newline reconstruction is lossy… but renderers must consume cells (not the flattened string) for coordinate placement — flag for renderer-side follow-up if PDF table re-rendering is added later.").

## Approved Expansions
- tests/test_text_region_renderer.py
