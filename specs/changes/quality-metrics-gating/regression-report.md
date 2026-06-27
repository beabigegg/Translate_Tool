# Regression Report — quality-metrics-gating

## Required by: change-classification.md:33

Three existing behaviors change. Each is verified below with pointer to the covering test and evidence that no regression is introduced.

---

## 1. Critique adoption: last-wins → score-gated

**Previous behavior**: The critique loop always adopted the most recent LLM revision regardless of translation quality.

**New behavior**: `_critique_gate_adopt()` (AC-7) adopts a revision only when `revised_score >= original_score`. On tie, the original is kept. Falls back to length-ratio/fluency heuristic when QE is unavailable (AC-8).

**Regression risk**: Callers that expected unconditional adoption (e.g. benchmarks, integration tests asserting revised text is always stored) could fail.

**Verification**:
- `tests/test_critique_gate.py` — adoption, rejection, exact-tie, empty-score, ImportError-fallback cases. All assert real seam `_critique_gate_adopt()` directly (not call-wiring).
- `tests/test_fewshot_glossary.py::TestCritiqueLoop::test_revised_draft_recorded_in_tmap` — bypasses QE gate via `_critique_gate_adopt` mock; confirms critique-loop recording still works regardless of gate outcome.
- Full test suite: 695 passed, 3 skipped — no regressions.
- Evidence: `test-evidence.yml` / `test-runs/` (final-status: passed, all phases).

**Status**: No regression. Tie behavior explicitly specified in BR-89.

---

## 2. Judge scoring: whole-document → per-block

**Previous behavior**: `_run_judge_loop_impl` joined all blocks into a single string and produced one whole-document score.

**New behavior**: `judge_block(src, tgt)` (AC-5) calls `evaluate(src, tgt)` per block individually. Each block receives its own score.

**Regression risk**: Code that consumed a single float from the judge loop as a document-level verdict could receive a different shape.

**Verification**:
- `tests/test_quality_judge.py` — per-block tests assert one float per (src, tgt) pair, correct arg routing, safe-degrade to 0.0 on failure.
- The return shape of `judge_block` is `float` (not `List[float]`), so call sites that consumed a single float per call are unaffected.
- Full test suite: 695 passed. No per-doc join path test failures observed.

**Status**: No regression. Per-block scoring is additive; the whole-doc consumer pattern was internal.

---

## 3. QE default: off → on

**Previous behavior**: `QE_ENABLED` defaulted to `"false"` — quality scoring, post-translate hook, and critique gate were all off by default.

**New behavior**: `QE_ENABLED` defaults to `"true"` (AC-3). On fresh deployments without the COMET library installed, the QE step fires, fails gracefully, and the critique gate falls back to the BR-90 length-ratio heuristic — pipeline always completes.

**Regression risk**: Deployments that relied on the `false` default will now attempt COMET model load on every job. If COMET is not installed, this adds one model-load attempt and a WARNING log per job before the heuristic runs. No job failure results.

**Mitigation**: BR-90 safe-degrade is unconditional — `ImportError` or any model load failure → heuristic → adopt/reject decision → pipeline completes. Operators who cannot or do not want COMET must explicitly set `QE_ENABLED=false`.

**Verification**:
- `tests/test_env_contract.py::TestQeDefault` — asserts `QE_ENABLED` is `True` after env pop (import-time default).
- `tests/test_critique_gate.py::test_qe_unavailable_falls_back_to_heuristic` — confirms ImportError path → heuristic → no exception.
- Full test suite: 695 passed. The prior `test_qe_hook_not_called_when_disabled` was updated to reflect the renamed seam.

**Approved-with-risk**: QE_ENABLED default flip uses a minor version bump in `env-contract.md` (convention for this pre-1.0 project) rather than a major bump. The contract-reviewer accepted this given BR-90 and the project's consistent versioning convention. Operators must be notified of this default change in release notes.

---

## Summary

| Behavior | Regression? | Covering test | Evidence |
|---|---|---|---|
| Critique adoption last-wins → score-gated | None | test_critique_gate.py | test-evidence.yml (all phases passed) |
| Judge whole-doc → per-block | None | test_quality_judge.py | test-evidence.yml (all phases passed) |
| QE default off → on | Operational risk only (log noise + heuristic fallback) | test_env_contract.py, test_critique_gate.py | approved-with-risk in agent-log/contract-reviewer.yml |

**Follow-up**: Release notes must call out `QE_ENABLED=true` default change so operators who do not have COMET installed know to set `QE_ENABLED=false` explicitly.
**Owner**: application-team
