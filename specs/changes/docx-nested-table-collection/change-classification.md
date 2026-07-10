# Change Classification

## Change Types
- primary: business-logic-change, feature-enhancement
- secondary: bug-fix (originating symptom: silent partial DOCX translation)

## Lane
- feature

Lane is `feature`, not `bug-fix`. The origin is symptom-driven — the user described the document shape and nobody had checked — but the fix requires contract changes (BR-81's dedup axis, plus a new routing/collection rule), which promotes it out of the pure bug-fix lane and forces the contract path. The originating symptom is recorded as a secondary `bug-fix` change type.

## Atomic-split assessment

**No split.** The classifier evaluated the four triggers and none fires:

- *Cross-feature*: the three sub-items — collect nested-table cells, reroute a layout-frame cell's prose to the body path, fix merged-cell duplication — are the same symptom surfacing in the same `<w:tbl>` walk in one file.
- *Cross-surface*: one surface (the DOCX collection path) plus its shared serialization tail.
- *Contract-heavy*: two contracts, not five.
- *Task-heavy*: borderline, under threshold.

Splitting the merged-cell fix out would fork one emit loop across two changes and duplicate the synthetic fixture for little rollback benefit. If `spec-architect` finds the BR-81 axis genuinely independent, it may flag a split in `design.md`.

## Risk Level
- medium

## Impact Radius
- cross-module

The DOCX `<w:tbl>` collection path runs on every DOCX job and feeds the shared table-serializer and `json_translation` payload path. The dominant risk is **not** the strictly-additive text collection — that only increases what reaches the LLM. It is the new **layout-frame routing decision**, which can silently reroute a genuine multi-column table cell to the body path and lose its row context. That is a quality regression neither sample document would necessarily catch. Held above module-level by that plus a contract touch and four open design questions; below system-wide because there is no migration, no auth or payments, it is DOCX-only, and a kill switch already exists upstream.

## Tier
- 2

## Architecture Review Required
- yes
- reason: four genuine, coupled design decisions cannot be deferred to implementation. (1) Whether "layout frame" is a decidable property or a heuristic, and the tie-break when the signals disagree — full-width span, contains-nested-table, many-direct-paragraphs. Getting this wrong in either direction is a defect. (2) Whether nesting recurses arbitrarily or one level, and the depth guard. (3) How a nested table's identity and coordinate space are carried: `table_id = id(child_element)` is per-table, so an inner table needs its own `table_id` and its own payload rather than being merged into the outer table's coordinate space. (4) Whether the merged-cell fix mutates BR-81's `(tgt, text, col)` key or dedupes on the underlying `<w:tc>` before emitting. `spec-architect` writes `design.md` before `implementation-planner` runs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Already quantified in change-request.md (per-document drop percentages, the 52-vs-49 cell count, the verified walk trace). A second copy would be a second source of truth. |
| proposal.md | no | No separate product investigation; the desired behavior is defined. |
| spec.md | no | Fits in design.md plus implementation-plan.md. |
| design.md | yes | Architecture Review is yes; four open questions must be decided before planning. |
| qa-report.md | no | Routine pass/fail goes in agent-log/qa-reviewer.yml; promote only on a blocking or approved-with-risk finding. |
| regression-report.md | yes | This modifies behavior on a path every DOCX job uses, and the layout-frame heuristic carries a specific silent-regression risk (a real table cell rerouted to the body path, undetectable by the two sample documents). Durable evidence of the guarded false-positive cases is warranted. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | No interaction fuzz surface. |
| stress-soak-report.md | no | Call volume and batching are explicitly out of scope. |

Artifact minimization: prefer optional `agent-log/*.yml` pointers for routine review evidence; later artifacts reference earlier ones by path/section/id.

## Required Contracts
- API: none
- CSS/UI: none
- Env: none — no change to `JSON_STRUCTURED_TRANSLATION_ENABLED` or any variable. Do not let env-vocabulary tier-floor false positives fire here.
- Data shape: yes — `contracts/data/data-shape-contract.md` §Table Serialization Wire Format. The coordinate JSON cell list (0.18.0) has no `num_rows × num_cols` constraint, which is exactly what lets an inner table ship as its own payload. The consumers table already names `docx_processor.py` (verified: it appears twice). Expect a documented note on nested-table identity and payload boundaries, and on the legacy pipe-grid degrade path. Bump `schema-version` from the LIVE value (**0.18.0**, read from disk). Confirm whether the wire shape itself is unchanged (likely) or whether only the consumer and behavior notes move.
- Business logic: yes — `contracts/business/business-rules.md`. A new rule (or a BR-81 extension) for layout-frame routing and nested-table collection. BR-68 (numeric passthrough) and BR-79..BR-83 (whole-table serialization and fallback) are governing context to reconcile, not necessarily to mutate. Bump `schema-version` from the LIVE value (**0.30.0**, read from disk).
- CI/CD: none

**Important reading of BR-81, verified against the live contract before this file was written.** BR-81's key is `(tgt, text, col)`, and Table T rows 364-365 make its intent explicit: *the same source text appearing in column X and column Y is translated independently*. That is a deliberate design choice about **different columns**. A merged cell is **one `<w:tc>` spanning several columns** — a different axis entirely. Deduplicating on `<w:tc>` identity before emitting segments therefore very likely does **not** require changing BR-81's key. `spec-architect` should confirm or refute this rather than assume the key must move.

## Required Tests
- unit: yes — the walk collects nested-table cells (recursive-walk character parity); a merged cell emits exactly one segment; the layout-frame versus real-table routing decision.
- contract: yes — dedup on `<w:tc>` identity; data-shape wire-format and consumers assertions; the new routing rule.
- integration: yes — full `docx_processor` collection through to a serialized payload, for a synthetic nested `.docx` (outer 1×1 frame plus inner 2×2 real table).
- E2E: no — the real files in `docs/TEST_DOC/` are untracked and no test may depend on them. Integration on a self-built fixture is the equivalent.
- visual: no
- data-boundary: yes — nested-table payloads, and the legacy `JSON_STRUCTURED_TRANSLATION_ENABLED=0` pipe-grid degrade path (a nested table cannot occupy the `num_rows × num_cols` matrix; assert it degrades sanely rather than crashing).
- resilience: yes (scoped) — a recursion depth-guard test: a document nested beyond the supported depth terminates safely.
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
- `spec-architect` — resolves the four open questions in `design.md` before planning.
- `contract-reviewer` — the new rule plus any BR-81 reconciliation in `business-rules.md`, and the `data-shape-contract.md` notes; verifies every `schema-version` bump is computed from the live value.
- `test-strategist` — builds the self-contained nested `.docx` fixture, the recursive-walk character-parity assertion (asserted on collected segment content, never on an internal attribute), the false-positive routing guard, and the depth guard.
- `implementation-planner` — turns design, contract deltas and test plan into the execution packet; verifies every named seam against live source.
- `backend-engineer` — implements the `<w:tbl>` walk recursion, layout-frame routing, and `<w:tc>` dedup. Must confirm any new `table_id` or payload actually reaches the serializer — accepting a value is not delivering it.
- `qa-reviewer` — release readiness; confirms zero character drop on the fixture, single translation of the merged cell, and green single-level table regression.

## Inferred Acceptance Criteria
- AC-1: For a self-built nested `.docx` fixture (outer 1×1 layout frame plus inner 2×2 real table), collected-segment characters equal a full recursive walk of the document — zero characters silently dropped — asserted on collected segment content, never on an internal attribute.
- AC-2: An outer cell identified as a layout frame contributes its direct paragraphs to the body path, and each nested real table it holds is emitted as its own table payload with its own `table_id`, rather than the whole cell being sent as one giant table cell.
- AC-3: A merged cell spanning N columns is translated exactly once. A fixture reproducing the real document's shape emits one segment for the merged body cell, not four; a table with 49 distinct `<w:tc>` elements emits 49 cell segments, not 52.
- AC-4: A genuine multi-column, non-frame table cell is NOT rerouted to the body path. A fixture with a real multi-column table keeps its cells on the table path with row context intact — the false-positive routing guard.
- AC-5: Nested-table recursion is bounded by an explicit depth guard; a fixture nested beyond the supported depth terminates safely without infinite recursion.
- AC-6: With `JSON_STRUCTURED_TRANSLATION_ENABLED=0` (the frozen legacy pipe-grid), the change degrades sanely — a nested table does not crash that path even though it cannot occupy the `num_rows × num_cols` matrix.
- AC-7: Existing single-level DOCX table tests remain green, and BR-81 dedup for non-merged cells is unchanged.
- AC-8: No test depends on `docs/TEST_DOC/`. Every fixture is constructed by the test itself, and the directory stays untracked.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.3, 2.6, 3.4, 3.5, 4.2, 4.4, 5.1, 5.2

Rationale: 2.1 no API surface; 2.2 no CSS/UI; 2.3 no env variable touched; 2.6 no CI/CD contract; 3.4 no fuzz/monkey surface; 3.5 no stress/soak surface; 4.2 no frontend; 4.4 existing CI gates suffice; 5.1/5.2 no UI. **Task 1.3 (design) is APPLICABLE and must not be skipped.**

## Clarifications or Assumptions
- Single change, not a split. If `spec-architect` finds the BR-81 axis genuinely independent of nested-table collection, it may propose isolating it.
- Assumption to be confirmed, not asserted: no wire-format mutation is needed, because the 0.18.0 coordinate cell list already has no shape constraint. The data-shape change is expected to be consumer and behavior notes plus a version bump. `spec-architect` and `contract-reviewer` must confirm or correct.
- Corrections applied by main Claude before writing this file, after grepping: (1) the classifier's CER-001 globs `tests/test_docx_table*.py` and `tests/test_passthrough*.py` **match nothing** — it said so itself and did not invent filenames, which was the right call. The real table tests are `tests/test_table_serialization.py` and `tests/test_table_context_translation.py`. DOCX table-cell collection is exercised by `tests/test_output_mode_processors.py`, `tests/test_translation_service.py`, `tests/test_table_context_translation.py` and `tests/test_orchestrator_phase0.py`. BR-81 dedup is exercised by `tests/test_docx_parser.py::test_parse_deduplication` and `tests/test_translatable_document.py`. (2) Every source path the classifier named exists on disk. (3) The data-shape consumers table does already name `docx_processor.py`.
