# Change Classification

## Change Types
- primary: `data-shape-change`, `refactor`
- secondary: `test-infrastructure` (golden-sample regression harness)

## Lane
- feature

## Risk Level
- high

## Impact Radius
- cross-module

## Tier
- 1

## Architecture Review Required
- yes
- reason: This defines the canonical IR data model and the (de)serialization contract that decouples three pipeline stages, with deliberate compatibility/migration trade-offs (extend-not-rewrite, `reading_order` replacing `round(y0,10pt)` heuristic, backward-compatible serialization for existing callers). It is a module-boundary and data-flow decision that downstream changes (`p2-layout-detection`, `p2-renderer-convergence`) depend on. `spec-architect` must record the IR schema, the serialization envelope/versioning, and the reading-order model in `design.md` before `implementation-planner` runs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | yes | Existing IR shape, `round(y0,10pt)` heuristic, and current `to_dict` format must be captured as compatibility baseline |
| proposal.md | no | Scope settled in change-request |
| spec.md | no | IR schema captured in design.md |
| design.md | yes | Architecture Review Required = yes; IR schema + serialization envelope + reading-order model + compatibility strategy must be designed before implementation |
| qa-report.md | yes | Tier 1 cross-module regression change; durable prose evidence of golden-sample pass/fail and approved-with-risk findings needed |
| regression-report.md | yes | Primary risk is regression across parsers/renderers/processors; new/old dual-run comparison results need durable capture |
| visual-review-report.md | no | No UI output; covered by golden-sample dual-run comparison |
| monkey-test-report.md | no | No interactive UI surface |
| stress-soak-report.md | no | Offline bounded golden-sample runs by constraint |

## Required Contracts
- API: none (no new/changed endpoints; explicit non-goal)
- CSS/UI: none
- Env: none
- Data shape: `contracts/data/data-shape-contract.md` — extend IR schema: new `ElementType` region values (`TABLE`, `FIGURE`, `FORMULA`, `LIST`), explicit `reading_order` field, serialization/deserialization envelope (bbox + font metadata + element type + reading order), and row-level/forward-compatibility rules
- Business logic: none (translation main-path behavior unchanged by constraint)
- CI/CD: `contracts/ci/ci-gate-contract.md` — register the offline golden-sample regression gate (no network, no GPU)

## Required Tests
- unit: `ElementType` new values, `reading_order` field, IR serialize/deserialize round-trip, backward-compatible deserialization, `to_dict` compatibility (`tests/test_translatable_document.py`)
- contract: IR serialized shape conforms to `data-shape-contract.md`; old-format → new-format compatibility assertions
- integration: parsers → IR → renderers round-trip; "re-render without re-parse" and "swap MT engine without re-render" decoupling paths
- E2E: no
- visual: no
- data-boundary: malformed/partial serialized IR, missing/unknown `ElementType`, missing `reading_order`, missing font metadata, empty document
- resilience: no
- fuzz/monkey: no
- stress: no
- soak: no
- golden-sample regression: new test infrastructure — 3–5 representative files per format under `tests/fixtures/golden/`, new/old dual-run comparison framework

## Required Agents
- `spec-architect` — IR schema, serialization envelope/versioning, reading-order model, compatibility strategy → `design.md` (must run before planner)
- `contract-reviewer` — update `data-shape-contract.md` and `ci-gate-contract.md` before implementation
- `test-strategist` — acceptance-criteria → test mapping, golden-sample set design, dual-run comparison framework design, data-boundary cases
- `ci-cd-gatekeeper` — wire offline golden-sample regression gate into CI
- `implementation-planner` — turns design + contracts + test plan into execution packet
- `backend-engineer` — IR model maturation, `ElementType` expansion, `reading_order`, serialize/deserialize, parser/renderer/processor adaptation
- `qa-reviewer` — release readiness, regression evidence sign-off, golden-sample pass/fail

## Inferred Acceptance Criteria
- AC-1: `ElementType` exposes at least `TABLE`, `FIGURE`, `FORMULA`, and `LIST` region types in addition to existing text-level types, and all existing `ElementType` values remain valid (no removals/renames).
- AC-2: The IR carries an explicit `reading_order` field, and `pdf_parser.py` populates it without using the `round(y0,10pt)` bucketing heuristic for ordering.
- AC-3: A `TranslatableDocument` serialized to its persisted form and deserialized back yields an equivalent IR (bbox, font metadata, element type, reading order all preserved) — round-trip fidelity.
- AC-4: A document serialized by the previous format deserializes successfully under the new code (backward compatibility), and `to_dict` output remains compatible with existing parser/renderer/processor callers.
- AC-5: "Re-render without re-parse" works: a persisted IR can be rendered without invoking any parser; "swap MT engine without re-render" works: translated text can be replaced in the IR and re-serialized without re-rendering.
- AC-6: A golden-sample set exists with 3–5 representative files each for PDF, DOCX, and PPTX under `tests/fixtures/golden/`.
- AC-7: A new/old dual-run comparison framework runs over the golden samples offline (no network, no GPU) and is wired as a CI gate, reporting per-sample pass/fail diffs.
- AC-8: The translation main-path behavior and the public API surface are unchanged (no endpoint additions/changes).

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.3, 2.5, 3.3, 3.5, 4.2, 4.3, 5.1, 5.2

## Clarifications or Assumptions
- Serialization format change is additive/backward-compatible per constraints; if design reveals unavoidable breaking shape change, re-classify.
- No `requirements.txt`/lockfile change anticipated; if dual-run comparison requires a new test dependency, document in design.md and update `requirements.txt` within this change.
- Open question: golden-sample placement and size cap — recommend `tests/fixtures/golden/<format>/` with documented per-file size ceiling; decide in design.md.
- Note: `cdd-kit gate` tier-floor may false-positive on vocabulary; if it forces a higher tier spuriously, use `tier-floor-override` with rationale that this is an additive in-memory IR + serialization change with no DB migration.

## Context Manifest Draft

### Affected Surfaces
- Document IR data model (`app/backend/models/translatable_document.py`)
- Parsers (`pdf_parser`, `docx_parser`, `pptx_parser`) — IR producers, reading-order source
- Renderers (`base`, `coordinate_renderer`, `pdf_generator`, `text_region_renderer`, `inline_renderer`) — IR consumers
- Processors / orchestrator — pipeline wiring
- Data-shape contract + CI gate contract
- Golden-sample regression fixtures + dual-run comparison test infrastructure

### Allowed Paths
- specs/changes/p2-ir-document-model/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/models/translatable_document.py
- app/backend/models/__init__.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/renderers/base.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- tests/test_translatable_document.py
- tests/test_pdf_parser.py
- tests/test_docx_parser.py
- tests/test_pptx_parser.py
- tests/test_coordinate_renderer.py
- tests/test_pdf_generator.py
- tests/test_text_region_renderer.py
- tests/test_inline_renderer.py
- tests/fixtures/
- docs/improvement-plan.md
- .github/workflows/contract-driven-gates.yml
- ci/gate-policy.md

### Agent Work Packets

#### change-classifier
- specs/changes/p2-ir-document-model/
- specs/context/project-map.md
- specs/context/contracts-index.md

#### spec-architect
- specs/changes/p2-ir-document-model/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/models/translatable_document.py
- app/backend/renderers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/base.py
- contracts/data/data-shape-contract.md
- docs/improvement-plan.md

#### contract-reviewer
- specs/changes/p2-ir-document-model/
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md

#### test-strategist
- specs/changes/p2-ir-document-model/
- tests/test_translatable_document.py
- tests/test_pdf_parser.py
- tests/test_docx_parser.py
- tests/test_pptx_parser.py
- tests/test_coordinate_renderer.py
- tests/test_pdf_generator.py
- tests/test_text_region_renderer.py
- tests/test_inline_renderer.py
- tests/fixtures/
- app/backend/models/translatable_document.py

#### ci-cd-gatekeeper
- specs/changes/p2-ir-document-model/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- ci/gate-policy.md
- tests/fixtures/

#### implementation-planner
- specs/changes/p2-ir-document-model/
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- app/backend/models/translatable_document.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/renderers/base.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py

#### backend-engineer
- specs/changes/p2-ir-document-model/
- app/backend/models/translatable_document.py
- app/backend/models/__init__.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/renderers/base.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py

#### qa-reviewer
- specs/changes/p2-ir-document-model/
- contracts/data/data-shape-contract.md
- tests/fixtures/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - tests/fixtures/golden/
  reason: Golden-sample fixture directory does not yet exist in the project map; it must be created and read by test-strategist, ci-cd-gatekeeper, and qa-reviewer. Approve creation/read scope under `tests/fixtures/golden/`.
  status: approved

- request-id: CER-002
  requested_paths:
    - .github/workflows/contract-driven-gates.yml
    - ci/gate-policy.md
  reason: CI workflow and gate policy must be edited to register the offline golden-sample regression gate (no network/GPU). Required by ci-cd-gatekeeper.
  status: approved
