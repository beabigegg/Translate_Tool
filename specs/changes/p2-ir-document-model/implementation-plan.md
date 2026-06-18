---
change-id: p2-ir-document-model
schema-version: 0.1.0
last-changed: 2026-06-18
---

# Implementation Plan: p2-ir-document-model

## Objective
Mature the in-memory `TranslatableDocument` IR into the canonical parse→translate→render intermediary: add four region-level `ElementType` members, add a nullable `reading_order` field with parser population and lossless backward-compatible (de)serialization, and stand up an offline golden-sample dual-run regression harness. Additive-only: no existing `ElementType` value, no existing `to_dict` key, and no public API/translation-path behavior may change. See `design.md` for the authoritative architecture.

## Execution Scope

### In Scope
Execute strictly in this dependency order (each step's tests are red before the next begins; Tier 0 unit/data-boundary first per `test-plan.md` §Notes):

1. **IR model core** (`app/backend/models/translatable_document.py`): add `ElementType` region members; add `reading_order: int | None` to `TranslatableElement` with `to_dict`/`from_dict` handling; update `get_elements_in_reading_order()` precedence. Foundation for all later steps.
2. **PDF parser reading-order** (`app/backend/parsers/pdf_parser.py`): assign sequential integer `reading_order` to elements after sorting; keep `round(y0,10pt)` only as a sort comparator, not as the persisted order value. Depends on step 1.
3. **DOCX / PPTX parser reading-order** (`docx_parser.py`, `pptx_parser.py`): assign `reading_order` from extraction sequence. Depends on step 1.
4. **Renderer / processor tolerance check** (renderers + processors): verify (and only minimally adjust if needed) that consumers do not raise on `reading_order is None` or on unrecognized region-level `element_type`; `element_type` branch chains stay `if/elif` with passthrough default (`design.md` Key Decisions). Depends on steps 1–3.
5. **Golden-sample harness + fixtures** (`tests/fixtures/golden/`, `tests/test_golden_regression.py`, `tests/test_ir_pipeline_decoupling.py`): commit 3–5 binary fixtures per format plus per-fixture IR snapshot, and the offline dual-run diff test. Depends on steps 1–4.

### Out of Scope
- DocLayout-YOLO / any layout-detection model integration (`p2-layout-detection`).
- Renderer convergence / any renderer rewrite (`p2-renderer-convergence`).
- Special rendering of `TABLE`/`FIGURE`/`FORMULA`/`LIST` regions — these are tolerated/passthrough only this change (`design.md` Key Decisions).
- Adding a `schema_version` key to the serialized envelope (explicitly rejected in `design.md`).
- Any API, env, CSS/UI, business-logic, DB-migration, or `requirements.txt` change (none anticipated; classification §Required Contracts marks all but data-shape + CI as none).
- OCR / formula recognition / XLSX IR extension / scanned-PDF path (`test-plan.md` §Out of Scope).
- Opportunistic refactor of parser/renderer internals beyond what `reading_order` requires.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | IR model | Add `TABLE`/`FIGURE`/`FORMULA`/`LIST` to `ElementType` (member names uppercase, wire values lowercase per `design.md` ADR 0001); keep all 8 existing members and their string values unchanged | backend-engineer |
| IP-2 | IR model | Add `reading_order: Optional[int] = None` to `TranslatableElement`; emit it in `to_dict`; read it in `from_dict` via `data.get("reading_order")` (absent ⇒ `None`) | backend-engineer |
| IP-3 | IR model | Update `get_elements_in_reading_order()` so non-null `reading_order` is authoritative and null falls back to `(page_num, bbox.y0, bbox.x0)` | backend-engineer |
| IP-4 | PDF parser | Assign sequential int `reading_order` after `_sort_by_reading_order`; `round(y0,10pt)` remains comparator only | backend-engineer |
| IP-5 | DOCX/PPTX parsers | Assign `reading_order` from extraction sequence | backend-engineer |
| IP-6 | renderers/processors | Confirm no raise on `None` reading_order or region-level types; keep `if/elif` + passthrough default; adjust only if a real break exists | backend-engineer |
| IP-7 | data contract | Correct the `ElementType` table wire-value rows for the 4 new types to lowercase to match `design.md` ADR 0001 (see Contract Updates) | contract-reviewer |
| IP-8 | test harness | Create golden fixtures + IR snapshots + dual-run diff test + decoupling test | test-strategist / backend-engineer |
| IP-9 | CI | Confirm `golden-sample-regression` job is wired offline in workflow (already applied per `ci-gates.md`) | ci-cd-gatekeeper |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Key Decisions (lowercase wire values, `int\|None` reading_order, no schema_version, tolerated region types, snapshot dual-run) | implementation constraints |
| design.md | Affected Components table | per-file nature of change |
| design.md | Open Risks (fixture sourcing, PyMuPDF table non-determinism, old `from_dict` ignores unknown keys) | risk handling |
| contracts/data/data-shape-contract.md | §Intermediate Representation (IR) — field shapes, Round-trip guarantee, Backward-compatibility rule, `to_dict` compatibility rule | serialized shape acceptance |
| contracts/ci/ci-gate-contract.md | §golden-sample-regression gate (scope, pass/fail, sample set) | gate behavior + fixture floor |
| test-plan.md | AC→test mapping + Test Names + Golden-Sample Set Design | tests to write/run |
| ci-gates.md | Required Gates table + Promotion Policy | verification commands |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/models/translatable_document.py | modify | `ElementType` (lines 14-24): add 4 region members. `TranslatableElement` (121-161): add `reading_order` field + `to_dict`/`from_dict`. `get_elements_in_reading_order()` (268-276): reading_order-first precedence with positional fallback |
| app/backend/parsers/pdf_parser.py | modify | After `_sort_by_reading_order` call (line 120) assign sequential `reading_order`; `_sort_by_reading_order` (348-368) stays comparator-only — do not persist `round(y0/10)*10` as the order value |
| app/backend/parsers/docx_parser.py | modify | Set `reading_order` from extraction sequence where `TranslatableElement`s are built (`_extract_from_container`/`parse`) |
| app/backend/parsers/pptx_parser.py | modify | Set `reading_order` from extraction sequence where elements are built (`_extract_from_slide`/`parse`) |
| app/backend/parsers/base.py | read-only | Confirm `parse` contract; change only if signature genuinely requires it (do not expand) |
| app/backend/renderers/base.py | verify (modify only if breaks) | Tolerate `None` reading_order / region types |
| app/backend/renderers/coordinate_renderer.py | verify (modify only if breaks) | same |
| app/backend/renderers/pdf_generator.py | verify (modify only if breaks) | same |
| app/backend/renderers/text_region_renderer.py | verify (modify only if breaks) | `create_text_regions_from_elements` must not assume region types |
| app/backend/renderers/inline_renderer.py | verify (modify only if breaks) | same |
| app/backend/processors/orchestrator.py | verify (modify only if breaks) | `element_type` branches stay if/elif + passthrough default |
| app/backend/processors/pdf_processor.py | verify (modify only if breaks) | `parse_pdf_to_document` consumes IR; no schema break |
| app/backend/processors/docx_processor.py | verify (modify only if breaks) | same |
| app/backend/processors/pptx_processor.py | verify (modify only if breaks) | same |
| app/backend/models/__init__.py | verify | Re-exports IR symbols; no new export needed unless a new public symbol is added (none planned) |
| app/backend/utils/bbox_utils.py | read-only | `BoundingBox` consumer; no change expected |
| app/backend/utils/font_utils.py | read-only | no change expected |
| tests/test_translatable_document.py | modify | Append `TestElementType`, `TestTranslatableElement` additions, `TestRoundTripFidelity`, `TestBackwardCompat` (test-plan.md Test Names) |
| tests/test_pdf_parser.py | modify | Append `TestReadingOrderField` |
| tests/test_ir_pipeline_decoupling.py | create | Decoupling + public-API-unchanged tests (test-plan.md Test Names) |
| tests/test_golden_regression.py | create | Inventory, per-format snapshot-stability, dual-run determinism, offline-no-network tests |
| tests/fixtures/golden/{pdf,docx,pptx}/ | create | 3–5 binary fixtures per format, ≤~200 KB each; companion per-fixture IR snapshot JSON (`{element_count, element_types:{type:count}, reading_order_present:bool}` per test-plan.md §Golden-Sample Set Design); add `README` documenting size ceiling + license provenance (design.md Open Risks) |
| .github/workflows/contract-driven-gates.yml | verify | `golden-sample-regression` job already added (ci-gates.md §Workflow Changes); confirm only |
| ci/gate-policy.md | verify | Gate policy reference; confirm only |

## Contract Updates
- API: none (explicit non-goal; classification §Required Contracts = none).
- CSS/UI: none.
- Env: none.
- Data shape: `contracts/data/data-shape-contract.md` IR section is authored. One correction required (IP-7): the §ElementType table (lines 114-117) lists new-value wire forms as `TABLE`/`FIGURE`/`FORMULA`/`LIST` (uppercase), but `design.md` ADR 0001 freezes wire values as lowercase (`"table"`,`"figure"`,`"formula"`,`"list"`) to match the 8 existing lowercase values and the golden fixtures. Contract table must be corrected to lowercase wire values before fixtures are committed. This is a contract/design conflict — resolve via contract-reviewer, not by the backend-engineer guessing.
- Business logic: none (translation main path unchanged by constraint).
- CI/CD: `contracts/ci/ci-gate-contract.md` §golden-sample-regression gate is authored; workflow job applied. Confirm offline (no network/GPU) and that a `reading_order`-only diff does not fail the gate.

## Test Execution Plan
Implementation agents generate evidence with `cdd-kit test run`; the gate validates `test-evidence.yml`. Required phase floor: `collect`, `targeted`, `changed-area`. This is a Tier 1 cross-module change, so `contract`, `quality`, and `full` triggers apply — run the full ladder before handoff. Tier 0 tests (unit/data-boundary) must be red before implementation (test-plan.md §Notes).

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_translatable_document.py::TestElementType | 4 region types present; 8 existing unchanged; unknown raises ValueError; values lowercase strings |
| AC-2 | tests/test_translatable_document.py::TestTranslatableElement | reading_order field present, defaults None, round-trips |
| AC-2 | tests/test_pdf_parser.py::TestReadingOrderField | reading_order is sequential int (not round(y0/10) product); TABLE emitted on table detect |
| AC-3 | tests/test_translatable_document.py::TestRoundTripFidelity | bbox/font/element_type/reading_order/count preserved across to_dict→from_dict |
| AC-4 | tests/test_translatable_document.py::TestBackwardCompat | old-format dicts deserialize cleanly; to_dict keys are superset of old keys |
| AC-5 | tests/test_ir_pipeline_decoupling.py | re-render without re-parse; swap MT without re-render |
| AC-6 | tests/test_golden_regression.py::test_golden_fixture_inventory | ≥3 PDF, ≥3 DOCX, ≥3 PPTX under tests/fixtures/golden/ |
| AC-7 | tests/test_golden_regression.py | per-sample snapshot stability + dual-run determinism + offline-no-network |
| AC-8 | tests/test_ir_pipeline_decoupling.py::test_public_api_unchanged | translate_pdf/docx/pptx accept same positional args |

Gate commands (ci-gates.md §Required Gates): `cdd-kit validate --contracts`; `cdd-kit gate p2-ir-document-model`; `pytest tests/ -x -q --tb=short`; `pytest tests/fixtures/golden/ --tb=short -q`.

Note: `cdd-kit test select` falls back to the `test file / command` column above; entries are bare pytest node ids / files that exist after step 5. The golden gate command in `ci-gates.md` targets `tests/fixtures/golden/`, while `test-plan.md` names the test file `tests/test_golden_regression.py`; ensure the golden tests are collected by both invocations (place the test under `tests/` and ensure fixtures dir is on the gate's collection path) — flag to ci-cd-gatekeeper if the two paths do not both collect the golden tests.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- Wire values for the 4 new `ElementType` members are lowercase (`design.md` ADR 0001), not the uppercase forms currently in the data contract table; do not resolve that conflict unilaterally — IP-7 corrects the contract.
- Do not add `schema_version` to the serialized envelope.
- Do not make any renderer branch specially on region-level types this change.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- **Contract/design wire-value conflict** (data contract uppercase vs design lowercase): blocks fixture commit if unresolved, because golden snapshots freeze the wire form. Owner: contract-reviewer (IP-7). Must land before step 5.
- **PyMuPDF table-detection non-determinism across versions** (design.md Open Risks): golden diff on `element_type`/`TABLE_CELL` may flap across CI runners. Mitigation per ci-gates.md Promotion Policy: quarantine affected sample field to informational sub-job with recorded owner/exit date — do not disable the gate. Owner: ci-cd-gatekeeper.
- **Fixture sourcing**: 3–5 license-clean, ≤~200 KB files per format must be created and committed; document ceiling + provenance in `tests/fixtures/golden/README`. Owner: test-strategist.
- **Old pre-change `from_dict` must ignore the new `reading_order` key for clean rollback**: current code reads keys explicitly (no `**`), so this holds — backend-engineer should preserve explicit-key reads and not switch to `**data` expansion.
- **Golden test collection path mismatch**: `ci-gates.md` runs `pytest tests/fixtures/golden/` but `test-plan.md` names `tests/test_golden_regression.py`; ensure both invocations collect the golden tests.
- **Code map freshness**: `.cdd/code-map.yml` generated 2026-06-17 (sources-digest present); line ranges used here verified against current source reads of the IR model and PDF parser. If the backend-engineer finds drift, re-read the target range rather than trusting the map.
