---
change-id: p2-ir-document-model
schema-version: 0.1.0
last-changed: 2026-06-18
---

# Design: p2-ir-document-model

## Summary

This change matures the existing in-memory `TranslatableDocument` into the canonical parse→translate→render intermediary (IR) for the whole P2 layout track. It is additive-only: `ElementType` gains four region-level members (`TABLE`, `FIGURE`, `FORMULA`, `LIST`); `TranslatableElement` gains an explicit nullable `reading_order` index; and `to_dict`/`from_dict` become a guaranteed lossless, backward-compatible round-trip (bbox floats, six font fields, element_type, reading_order). No new module, persistence engine, queue, API surface, or business rule is introduced — the IR remains a plain dataclass tree serialized to/from dicts. The architectural value is decoupling: a persisted IR can be re-rendered without re-parsing and re-serialized after MT replacement without re-rendering. A new offline golden-sample dual-run harness under `tests/fixtures/golden/` locks the pre-existing fields against regression so downstream changes (`p2-layout-detection`, `p2-renderer-convergence`) can build on a stable schema.

## Affected Components

| component | file path(s) | nature of change |
|---|---|---|
| IR model | `app/backend/models/translatable_document.py` | Add 4 `ElementType` members; add `reading_order` field + (de)serialization; precedence in `get_elements_in_reading_order()` |
| PDF parser | `app/backend/parsers/pdf_parser.py` | Assign sequential `reading_order` after existing sort; retain `round(y0,10pt)` only as the sort comparator, not as the persisted order |
| DOCX parser | `app/backend/parsers/docx_parser.py` | Assign `reading_order` from extraction sequence |
| PPTX parser | `app/backend/parsers/pptx_parser.py` | Assign `reading_order` from extraction sequence |
| Renderers | `renderers/{base,coordinate_renderer,pdf_generator,text_region_renderer,inline_renderer}.py` | Consume `reading_order` via the model accessor; must not raise on `None` or on unrecognized region-level types |
| Processors | `processors/{pdf_processor,docx_processor,orchestrator,pptx_processor}.py` | `element_type` branch chains stay if/elif with a default passthrough (no exhaustive match to break) |
| Data contract | `contracts/data/data-shape-contract.md` | IR schema section (already authored) |
| CI contract | `contracts/ci/ci-gate-contract.md` | golden-sample-regression gate (already authored) |
| Golden harness | `tests/fixtures/golden/` (new) | 3–5 binary fixtures (PDF/DOCX/PPTX) + offline dual-run diff test |

## Key Decisions

- **Serialized string values use lowercase (`"table"`,`"figure"`,`"formula"`,`"list"`); Python enum member names are uppercase.** Rationale: every existing member serializes to a lowercase string (`text`, `table_cell`); persisting the new ones as literal `"TABLE"` would split the on-disk convention and make case-sensitive consumers brittle. The change-request lists member *names* (`TABLE`…), not wire values. → Rejected: uppercase wire values — inconsistent with 8 existing values, harder to reverse once fixtures are committed. (See ADR 0001.)
- **`reading_order` is `int | None`, parser-assigned, with positional fallback.** When non-null it is authoritative in `get_elements_in_reading_order()`; when null the existing `(page_num, bbox.y0, bbox.x0)` heuristic applies per element so mixed-population documents still sort deterministically. → Rejected: making it required/non-null — breaks old-format deserialization and forces every producer to populate it in one change.
- **No schema-version key in the serialized envelope.** Old vs new format is detected structurally: absence of the `reading_order` key ⇒ old format ⇒ defaults to `None`. The schema is purely additive, so a version gate would add ceremony without enabling any branch. → Rejected: embedding `schema_version` — premature; reintroduce only when a genuinely breaking shape change arrives (deprecate-2-minors policy in the data contract).
- **Region-level types are tolerated, not exhaustively handled.** Consumers keep `if/elif` chains with a passthrough default; no consumer is required to render `TABLE`/`FIGURE`/`FORMULA`/`LIST` specially in this change (that is `p2-layout-detection`/`renderer-convergence`). → Rejected: forcing every renderer to branch on new types now — couples this schema change to unrelated rendering work.
- **`from_dict` still raises `ValueError` on a genuinely unknown `element_type`; the four new values are no longer unknown.** The "must not raise on region-level types" rule is satisfied by adding them to the enum, not by swallowing invalid input. → Rejected: silently coercing unknown types to `TEXT` — masks producer bugs and corrupts round-trip fidelity.
- **Dual-run harness compares against a committed pre-change IR snapshot, not a live old code path.** Each fixture ships with a frozen `*.expected.json` (old-format serialization). The test parses with new code, serializes, and diffs field-by-field; a difference on any pre-existing field fails the gate, a `reading_order`-only difference does not. → Rejected: importing the old module at test time — requires keeping dead code on the branch and a second import path; snapshot is simpler and fully offline.

## Migration / Rollback

No data migration: the IR is in-memory and any serialized form is transient (job-scoped), never a system of record, so there is no stored corpus to migrate and no ALTER TABLE. Forward path is deploy-and-go — new code reads both old-format (no `reading_order`) and new-format dicts. Rollback is clean because new code never *requires* `reading_order`: a new-format dict fed to pre-change code is also safe except for the added key, which the old `from_dict` ignores via `**`-free explicit field access (it reads only known keys). Golden fixtures and the regression gate are the rollback safety net — if a field regresses, the gate blocks merge before release. Reverting the change is a straight code revert; no cleanup step.

## Open Risks

- Fixture sourcing: 3–5 representative PDF/DOCX/PPTX files must be license-clean and small (recommend ≤ ~200 KB each, documented ceiling in `tests/fixtures/golden/README`). Owner: test-strategist.
- PyMuPDF table detection is non-deterministic across versions; pin the parsing dependency or the golden diff may flap on `element_type` (TABLE_CELL) across CI runners. Owner: ci-cd-gatekeeper. Follow-up if flaky: normalize/exclude table-detection-derived fields from the diff with recorded rationale.
- The old pre-change `from_dict` (rollback target) must be confirmed to ignore unknown keys rather than reject them; current code reads keys explicitly, so this holds, but verify before relying on it for rollback.
