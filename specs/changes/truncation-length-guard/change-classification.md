# Change Classification

## Change Types
- primary: business-logic-change (new translation-acceptance behavior + new BR for the length guard and its recovery)
- secondary: feature-add (new shared, script-composition-aware length-guard helper reused by two acceptance seams)

## Lane
- feature

Known root cause and code location (docx_processor.py ~L1093; table_serializer.parse_json L159) — not a symptom hunt. It is a designed new capability (calibrated length model + new shared helper + new BR + new ADR). The user explicitly requested spec-architect + an ADR.

## Atomic-split assessment
No split. The cell-path guard and the body/segment-path guard invoke the SAME shared helper (composition length model + recovery). Splitting would duplicate the calibration model and fail-safe logic. One change-type family, ≤2 contracts, one risk surface.

## Risk Level
- high

The guard runs at the translation-acceptance seam on EVERY job, and the user-named hazard is that a false positive re-translates a correct translation — worse than the bug. Calibration shows 0% FP at k=0.3 but on ONE dominant language pair (→Vietnamese, CJK-heavy), so the fail-safe design for unknown targets is load-bearing and unproven on other pairs.

## Impact Radius
- cross-module (docx_processor.py, table_serializer.py, json_translation.py, translation_service.py, text_utils.py, config.py, and a new shared helper consumed by all)

## Tier
- 1

High risk × cross-module. Bounded to the translation-acceptance path with a fail-safe design (not Tier 0 system-wide), but every-job reach plus the false-positive-makes-it-worse hazard classifies upward from 2 to 1.

## Architecture Review Required
- yes
- reason: spec-architect owns the load-bearing open decisions: (1) guard placement (cell-path only vs body/segment path too); (2) per-target coefficients vs one conservative default + the exact fail-safe rule for unknown targets; (3) recovery action (split-and-retranslate vs retry-same) + the retry bound that must never loop; (4) mixed-composition (cjk+latin+numeric) length estimation; (5) interaction with BR-82 fallback, BR-68 passthrough, BR-108 meta-refusal; (6) IR-marker reuse — `render_truncated` (ADR-0004, BR-38) exists but denotes RENDER-time bbox truncation, a different concept; decide reuse-vs-new. New ADR-0020 (0019 is the highest).

## Required Agents
- spec-architect — owns the 6 open decisions; writes design.md + ADR-0020. Runs first.
- contract-reviewer — new BR + any data-shape change
- test-strategist — calibration-boundary fixtures, AC→test mapping, data-boundary/resilience suites
- ci-cd-gatekeeper — ci-gates.md
- implementation-planner — execution packet; MUST grep-verify every seam + the new-module path before wiring
- backend-engineer — shared guard + wiring into both seams + config.py constants
- monkey-test-engineer — adversarial short-translation fuzz for the false-positive boundary (writes monkey-test-report.md)
- qa-reviewer — release readiness / regression sign-off

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Defect fully recorded in change-request + evidence/calibration-facts.md. |
| proposal.md | no | The coefficient/default decision belongs in design.md + ADR. |
| spec.md | no | Covered by design.md + business-rules.md. |
| design.md | yes | Architecture Review = yes; spec-architect writes model/coefficients/placement/recovery/fail-safe + ADR link. |
| qa-report.md | no | agent-log pointer unless blocking. |
| regression-report.md | yes | Behavior change at an every-job acceptance seam; durable evidence that non-truncated output is unchanged and legitimate-short outputs are not flagged. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | yes | The false-positive boundary is the load-bearing hazard; adversarial short-translation fuzz across CJK-heavy / latin-heavy / unknown-target inputs needs durable evidence. |
| stress-soak-report.md | no | Not a high-load change; bounded retries covered by unit/resilience tests. |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none — threshold `k` and coefficients `a`/`b` are `config.py` constants (mirroring `MAX_TABLE_NESTING_DEPTH`), NOT env vars. TIER-FLOOR FALSE-POSITIVE WARNING: "config", "threshold", "coefficient" will trip the env-vocab tier-floor. No env var/secret/`.env` change — use `tier-floor-override` with written rationale.
- Data shape: conditional — only if the design adds/repurposes an IR marker (`suspected_truncation`/`recovered`). `render_truncated` (ADR-0004) is a RENDER-time marker, a different concept; spec-architect decides reuse-vs-new. If any IR field is added/repurposed, `contracts/data/data-shape-contract.md` is touched and data-boundary tests required. Treat as in-scope pending the design decision.
- Business logic: yes — new BR defining (a) the composition length model `E = a·cjk + b·latin`, (b) the `translated_len < k·E` flag with fail-safe-when-unknown, (c) the recovery contract (split-and-retranslate, never replace-with-source), (d) bounded-retry / never-loop, (e) exemptions (BR-68 numeric passthrough) and interactions (BR-82, BR-108). Bump `schema-version` from the LIVE value.
- CI/CD: none

## Inferred Acceptance Criteria
- AC-1: The recorded live case (4,827-char CJK source cell → 370-char reply, ok=True) is DETECTED by the guard (0.077 < k·E at k=0.3) on both the JSON-envelope path and the legacy pipe-grid path.
- AC-2: After detection, the cell is RECOVERED by split-and-retranslate (BR-82 pattern), yielding a translated length that is a plausible multiple of the source (well above 10% of E) — recovery NEVER replaces the translation with the source text.
- AC-3: A calibration-derived fixture set of legitimate-short translations across CJK-heavy AND latin-heavy sources produces ZERO false positives at the chosen k.
- AC-4: For an unknown/uncalibrated target language (no coefficients), the guard FAILS SAFE — it does not flag, so no legitimate translation is ever re-translated for a target the model was not calibrated on.
- AC-5: BR-68 numeric/passthrough cells are exempt (never counted as truncation) by construction.
- AC-6: Recovery retries are BOUNDED and provably terminate — the retry path cannot loop; on retry exhaustion the outcome is defined (keep-and-mark), never replace-with-source.
- AC-7: Existing non-truncated output is byte-for-byte unchanged (regression): the guard does not alter acceptance for any translation whose length is above the threshold.
- AC-8: Mixed-composition sources (cjk + latin + numeric in one cell) compute E from the composition model (numeric excluded per BR-68), not from a single length ratio.

## Tasks Not Applicable
Frontend/UI implementation, UI/UX + visual review, API contract/endpoint/OpenAPI, CSS/design-token, env-contract/`.env.example`/env-schema, migration/rollback DDL, and stress/soak load-profile tasks are not applicable (backend-only, no UI/API/env surface, no high-load path). Task 1.3 (design review) IS applicable.

## Context Manifest Draft

### Affected Surfaces
- Translation acceptance — table-cell path (`table_serializer.parse_json` / `json_translation.build_table_payload`)
- Translation acceptance — body/segment path (`translation_service.translate_texts` / client `translate_once` return)
- New shared length-guard helper (composition model + recovery)
- Configuration constants (`config.py`)

### Allowed Paths
- specs/changes/truncation-length-guard/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/docx_processor.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/services/translation_service.py
- app/backend/utils/text_utils.py
- app/backend/utils/translation_verification.py
- app/backend/utils/length_guard.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/CHANGELOG.md
- docs/adr/0020-truncation-length-guard.md
- tests/test_length_guard.py
- tests/test_json_translation_body.py
- tests/test_docx_nested_tables.py

### Required Contracts
- contracts/business/business-rules.md (new BR — required)
- contracts/data/data-shape-contract.md (conditional — only if an IR marker is added or repurposed)

### Required Tests
- tests/test_length_guard.py (new — unit / boundary for the guard + recovery)
- tests/test_json_translation_body.py (body-path acceptance integration)
- tests/test_docx_nested_tables.py (cell-path acceptance / recorded-case regression)

### Context Expansion Requests
- CER-001 (approved by main Claude): read docx_processor.py L1080-1120 (BR-82 fallback recovery block), table_serializer.parse_json ~L159, json_translation.build_table_payload ~L72. Already in Allowed Paths.

### Verified by main Claude before spec-architect
- `app/backend/utils/translation_verification.py` EXISTS (candidate home for the guard); `length_guard.py` does NOT (a new-module candidate).
- `render_truncated` (models/translatable_document.py L240) is the ADR-0004/BR-38 RENDER-time marker — a different concept from LLM-reply truncation. spec-architect decides reuse-vs-new.
- Highest ADR is 0019 → new is 0020. `tests/metrics/truncation_rate.py` exists.
- Seams confirmed: `parse_json` (table_serializer L159), `translate_texts` (translation_service L237), `translate_once` (clients).
