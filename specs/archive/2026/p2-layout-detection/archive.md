# Archive: p2-layout-detection

> Cold Data Warning: This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.

## Change Summary

Added the Docling heron-101 ONNX layout detector to the native-PDF parse path. The previous `round(y0,10pt)` Y-axis bucket heuristic for reading order was replaced by ML-based region detection using IBM's RT-DETRv2 architecture (78.0% mAP on DocLayNet, Apache-2.0). A new isolated module `app/backend/parsers/layout_detector.py` performs per-page inference: it rasterizes each page, runs the ONNX model, maps heron-101 class labels to IR `ElementType` values, and writes `element_type` + `reading_order` into the existing `TranslatableElement` IR. A fail-soft contract (BR-33) ensures any per-page inference failure falls back silently to the heuristic; the privacy contract (BR-32) prohibits any network/HTTP import in the module.

## Final Behavior

- Native-PDF parse path now calls `layout_detector.detect()` per page (when `LAYOUT_DETECTOR_ENABLED=true`, default).
- Detected regions are typed (text/title/table/figure/formula/header/footer/list-item/caption/footnote) and assigned reading order column-aware.
- Global reading_order is re-sequenced (0..N-1) after all pages are processed.
- Any page whose inference fails emits a `WARNING` log and uses the round(y0,10pt) heuristic for that page only; the job continues.
- Model weights resolve via: `LAYOUT_DETECTOR_MODEL_PATH` env var → HF local cache → HF auto-download.
- CPU-only (`onnxruntime`, no `onnxruntime-gpu`) — GPU opt-in is out-of-band.

## Final Contracts Updated

| contract | version change | what changed |
|---|---|---|
| `contracts/env/env-contract.md` | 0.3.0 → 0.4.0 | `LAYOUT_DETECTOR_MODEL_PATH` (opt, default HF auto-download), `LAYOUT_DETECTOR_ENABLED` (default true) |
| `contracts/data/data-shape-contract.md` | 0.4.1 → 0.4.2 | `ElementType` completeness confirmed; `reading_order` field declared as detector output |
| `contracts/business/business-rules.md` | 0.6.0 → 0.7.0 | BR-32 (privacy: no network imports in layout_detector.py), BR-33 (fail-soft: inference failure → heuristic fallback, no crash) |
| `contracts/ci/ci-gate-contract.md` | 0.3.0 → 0.4.0 | `layout-detector-dependency-gate` rule (ultralytics + onnxruntime-gpu forbidden in base requirements) |
| `contracts/env/env.schema.json` | — | `LAYOUT_DETECTOR_MODEL_PATH`, `LAYOUT_DETECTOR_ENABLED` properties added |
| `contracts/env/.env.example.template` | — | Layout detector section added |

## Final Tests Added / Updated

| file | type | count |
|---|---|---|
| `tests/test_layout_detector.py` | unit + contract + resilience | 16 tests (new) |
| `tests/test_env_contract.py` | contract | 4 tests (new; `test_layout_detector_model_path_declared`) |
| `tests/test_pdf_parser.py` | integration | 3 tests added |
| `tests/test_golden_regression.py` | regression | 2 tests added (dual-run + multi-column accuracy) |

Test evidence: `specs/changes/p2-layout-detection/test-evidence.yml` — all 3 required phases (collect, targeted, changed-area) passed; 50 passed, 3 expected-skipped (changed-area phase).

## Final CI/CD Gates

| gate | tier | trigger | pass condition |
|---|---|---|---|
| contract-validate | 2 | PR / pre-commit | exit 0 |
| change-gate | 2 | PR / pre-commit | exit 0 |
| unit-tests | 2 | PR | 50 passed, 3 skipped |
| golden-sample-regression | 2 | PR | all pre-existing IR fields match |
| layout-detector-dependency-gate | 2 | PR | no ultralytics / onnxruntime-gpu in base requirements |
| hf-download-live | 3 (nightly) | nightly | informational only; not required at PR |

ADR written: `docs/adr/0003-layout-detector-runtime-and-failure-mode.md` (CPU-only and fail-soft decisions).

## Production Reality Findings

- **CVE-2024-43591** (onnxruntime < 1.20.0, CVSS 8.8 heap buffer overflow in ONNX parser): found by `dependency-security-reviewer`; floor bumped from `>=1.17.0` to `>=1.20.0` in `requirements.txt`. Low exploitability (no user-supplied ONNX path) but eliminated proactively. Evidence: `agent-log/backend-engineer.yml` + requirements.txt.
- **ci-gates.md column header "workflow" token**: `validate_ci_gates.py` requires the literal token `workflow` in gate table content; original column header `command` failed validation. Fixed to `command / workflow`. Evidence: qa-reviewer finding; ci-gates.md fix confirmed by gate re-run.
- No pre-existing test failures in surrounding suite (421 passed at changed-area time).

## Lessons Promoted to Standards

| lesson | target | evidence |
|---|---|---|
| `ci-gates.md` gate-table column header must include the literal token `workflow` (e.g. `command / workflow`) — `validate_ci_gates.py` rejects files missing it; do not rename the column from the template | `CLAUDE.md` Promoted Learnings (new line appended) | qa-reviewer finding; ci-gates.md line 4 fix; gate re-run confirmed |
| onnxruntime CVE floor (`>=1.20.0`) | do-not-promote — floor already machine-enforced in `requirements.txt:14`; no cross-change workflow lesson | dependency-security-reviewer finding |

## Follow-up Work

- `hf-download-live` test (`pytest tests/ -k hf_live`): currently skipped at PR; promote to required only if AC-4 coverage gaps emerge post-merge.
- 4 open medium risks from spec-architect: mAP-vs-target gap, CPU inference latency, line-region tie-break behavior, code-map index not consulted during arch review. None are blocking at current scope.
- `onnxruntime-gpu` opt-in path: intentionally out-of-band; no tracked change exists yet. Users requiring GPU inference must install `onnxruntime-gpu` out-of-band (replaces CPU variant at runtime).
