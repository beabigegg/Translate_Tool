# Change Classification

## Change Types
- primary: feature-enhancement, business-logic-change
- secondary: data-shape-change (truncation marker IR boundary), refactor (single-path enforcement)

## Risk Level
- medium

## Impact Radius
- cross-module

## Tier
- 2

## Tier Floor Override
yes — `cdd-kit gate` tier-floor heuristics will fire on vocabulary in this change: "cache" (font buffer LRU cache), "fallback" / "fallback chain", and dual-path refactor wording. None of these introduce a secret, env var, schema migration, or `ALGORITHM=COPY` DDL. This change modifies in-process rendering logic and a font-selection helper only; no datastore migration, no env/secret change, no API endpoint change. Tier 2 is correct per cross-module rendering blast radius.

## Architecture Review Required
- yes
- reason: Non-obvious design decisions must be recorded before implementation: (1) priority cascade ordering and per-step thresholds (font-size → line-spacing → letter-spacing → controlled overflow → marked truncation); (2) metric-compatible fallback chain heuristic (x-height/cap-height/advance-width selection, Noto as standard fallback) and interaction with existing per-language Noto loading and P1 font LRU cache; (3) truncation-marker representation and IR/data-shape boundary ownership; (4) expansion-factor table coverage and default policy for non en→de/es/fr pairs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current "shrink to ~4pt then truncate" behavior fully described in change-request; regression scope in test-plan |
| proposal.md | no | Scope settled by improvement plan |
| spec.md | no | Behavior decisions fit in design.md + implementation-plan |
| design.md | yes | Architecture Review Required = yes; cascade ordering, fallback heuristic, truncation-marker IR representation, expansion-table policy are non-obvious decisions on a shared path |
| qa-report.md | no | Promote only if a blocking finding arises |
| regression-report.md | no | Golden-regression evidence via test runs + agent log; promote only if a regression is found and accepted |
| visual-review-report.md | yes | Change judged on rendered visual output (0 overflow / 0 tofu); durable visual evidence bundle for en→de/es benchmark is primary acceptance proof |
| monkey-test-report.md | no | No interactive UI surface |
| stress-soak-report.md | no | No high-load / long-running runtime surface |

## Required Contracts
- API: none (no endpoint/schema change)
- CSS/UI: none (backend render output, not web UI styling)
- Env: none (no new env var/secret; font LRU cache is in-process)
- Data shape: contracts/data/data-shape-contract.md — truncation marker representation in IR + renderer IR-consumption contract (Known consumers table)
- Business logic: contracts/business/business-rules.md — expansion-factor lookup tables, fit cascade priority order, truncation-as-last-resort + marking policy, metric-fallback selection policy
- CI/CD: contracts/ci/ci-gate-contract.md — review only if a new benchmark gate is added

## Required Tests
- unit: tests/test_text_region_renderer.py (cascade ordering, threshold steps, marked truncation), tests/test_font_utils.py (metric-compatibility selection, Noto fallback, LRU cache reuse)
- contract: business-rule assertions for expansion factors + truncation policy; data-shape assertion for truncation marker field
- integration: tests/test_renderer_convergence.py (per-backend wiring via mock.patch, single-path enforcement per AC-6)
- E2E: none
- visual: en→de/es expansion benchmark render comparison (0 overflow, 0 tofu) — visual-reviewer evidence bundle
- data-boundary: truncation-marker presence/shape and missing-glyph handling at IR boundary; against tests/test_golden_regression.py golden set
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
1. spec-architect — write design.md (cascade ordering, fallback heuristic, truncation-marker representation, expansion-table policy)
2. contract-reviewer — update business-rules.md (expansion factors, cascade policy, truncation policy) and data-shape-contract.md (truncation marker + IR-consumption table)
3. test-strategist — author test-plan.md with AC→test mapping
4. ci-cd-gatekeeper — write ci-gates.md
5. implementation-planner — write implementation-plan.md after all above are ready
6. backend-engineer — implement text_region_renderer.py expansion cascade and font_utils.py fallback chain
7. visual-reviewer — confirm 0 overflow (en→de/es), 0 tofu; write visual-review-report.md
8. qa-reviewer — release readiness decision

## Inferred Acceptance Criteria
- AC-1: For the en→de expansion benchmark (+30%), rendered output has 0 bbox overflow across the golden sample set.
- AC-2: For the en→es expansion benchmark (+25%), rendered output has 0 bbox overflow across the golden sample set.
- AC-3: Target-language glyphs that the primary language font lacks render with a metric-compatible fallback font (Noto as standard fallback) and produce 0 tofu boxes in the benchmark set.
- AC-4: When fitting fails, the renderer applies the cascade in order (font-size → line-spacing → letter-spacing → controlled overflow into adjacent whitespace) and only truncates as the last resort.
- AC-5: Every truncation is marked in a machine-readable way consumable by the QA safety net / human review (no silent truncation).
- AC-6: Implementation lives only on the single converged fitz path + shared bbox_reflow.py; no duplicated logic in any legacy dual path (verified by consumer-import grep and per-backend mock assertions).
- AC-7: Metric-compatible fallback selection reuses existing per-language Noto loading and the P1 font buffer LRU cache (no redundant font I/O).
- AC-8: Language pairs outside en→de/es/fr resolve to a documented default expansion factor (resolves the Open Question).

## Tasks Not Applicable
- not-applicable: 2.1 (no API endpoint/schema change), 2.2 (no CSS/UI surface), 2.3 (no env var/secret change), 3.3 (no E2E/resilience surface), 3.4 (no monkey/fuzz surface), 3.5 (no stress/soak surface), 4.2 (no frontend change), 4.3 (no env/deploy change), 5.1 (no UI/UX surface), 6.3 (no informational gates), 6.4 (no nightly/weekly/manual gates)

## Clarifications or Assumptions
- Assumption: truncation marker is carried in the IR (translatable_document.py) and therefore touches the data-shape contract; if purely a render-time annotation, data-shape contract downgrades to review-only — spec-architect to settle in design.md.
- Assumption: expansion benchmark extends the existing golden-regression gate; if a separate CI gate workflow is added, ci-cd-gatekeeper must also update contracts/ci/ci-gate-contract.md and .github/workflows/contract-driven-gates.yml.
- Open Question (AC-8): expansion-factor table coverage for non en→de/es/fr pairs defaults to a documented value; spec-architect to fix the default in design.md.

## Context Manifest Draft

### Affected Surfaces
- Backend text-region rendering (expansion / fit cascade)
- Backend font selection (metric-compatible fallback chain)
- Shared reflow path (bbox_reflow.py) and converged fitz renderer
- IR / data-shape boundary (truncation marker)

### Allowed Paths
- specs/changes/p2-text-expansion/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/text_region_renderer.py
- app/backend/utils/font_utils.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/renderers/__init__.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/text_utils.py
- app/backend/fonts/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- tests/test_text_region_renderer.py
- tests/test_font_utils.py
- tests/test_renderer_convergence.py
- tests/test_golden_regression.py
- tests/fixtures/golden/

### Agent Work Packets

#### spec-architect
- specs/changes/p2-text-expansion/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/utils/font_utils.py
- app/backend/models/translatable_document.py

#### contract-reviewer
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md

#### test-strategist
- specs/changes/p2-text-expansion/
- tests/test_text_region_renderer.py
- tests/test_font_utils.py
- tests/test_renderer_convergence.py
- tests/test_golden_regression.py
- tests/fixtures/golden/
- app/backend/renderers/text_region_renderer.py
- app/backend/utils/font_utils.py

#### ci-cd-gatekeeper
- specs/changes/p2-text-expansion/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml

#### implementation-planner
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/utils/font_utils.py
- app/backend/models/translatable_document.py
- tests/test_text_region_renderer.py
- tests/test_font_utils.py

#### backend-engineer
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/utils/font_utils.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/text_utils.py
- app/backend/models/translatable_document.py
- app/backend/fonts/

#### visual-reviewer
- specs/changes/p2-text-expansion/
- tests/fixtures/golden/
- tests/test_golden_regression.py

#### qa-reviewer
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/renderers/coordinate_renderer.py
    - app/backend/renderers/inline_renderer.py
    - app/backend/renderers/pdf_generator.py
  reason: verify no duplicated expansion logic in legacy/dual render paths (AC-6); confirm consumers route through shared bbox_reflow path
  status: pending
