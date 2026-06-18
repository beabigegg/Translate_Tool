# Change Classification

## Change Types
- primary: `feature-add`
- secondary: `env-change`, `data-shape-change` (IR serialized values / reading_order), `dependency-add` (onnxruntime / local ONNX model)

## Risk Level
- medium

## Impact Radius
- cross-module (parsers → IR model → processor pipeline)

## Tier
- 2

## Architecture Review Required
- yes
- reason: Non-obvious design decisions — CPU-vs-GPU runtime default, inference-failure degradation strategy (fallback to `round(y0,10pt)` vs hard error), model-selection rationale — plus a new module boundary in the parse pipeline and operational trade-offs (offline bundling, license, privacy). `spec-architect` writes `design.md` before `implementation-planner` runs and resolves the two Open Questions from the change request.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | |
| proposal.md | no | |
| spec.md | no | |
| design.md | yes | Architecture Review Required; fallback/runtime/privacy decisions must be recorded before implementation |
| qa-report.md | no | |
| regression-report.md | no | |
| visual-review-report.md | no | |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: none (no new endpoint; offline inference only)
- CSS/UI: none
- Env: `contracts/env/env-contract.md` — add `LAYOUT_DETECTOR_MODEL_PATH` (optional, default = HuggingFace auto-download); update `.env.example.template` + `env.schema.json`
- Data shape: `contracts/data/data-shape-contract.md` — confirm/extend `ElementType` + `reading_order` serialized values written by the detector (consistency with ADR 0002 / `p2-ir-document-model`)
- Business logic: `contracts/business/business-rules.md` — local-inference privacy constraint + failure-degradation rule (per design decision)
- CI/CD: `contracts/ci/ci-gate-contract.md` — new onnxruntime dependency gate; offline-model-bundle verification

## Required Tests
- unit: yes — `layout_detector.py` region typing, IR write, reading-order assembly (model inference mocked)
- contract: yes — env var presence/validation; IR serialized-value (`ElementType`/`reading_order`) shape
- integration: yes — `pdf_parser.py` → `layout_detector.py` → IR pipeline end-to-end on native PDF
- E2E: no
- visual: no
- data-boundary: yes — multi-column / rotated / malformed-region inputs; detector-failure degradation path
- resilience: yes (lightweight) — heron inference failure handling (fallback or controlled error per design decision)
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
(commission order)
1. `spec-architect` — design.md: model/runtime/fallback decisions, IR write contract, privacy/offline boundary
2. `contract-reviewer` — env + data-shape + business-rules + CI/CD contracts
3. `test-strategist` — unit + data-boundary + resilience + golden dual-run regression mapping
4. `ci-cd-gatekeeper` — ci-gates.md: new dependency gate, offline-bundle verification
5. `implementation-planner` — turn design + contracts + tests into execution packet
6. `backend-engineer` — layout_detector.py + pdf_parser.py integration, TDD
7. `dependency-security-reviewer` — onnxruntime license + CVE, requirements.txt change
8. `qa-reviewer` — release readiness, golden-sample regression verification

## Inferred Acceptance Criteria
- AC-1: `app/backend/parsers/layout_detector.py` exists and detects typed regions (text/title/table/figure/formula/header/footer/list) per native-PDF page via the local Docling heron-101 ONNX model.
- AC-2: Detection results are written into the existing IR (`ElementType` + `reading_order` on `translatable_document.py`) with no parallel/duplicate data structure.
- AC-3: The `round(y0,10pt)` bucket heuristic in `pdf_parser.py` is replaced by layout-detector-driven reading order on the native-PDF path.
- AC-4: Inference is fully local — no page image leaves the machine; model weights load from a local/offline path or HuggingFace auto-download (no required cloud call).
- AC-5: New optional env var `LAYOUT_DETECTOR_MODEL_PATH` is declared in the env contract, `.env.example.template`, and `env.schema.json`, and falls back to HuggingFace auto-download when unset.
- AC-6: Golden-sample old-vs-new reading-order dual-run regression passes; multi-column academic-PDF reading-order correctness > 95%.
- AC-7: Detector inference failure is handled by an explicit, design-decided strategy (fallback to heuristic or controlled error) — no unhandled crash on the parse path.
- AC-8: Only Apache-2.0-licensed dependencies are added (`onnxruntime`, no `ultralytics`); offline Docker bundling of model weights is documented/supported.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 3.5, 4.2, 5.1, 5.2

## Tier Floor Override
Gate tier-floor will likely trip on env/config vocabulary (`LAYOUT_DETECTOR_MODEL_PATH`, "model", "weights", "offline", "download"). No DB migration, no auth, no cache, no external API endpoint — inference is local and offline-only. Apply `tier-floor-override` to **Tier 2** with this rationale.

## Clarifications or Assumptions
- The two Open Questions from the change request (onnxruntime-gpu vs CPU-only; inference-failure fallback vs hard-error) are resolved by `spec-architect` in `design.md`.
- No new public API endpoint; if a health endpoint for model availability is later requested, that is a separate change requiring api-contract update.

## Context Manifest Draft
See `specs/changes/p2-layout-detection/context-manifest.md` (updated from this classification output).
