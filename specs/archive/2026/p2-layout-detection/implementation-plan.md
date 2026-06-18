---
change-id: p2-layout-detection
schema-version: 0.1.0
last-changed: 2026-06-18
---

# Implementation Plan: p2-layout-detection

## Objective
Add a local, offline Docling heron-101 ONNX layout detector that types per-page native-PDF regions and assigns reading order onto the existing IR (`TranslatableElement.element_type` + `reading_order`), replacing the `round(y0,10pt)` bucket heuristic on the native-PDF text-layer path. Inference is local-only (no page image leaves the machine), fail-soft to the legacy heuristic, and gated by `LAYOUT_DETECTOR_ENABLED`. Implementation must follow design.md decisions D-1..D-5 verbatim; do not re-decide them.

## Execution Scope

### In Scope
- New module `app/backend/parsers/layout_detector.py` (`LayoutDetector` class; see design.md D-3/D-4).
- Inject the detector into `PyMuPDFParser.parse()` after text extraction; replace the final sort+index step on the native-PDF path.
- Config reads for `LAYOUT_DETECTOR_MODEL_PATH` and `LAYOUT_DETECTOR_ENABLED` in `app/backend/config.py`.
- Dependency manifest updates (`requirements.txt`, optionally `environment.yml`): add `onnxruntime` (CPU) + `huggingface_hub`; ensure no `ultralytics` / `onnxruntime-gpu`.
- Tests per test-plan.md §Test Files (new `tests/test_layout_detector.py`; extend `tests/test_pdf_parser.py`, `tests/test_golden_regression.py`, `tests/test_env_contract.py`).

### Out of Scope (do not implement; do not opportunistically refactor)
- Scanned / no-text-layer / OCR PDF path (P3-1).
- Formula LaTeX recovery (P3-2), table cell topology (P3-3) — regions are typed only.
- Any renderer change; any IR wire-schema change (fields already exist from `p2-ir-document-model`).
- New API endpoint or model-health surface (separate future change per change-classification.md §Clarifications).
- GPU provider correctness validation; live HuggingFace download in PR tests (Tier 3 nightly only).
- Rewriting `_extract_page_elements`, `_detect_and_mark_tables`, or `_extract_metadata` — leave intact; the detector replaces only the final sort+`reading_order` assignment (`pdf_parser.py:119-124`).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | new module | Create `layout_detector.py` with `LayoutDetector` (lazy/cached model load, `detect(page_pixmap_array, elements) -> None` writing in-place), label-map constant (D-4), 3-tier weight resolution (D-5), fail-soft (D-2), privacy boundary (D-3), `LAYOUT_DETECTOR_ENABLED` skip. | backend-engineer |
| IP-2 | parser integration | In `PyMuPDFParser.parse()` rasterise each page (`page.get_pixmap()`), invoke detector after `_extract_page_elements`/`_detect_and_mark_tables`, replace `_sort_by_reading_order`+index step on native-PDF path; retain `_sort_by_reading_order` as the fail-soft fallback. | backend-engineer |
| IP-3 | config | Add `LAYOUT_DETECTOR_MODEL_PATH` (optional, default unset) and `LAYOUT_DETECTOR_ENABLED` (default on) reads in `config.py` near the `PDF_PARSER_ENGINE` block. | backend-engineer |
| IP-4 | dependency manifest | Add `onnxruntime` (CPU, no `-gpu` suffix) + `huggingface_hub` to `app/backend/requirements.txt` (mirror in `environment.yml` if present); confirm no `ultralytics`/`onnxruntime-gpu`. | backend-engineer |
| IP-5 | tests | Author/extend tests per test-plan.md §Test Files, TDD red-first (see Test Execution Plan + TDD Execution Sequence). | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | D-1 Runtime | CPU-only `onnxruntime` declared; provider auto-select (CUDA if present else `CPUExecutionProvider`). Only `CPUExecutionProvider` declared by default. |
| design.md | D-2 Inference Failure | Fail-soft per page to `_sort_by_reading_order`; WARNING (page num + reason, no page content); never raise. |
| design.md | D-3 Module Boundary | `detect()` signature, geometric line→region containment (reuse `_is_inside` tolerance pattern), column-aware ordering, 0-based `reading_order`, region provenance in `metadata` (`layout_region`, `layout_confidence`); page array created/consumed/discarded in-module, no network/IO client imports. |
| design.md | D-4 Label Mapping | heron label → `ElementType` table; unknown → `text` (never raise). Map is a module constant = single source of truth. |
| design.md | D-5 Offline Bundle | 3-tier weight resolution: (1) `LAYOUT_DETECTOR_MODEL_PATH`, (2) local HF cache, (3) HF auto-download; first hit wins. |
| design.md | Migration/Rollback | `LAYOUT_DETECTOR_ENABLED=0` restores heuristic; IR wire-identical under both paths. |
| test-plan.md | AC→Test mapping; §Execution Ladder; §Notes | which tests cover which AC; mock at `onnxruntime.InferenceSession` boundary. |
| ci-gates.md | Required Gates table; Tier Floor Override | verification commands + `tier-floor-override` rationale. |
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-8 | acceptance targets. |
| docs/adr/0002-ir-elementtype-serialized-values.md | lowercase wire values | all `ElementType` assignments use existing lowercase values; no new enum members. |
| contracts/data/data-shape-contract.md | §Label mapping | data-shape confirmation of detector as IR producer. |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/parsers/layout_detector.py` | create | `LayoutDetector` per IP-1. Single stateless-after-init class. No `requests`/`httpx`/socket/network-client imports (privacy boundary D-3). Label-map constant per D-4. All `ElementType` via existing lowercase values (enum members confirmed present: `text/title/header/footer/table/figure/formula/list/list_item/caption/footnote/table_cell` at `translatable_document.py:18-31`). |
| `app/backend/parsers/pdf_parser.py` | modify | Inject detector in `parse()` after `_detect_and_mark_tables` (currently `pdf_parser.py:117`). Rasterise page per-page via `page.get_pixmap()`. Replace the `_sort_by_reading_order(elements)` + sequential index block (`pdf_parser.py:119-124`) on the native-PDF text-layer path with detector-driven order. Keep `_sort_by_reading_order` method (now the fail-soft fallback). Gate by `LAYOUT_DETECTOR_ENABLED`; when disabled, keep current behaviour. No-text-layer pages keep current behaviour (D-3). |
| `app/backend/config.py` | modify | Add the two reads near `PDF_PARSER_ENGINE` (`config.py:129-132`). `LAYOUT_DETECTOR_MODEL_PATH` optional (default unset/None). `LAYOUT_DETECTOR_ENABLED` default on, parsed with the existing `("1","true","yes")` truthiness idiom used elsewhere in the file. Name/default must match `contracts/env/env-contract.md` + `env.schema.json`. |
| `app/backend/requirements.txt` | modify | Add `onnxruntime` + `huggingface_hub`. No `-gpu`. No `ultralytics`. |
| `app/backend/environment.yml` | modify (if present) | Mirror the same deps; same forbidden-package rule. |
| `tests/test_layout_detector.py` | create | All unit + resilience tests from test-plan.md §Test Files. Mock at `onnxruntime.InferenceSession`. |
| `tests/test_pdf_parser.py` | modify | Add 3 integration tests + update existing reading-order assertions (test-plan.md §Test Update Contract row 1). |
| `tests/test_golden_regression.py` | modify | Add dual-run + multi-column accuracy assertions (AC-6). |
| `tests/test_env_contract.py` | modify | Add `test_layout_detector_model_path_declared` (AC-5). NOT in manifest Allowed Paths — see Known Risks; file a CER if it must be created/edited. |

## Contract Updates
Contracts are owned by contract-reviewer and already authored for this change; backend-engineer keeps code consistent with them, does not rewrite them.
- API: none (no endpoint).
- CSS/UI: none.
- Env: `contracts/env/env-contract.md` declares `LAYOUT_DETECTOR_MODEL_PATH` (optional); `contracts/env/env.schema.json` + `.env.example.template` updated. `config.py` must match the declared name/default.
- Data shape: `contracts/data/data-shape-contract.md` §Label mapping — detector is the IR producer; reuse existing `ElementType` lowercase wire values (no schema change).
- Business logic: `contracts/business/business-rules.md` — local-inference privacy boundary + fail-soft degradation rule; code must honour both.
- CI/CD: `contracts/ci/ci-gate-contract.md` — `layout-detector-dependency-gate` (forbid `ultralytics`/`onnxruntime-gpu`); `golden-sample-regression` (reading_order-only diff is not a regression).

## Test Execution Plan
Required phases: collect, targeted, changed-area; plus the full-tier-1 ladder run from test-plan.md §Execution Ladder. Generate evidence with `cdd-kit test run`; the gate validates `test-evidence.yml`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (typed regions, label map, unknown→text) | tests/test_layout_detector.py | typed boxes returned; all known labels map; unknown defaults to `text` |
| AC-2 (IR write, no parallel struct) | tests/test_layout_detector.py | `element_type` + `reading_order` set on IR; no extra fields |
| AC-3 (heuristic replaced) | tests/test_pdf_parser.py | detector order replaces y0 buckets on native path |
| AC-4 (privacy boundary) | tests/test_layout_detector.py | no network imports; page image not retained after `detect` |
| AC-5 (env var + weight resolution) | tests/test_env_contract.py | env var declared; env path wins over HF; unset falls back to HF |
| AC-6 (golden dual-run, >95% multi-col) | tests/test_golden_regression.py | dual-run regression passes; multi-column accuracy >95% |
| AC-7 (fail-soft) | tests/test_layout_detector.py | missing model / ONNX error / OOM / unrasterisable page → fallback + WARNING; parse still returns a document |
| AC-8 (no ultralytics) | tests/test_layout_detector.py | `ultralytics` not imported; dep gate clean |

(`cdd-kit test select` falls back to this table when test-plan.md has no mapping. Bare targets / pytest commands only.)

## TDD Execution Sequence (backend-engineer)
1. `cdd-kit test select p2-layout-detection --json`.
2. Write failing tests: new `tests/test_layout_detector.py`; extend `tests/test_pdf_parser.py`, `tests/test_golden_regression.py`, `tests/test_env_contract.py` per test-plan.md §Test Files. Mock at `onnxruntime.InferenceSession` (test-plan.md §Notes).
3. `cdd-kit test run p2-layout-detection --phase collect --command "pytest tests/test_layout_detector.py tests/test_pdf_parser.py tests/test_golden_regression.py tests/test_env_contract.py --collect-only"`.
4. `cdd-kit test run p2-layout-detection --phase targeted --command "pytest tests/test_layout_detector.py tests/test_env_contract.py -x"` — expect red.
5. Implement IP-1..IP-4 (source + config + deps).
6. Re-run targeted; then changed-area / full-tier-1: `cdd-kit test run p2-layout-detection --phase full-tier-1 --command "pytest tests/test_layout_detector.py tests/test_pdf_parser.py tests/test_golden_regression.py tests/test_env_contract.py"` until green.

## Constraints Checklist (non-negotiable)
- [ ] No `ultralytics` import anywhere; no `onnxruntime-gpu` in manifests.
- [ ] No network-client import in `layout_detector.py` (privacy boundary D-3); weight download is the only network touch and only via `huggingface_hub` weight resolution (D-5), never page data.
- [ ] Page pixmap array created/consumed/discarded in-module; never serialised, persisted, or sent over a socket.
- [ ] `LAYOUT_DETECTOR_ENABLED=false` skips detector → legacy heuristic; IR wire-identical under both paths.
- [ ] Inference failure logs WARNING only (page num + reason, no page content); never raises (D-2).
- [ ] All `ElementType` assignments use existing lowercase wire values (ADR 0002); no new enum members.
- [ ] GPU: only `CPUExecutionProvider` declared by default; CUDA used only if `onnxruntime-gpu` installed out-of-band and CUDA provider available (D-1).
- [ ] `_sort_by_reading_order` retained as the fail-soft fallback, not deleted.

## Gate Command
Run with the required override (trigger vocab: `LAYOUT_DETECTOR_MODEL_PATH`, "model", "weights", "offline", "download", "integration"):

```
cdd-kit gate p2-layout-detection --tier-floor-override 2 --reason "Local CPU-only offline ONNX inference; no DB migration, no auth, no cache, no external API endpoint. Per change-classification.md and ci-gates.md Tier Floor Override."
```

Required gates (ci-gates.md): contract-validate, change-gate, unit-tests, golden-sample-regression, layout-detector-dependency-gate — all green; no open AC-8 (ultralytics) violation. `layout-detector-dependency-gate` has no override path.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- design.md is authoritative for D-1..D-5; do not re-decide runtime, fallback, or weight-resolution strategy.

## Known Risks

- `tests/test_env_contract.py` is referenced by test-plan.md (AC-5) but is NOT in context-manifest.md §Allowed Paths. If it must be created/edited, file a Context Expansion Request before writing it; do not silently read/write outside the manifest.
- `app/backend/environment.yml` is listed in the manifest; confirm it exists before editing (design.md treats the mirror as optional).
- `.cdd/code-map.yml` was not consulted for this plan; affected ranges were grounded by direct reads of allowed paths (consistent with design.md Open Risks). If broad navigation is later needed, run `cdd-kit code-map` first.
- Text-line→region assignment tie-break (nearest-center vs largest-overlap) is left to implementation but MUST be deterministic for golden-sample stability (design.md Open Risks).
- CPU inference latency per page is unmeasured; not blocking, but a page-cap/batching follow-up may surface (design.md Open Risks).
- heron-101 DocLayNet mAP 78.0% — the >95% reading-order target depends on column-ordering logic, not raw mAP; AC-6 golden dual-run is the real validator.
