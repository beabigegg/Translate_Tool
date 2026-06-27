# Change Classification

## Change Types
- primary: test-infrastructure-add (test-only feature)
- secondary: none

## Risk Level
- low

## Impact Radius
- isolated (test suite only)

## Tier
- 4

## Architecture Review Required
- no
- reason: n/a — no module boundaries change, no production data-flow change, no migration/rollback decision. The metric algorithms are self-contained test utilities. `design.md` stays `no` and task `1.3` is skipped.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | net-new harness, no existing behavior to document |
| proposal.md | no | scope is fully specified in change-request |
| spec.md | no | metric definitions fit in implementation-plan |
| design.md | no | no architecture review required |
| qa-report.md | no | routine pass/fail fits agent-log/qa-reviewer.yml pointer |
| regression-report.md | no | no existing behavior modified |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | n/a |
| stress-soak-report.md | no | n/a |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none
- Data shape: none (read-only consumer of BoundingBox.render_truncated; IR contract not modified)
- Business logic: none
- CI/CD: none (Track G will wire these metrics as gates in its own separate change)

## Required Tests
- unit: yes — tests/test_layout_metrics.py covers compute_biou, check_residual_text, compute_truncation_rate with selection-style assertions
- contract: none
- integration: none
- E2E: none
- visual: none
- data-boundary: yes — degenerate inputs (empty/zero-area bboxes, missing render_truncated, mismatched source/rendered counts) must return defined values without raising
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- implementation-planner
- test-strategist
- contract-reviewer
- qa-reviewer

## Inferred Acceptance Criteria
- AC-1: `compute_biou(source_bboxes, rendered_bboxes)` returns mean of per-source best-match IoU as float in [0.0, 1.0]; identical bbox sets return 1.0 and fully disjoint sets return 0.0.
- AC-2: `compute_biou` handles degenerate input (empty source list, empty rendered list, zero-area boxes) with a defined return value and no exception.
- AC-3: `check_residual_text(page, whiteover_bboxes)` returns a list of per-region records flagging text leaking through each whiteover region; a clean page returns an empty list.
- AC-4: `compute_truncation_rate(elements)` returns a dict with truncated ratio (truncated count / total) and `overflow_area_sum`; all-truncated yields ratio 1.0, none-truncated yields 0.0.
- AC-5: A deterministic 1-page `simple_test.pdf` fixture is committed under `tests/fixtures/golden/` and reproducible across CI runners.
- AC-6: `tests/test_layout_metrics.py` uses selection-style assertions (which bbox matched, not just count) and passes under `pytest` from project root.
- AC-7: No file under `app/backend/` or `app/frontend/` is modified; the metric modules are importable as `from tests.metrics.biou import compute_biou` etc.

## Tasks Not Applicable
- not-applicable: 1.3 (no architecture review), 2.1 (no API contract), 2.2 (no CSS contract), 2.3 (no env contract), 2.4 (no data contract), 2.5 (no business contract), 2.6 (no CI contract), 3.2 (no integration tests), 3.3 (no E2E tests), 3.5 (no stress/soak tests), 4.2 (no frontend), 4.3 (no env/deploy), 4.4 (no CI workflows), 5.1 (no UI/UX review), 5.2 (no visual review), 6.3 (no informational gates), 6.4 (no nightly/manual gates)

## Clarifications or Assumptions
- Tier-floor-override required: words "regression gates", "metrics", "harness" can trip tier-floor false-positives (see promoted learnings). Apply tier-floor-override with rationale: "Pure test-infrastructure addition; no production code, contract, API, env, or CI-pipeline change; metrics are wired as gates by Track G in a separate change."
- This change does NOT author a CI gate entry — it only provides importable metric modules.
- `render_truncated` already exists on BoundingBox (confirmed by ADR 0004 and p2-text-expansion), so no IR change needed.
- PDF fixture must be generated programmatically (ReportLab or fitz) at fixture-create time and committed, so CI does not depend on external downloads.

## Context Manifest Draft

### Affected Surfaces
- test suite (tests/metrics/, tests/fixtures/golden/)
- read-only reference: IR data model (BoundingBox)

### Allowed Paths
- specs/changes/layout-fidelity-metrics/
- specs/context/project-map.md
- specs/context/contracts-index.md
- tests/metrics/
- tests/fixtures/golden/
- tests/test_layout_metrics.py
- tests/conftest.py
- app/backend/models/translatable_document.py

### Agent Work Packets

#### implementation-planner
- specs/changes/layout-fidelity-metrics/
- specs/context/project-map.md
- app/backend/models/translatable_document.py

#### test-strategist
- specs/changes/layout-fidelity-metrics/
- tests/metrics/
- tests/fixtures/golden/
- tests/test_layout_metrics.py
- tests/conftest.py
- app/backend/models/translatable_document.py

#### contract-reviewer
- specs/changes/layout-fidelity-metrics/
- specs/context/contracts-index.md
- app/backend/models/translatable_document.py

#### qa-reviewer
- specs/changes/layout-fidelity-metrics/
- tests/metrics/
- tests/test_layout_metrics.py

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/renderers/bbox_reflow.py
    - app/backend/utils/bbox_utils.py
  reason: If implementer needs existing bbox/IoU geometry conventions to keep metric consistent with renderer output. Leave pending; approve only if translatable_document.py is insufficient.
  status: pending
