# Archive — quality-metrics-gating

## Change Summary

Shipped per-segment QE scoring as the gate for the critique adoption loop, per-block judge scoring, and `translate_document()` parity with `translate_texts()`. `QE_ENABLED` was flipped to `true` by default so the critique gate and post-job rescore threshold are active out of the box. A deterministic length-ratio heuristic ensures the pipeline always completes even when COMET is absent. The `judge_layout()` MLLM seam was added to `QualityJudge` (local Gemma, in-memory PIL only per ADR 0008) as a callable method, wiring to `pdf_processor.py` deferred intentionally.

## Final Behavior

- **Critique adoption gate**: `_critique_gate_adopt(src, draft, revised)` calls COMET on both drafts; adopts revised only when `revised_score > draft_score`; tie keeps original; on QE unavailable → length-ratio heuristic; pipeline always completes
- **Per-block judge**: `judge_block(src, tgt) -> float` replaces whole-doc join; each block scored individually via `evaluate()`
- **`judge_layout()` seam**: accepts in-memory `PIL.Image`, returns int 1–5 from local Gemma; never routed to cloud; call site in `pdf_processor.py` not yet wired
- **`translate_document()` parity**: delegates per-chunk to `translate_texts()` — term substitution, critique loop, and 50-token overlap context all apply automatically
- **`QE_ENABLED` default**: `false` → `true`; deployments without COMET get heuristic fallback automatically
- **`QE_RESCORE_THRESHOLD=0.5`**: segments below threshold flagged for re-translation in post-translate hook

## Final Contracts Updated

- `contracts/env/env-contract.md` v0.11.0 — `QE_ENABLED` default true; `QE_RESCORE_THRESHOLD` row added
- `contracts/env/env.schema.json` — `QE_ENABLED` default `"true"`; `QE_RESCORE_THRESHOLD` property with pattern
- `contracts/env/.env.example.template` — `#QE_RESCORE_THRESHOLD=0.5` added
- `contracts/business/business-rules.md` v0.21.0 — BR-89..BR-95 (critique gate semantics, heuristic fallback, per-block judge, translate_document parity, judge_layout seam-only, privacy boundary)
- `contracts/data/data-shape-contract.md` v0.15.0 — §Quality-Metrics-Gating Extensions (per-segment QE list, per-block judge dict, MLLM layout score seam-only)
- `docs/adr/0008-mllm-layout-judge-local-only-image.md` — privacy decision: PIL stays in-memory, never serialised to disk or sent to cloud

## Final Tests Added / Updated

- `tests/test_critique_gate.py` (new) — adoption, rejection, tie, empty-score, ImportError-fallback, heuristic rules
- `tests/test_translate_document_parity.py` (new) — AC-9/10/11: terms kwarg wiring, critique loop invocation, overlap context threading
- `tests/test_env_contract.py::TestQeDefault` (new) — AC-3 default true; AC-4 threshold in schema/template/config
- `tests/test_quality_evaluation.py`, `tests/test_quality_judge.py` — per-segment and per-block scoring, judge_layout seam
- Updated: `test_translation_strategy.py`, `test_fewshot_glossary.py`, `test_sentence_mode_consistency.py`

## Final CI/CD Gates

| gate | tier | command |
|---|---|---|
| validate-contracts | 1 | `cdd-kit validate --contracts` |
| env-schema-sync QE_RESCORE_THRESHOLD | 1 | `grep -q "QE_RESCORE_THRESHOLD" .env.example.template && env.schema.json` |
| targeted-quality-gating | 1 | `pytest test_quality_evaluation.py test_quality_judge.py test_critique_gate.py test_translate_document_parity.py test_env_contract.py` |
| full-test-suite | 1 | `pytest tests/` |

## Production Reality Findings

- **Contract-reviewer BLOCKED on wrong path**: first pass read main repo instead of worktree; all contract changes were correct but invisible. Fixed by re-briefing with full absolute worktree path.
- **QE_ENABLED default flip**: minor version bump used per project pre-1.0 convention (policy says major); accepted because BR-90 safe-degrade guarantees no job failure even without COMET. Operators without COMET get heuristic fallback, not a crash.
- **`judge_layout` ships without a caller**: CER-003 was approved but wiring to `pdf_processor.py` was intentionally deferred as a seam-only delivery. Documented in BR-95 and data-shape-contract.md. 695 tests pass.
- **`regression-report.md` initially missing**: required by classification for three behavior changes; written before merge.

## Lessons Promoted to Standards

- **do-not-promote** (already covered): contract-reviewer wrong-path issue is the same worktree specs-location lesson promoted in `office-output-mode` close.
- **do-not-promote**: QE_ENABLED default flip minor-vs-major versioning is a one-off accepted risk, not a durable rule worth enshrining.

## Follow-up Work

- `judge_layout()` caller in `pdf_processor.py` — wiring deferred; implement in a future change when PDF layout scoring is prioritised.
- Operator release notes: `QE_ENABLED=true` is now the default; teams without COMET should add `QE_ENABLED=false` to their `.env`.

---

*This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.*
