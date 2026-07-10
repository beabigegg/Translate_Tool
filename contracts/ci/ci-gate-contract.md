---
contract: ci
summary: CI gate inventory, artifact retention, and rollback requirements.
owner: platform-team
surface: delivery-pipeline
schema-version: 0.7.0
last-changed: 2026-07-06
breaking-change-policy: deprecate-2-minors
---

# CI/CD Gate Contract

## Gate Inventory
| gate | tier | trigger | required | command/workflow | owner | artifact |
|---|---:|---|---:|---|---|---|
| contract-validate | 2+ | pre-commit / PR | yes | cdd-kit validate --contracts | platform-team | exit code 0 |
| change-gate | 2+ | pre-commit / PR | yes | cdd-kit gate <change-id> | platform-team | exit code 0 |
| unit-tests | 2+ | PR | yes | pytest tests/ | application-team | junit XML |
| golden-sample-regression | 2+ | PR | yes | pytest tests/test_golden_regression.py --tb=short -q | application-team | per-sample pass/fail diff (step log) |
| layout-detector-dependency-gate | 2+ | PR | yes | `! grep -E "(ultralytics|onnxruntime-gpu)" app/backend/requirements.txt app/backend/environment.yml` | platform-team | exit code 0 (no forbidden packages) |
| renderer-equivalence | 2+ | PR | yes | pytest tests/test_ir_pipeline_decoupling.py tests/test_golden_regression.py -k "equivalence" --tb=short -q | application-team | per-element pass/fail diff (step log) |
| text-expansion-benchmark | 2+ | PR | yes | pytest tests/test_text_expansion_benchmark.py --tb=short -q | application-team | zero-overflow + zero-tofu assertion log; covers AC-1 AC-2 AC-3 |
| residual-text | 2+ | PR | yes | pytest tests/test_pdf_layout_refactor.py -k "residual_text" --tb=short -q | application-team | residual source-text count = 0 across all rendered PDF fixture pages |
| biou-layout-fidelity | 2+ | PR | no | pytest tests/test_layout_metrics.py -k "biou" --tb=short -q | application-team | BIoU ≥ PR#3 metrics baseline (informational) |
| truncation-rate | 2+ | PR | no | pytest tests/test_layout_metrics.py -k "truncation_rate" --tb=short -q | application-team | `render_truncated=True` element count = 0 across benchmark fixture set (informational) |
| reading-order-edit-distance | 2+ | PR | no | pytest tests/test_layout_metrics.py -k "reading_order" --tb=short -q | application-team | normalized edit distance on multi-column fixture ≤ PR#3 baseline (informational) |
| ocr-absent-gate | 2+ | PR | yes | pytest tests/test_pdf_layout_refactor.py -k "ocr_absent" --tb=short -q | application-team | all PDF gates pass or skip gracefully when `OCR_ENABLED=False` and OCR library absent |
| libreoffice-conversion-gate | 2+ | PR | yes | pytest tests/test_libreoffice_helpers.py --tb=short -q | application-team | pass, or skip-with-marker when LibreOffice absent from runner (see policy below); mocked degrade-path sub-test always runs |

## Required Check Policy

All gates in the Gate Inventory marked `required: yes` must pass before a PR is eligible to merge.

### golden-sample-regression gate

- **Scope**: runs the dual-run comparison framework over all samples in `tests/fixtures/golden/`. The framework parses each sample file with both old-format (pre-change) and new-format (post-change) code paths, serializes each resulting IR, and diffs the field-by-field output.
- **Offline constraint**: the gate must run with no network access and no GPU. All sample files are pre-committed fixtures; no external downloads occur at gate time.
- **Pass condition**: all samples produce field-by-field equivalent IR on both code paths for every field listed in the Round-trip guarantee in `contracts/data/data-shape-contract.md` (bbox coordinates, font metadata, element_type, reading_order, element_id, content, page_num, should_translate, translated_content, metadata).
- **Fail condition**: any sample where the new-format IR differs from the old-format IR on a pre-existing field (i.e., a field that existed before p2-ir-document-model) causes the gate to fail and blocks merge. Differences limited to the new `reading_order` field alone are not a regression.
- **Report artifact**: the gate emits a per-sample pass/fail diff to stdout (captured by CI as a step log). No external artifact store is required at Tier 2.
- **Sample set**: `tests/fixtures/golden/` must contain 3–5 representative files covering at minimum one PDF, one DOCX, and one PPTX. Files must be committed as binary fixtures; they must not be generated at CI time. Note: DOCX and PPTX binary fixtures are deferred pending sourcing of license-clean representative files; the gate skips DOCX/PPTX samples gracefully until they are committed.
- **Snapshot initialization**: `_load_or_create_snapshot()` MUST NOT auto-write and auto-pass when a snapshot JSON is absent. CI must fail (not silently create) when a fixture file exists in `tests/fixtures/golden/` without a corresponding committed `.ir.json` snapshot. Any new fixture file committed to the golden directories MUST be accompanied by a committed snapshot in the same PR.

## Text Expansion Benchmark Gate

**Gate name**: `text-expansion-benchmark`

**Added in p2-text-expansion.**

**Scope**: Runs `tests/test_text_expansion_benchmark.py` against pre-committed en→de and en→es expansion fixtures in `tests/fixtures/golden/expansion/`. Asserts (1) zero bbox overflow across all rendered benchmark elements; (2) zero tofu boxes in the rendered PDF output (all glyphs resolve to a registered font face).

**Pass condition**: No element in the benchmark set overflows its bbox region; no glyph in the rendered output resolves to a missing-glyph placeholder. Both sub-checks must pass.

**Fail condition**: Any overflow or any tofu box blocks merge.

**Offline constraint**: runs with no network access, no GPU; uses pre-committed benchmark fixture PDFs and their `.ir.json` snapshots. Fixtures must follow the same snapshot-initialization rule as `golden-sample-regression` — CI must fail (not silently create) when a fixture file exists without a committed snapshot.

**Fixture requirement**: at least two en→de and two en→es pre-rendered benchmark PDFs plus their `.ir.json` snapshots must be committed before this gate can pass. The backend-engineer is responsible for committing these fixtures in the same PR as the implementation.

**Non-determinism quarantine**: if glyph resolution varies across runner images due to font-rendering non-determinism, the affected sub-check must be quarantined per the Informational Gate Promotion Policy; the overflow sub-check remains required.

## Layout Detector Dependency Gate

**Gate name**: `layout-detector-dependency-gate`

**Pass condition**: Neither `ultralytics` nor `onnxruntime-gpu` appears in `app/backend/requirements.txt` or `app/backend/environment.yml`. `onnxruntime` (CPU variant, no suffix) is the only permitted ONNX runtime entry. `huggingface_hub` is also permitted.

**Fail condition**: Any line matching `ultralytics` or `onnxruntime-gpu` in either requirements file blocks merge.

**GPU opt-in**: `onnxruntime-gpu` may be installed out-of-band by operators for GPU acceleration. The detector auto-selects CUDA execution provider when available and silently falls back to `CPUExecutionProvider`. This requires no code change and is not tracked in base requirements.

**Model weight bundling note**: Weights are NOT bundled in the repository. Offline bundling is achieved via Docker image preload + `LAYOUT_DETECTOR_MODEL_PATH`. The gate does not verify Docker weight bundling; that is an operational concern.

## Renderer Equivalence Gate

**Gate name**: `renderer-equivalence`

**Added in p2-renderer-convergence.**

**Scope**: For each fixture in `tests/fixtures/golden/pdf/`, run the same `TranslatableDocument` IR through both the fitz primary renderer and the ReportLab fallback renderer. Compare element-level decisions (inclusion, reading-order bucket assignment, text-source selection) on both paths.

**Pass condition**: For every element in the IR, both render paths make identical element-level decisions as defined in `contracts/data/data-shape-contract.md § Renderer IR-consumption contract` and BR-35. Layout pixel-position differences and font rendering differences within the documented numeric tolerance do not fail this gate.

**Fail condition**: Any element where the two paths disagree on inclusion/exclusion, reading-order bucket (null vs. non-null bucket assignment), or text-source selection (translated_content vs. content) fails the gate and blocks merge.

**Offline constraint**: runs with no network access, no GPU; uses pre-committed IR fixtures.

**Report artifact**: per-element pass/fail diff to stdout (captured as step log). No external artifact store required at Tier 2.

## LibreOffice Conversion Gate

**Gate name**: `libreoffice-conversion-gate`

**Added in support-legacy-office-formats.**

**Scope**: Runs `tests/test_libreoffice_helpers.py` (unit coverage for `doc_to_docx`, `xls_to_xlsx`, `ppt_to_pptx`, `is_libreoffice_available()`). The `.doc`/`.xls`/`.ppt` branches in `tests/test_orchestrator_phase0.py` are exercised by the main `pytest tests/ -x -q` job and are subject to the same skip-vs-required split defined below — they are not a separate gate.

- The CI runner SHOULD install `libreoffice-core` in a setup step (e.g. `apt-get install -y libreoffice-core`) so the real conversion path is exercised on every PR, rather than perpetually skipped. This install step MUST NOT be allowed to fail the gate (see Workflow Changes in the per-change `ci-gates.md`) — if the install step itself fails or is unavailable, the suite must still pass via graceful skip, never via a red gate caused by infra.
- Tests requiring the real binary MUST be marked `@pytest.mark.skipif(not is_libreoffice_available(), reason="LibreOffice not installed on this runner")` so the suite degrades gracefully (skip, not fail) on any runner where the install step is unavailable or fails.
- The graceful-degradation path itself (LibreOffice absent → file skipped, warning logged, job not failed) MUST be tested with a mocked/forced-`False` `is_libreoffice_available()` — this sub-test does NOT require the real binary and MUST run unconditionally (never skipped) on every runner.

**Pass condition**: all `.doc`/`.xls`/`.ppt` conversion unit tests pass when LibreOffice is present; all such tests skip cleanly (no CI failure) when LibreOffice is absent; the mocked graceful-degradation test always runs and always passes.

**Fail condition**: any test failure (as opposed to skip) when LibreOffice is absent; the mocked degrade-path test failing or being skipped under any condition.

**Offline constraint**: no network access required at test-run time; if installed, LibreOffice is installed from the OS package cache/mirror in a separate CI setup step, not fetched at test-run time.

**Cross-reference**: LibreOffice is a documented OPTIONAL external binary dependency — see `contracts/env/env-contract.md` § External Binary Dependencies.

## Informational Gate Promotion Policy

When a required gate produces results that vary across runner versions due to third-party library non-determinism (e.g. PyMuPDF table-detection variance), the affected field or sub-check MUST be quarantined to an informational sub-job rather than disabling or deleting the gate. The informational sub-job must record: the affected gate name, the non-deterministic field, the library and version range exhibiting the behavior, an assigned owner, and an exit date. The parent gate remains required and continues to block on all deterministic fields.

## Validator Dependencies

The `cdd-kit validate --contracts` gate requires Python packages beyond the application runtime. These must be present in `app/backend/requirements.txt` (not installed ad-hoc) so that a clean CI environment can run the gate:

| validator | required package | gate step |
|---|---|---|
| response-shape | `jsonschema>=4.0.0` | Validate contracts |

**Invariant**: `jsonschema>=4.0.0` must remain in `app/backend/requirements.txt` as long as `tests/contract/response-samples.json` exists. If `response-samples.json` is removed, the package may be dropped if no other consumer requires it.

## Artifact Retention Policy

## Known Validator Gaps

These are gaps in `cdd-kit`'s own validators, not in this project's gates. Until
each is closed in the tool, the named reviewer MUST check it by hand, and a
finding here is gate-blocking regardless of the tool's exit code.

| gap | consequence | who checks |
|---|---|---|
| `cdd-kit validate --contracts` does not verify that a contract's `schema-version` bump is paired with a matching `contracts/CHANGELOG.md` entry. Confirmed by deleting an entry: exit 0, "All validations passed", no mention of the changelog. | A version bump can ship with no changelog record of what changed. | contract-reviewer, before approving any bump |
| The gate validates `test-evidence.yml`'s phases and waivers but never compares its recorded timestamp against the mtimes of the source and test files it claims to cover. Stale evidence — recorded before a later test or production-file edit — passes. | A green evidence bundle can describe bytes that are not the bytes being merged. | qa-reviewer, before approving any change |

Both gaps were found by execution, not by reading: the first while writing three
CHANGELOG entries by hand for `json-structured-translation-io`, the second when
`qa-reviewer` blocked that change because its recorded `full` junit contained zero
of the 24 resilience tests that had landed 13 minutes after the run.

## Rollback Policy
