# Archive: batch-critique-qe-scoring

## Change Summary
The critique loop scored one segment's `(draft, revised)` pair per `score_blocks()`
call, instantiating a Lightning Trainer O(segments × iterations) times. This change
inverts the loop to round-based: each of `CRITIQUE_MAX_ITERATIONS` rounds revises all
pending segments, issues ONE batched `score_blocks()` across every segment's
draft/revised pairs, then applies per-segment adoption — dropping Trainer
instantiations to O(iterations). Behavior-preserving: identical per-segment adopted
output. Independent of #1-#4; must land before #7 (which shares the critique loop).
Tier 2, feature lane. Implemented by a backend-engineer agent, main-Claude verified.

## Final Behavior
No functional change to translations. QE (COMET) scoring in the critique loop is
issued once per iteration round (batched) instead of once per (segment, iteration).
Every segment's draft-vs-revised adoption is identical to before (strict-greater,
tie keeps draft — BR-89). Trainer/model instantiations drop from O(segments×iterations)
to O(iterations).

## Final Contracts Updated
- `contracts/data/data-shape-contract.md` — "Critique gate usage" row rewritten from
  the two-element per-segment call to the batched flat-list call shape (`[seg0_draft,
  seg0_revised, seg1_draft, …]`, scores read back at `2*i`/`2*i+1`). schema-version
  0.16.0 → 0.17.0 + `contracts/CHANGELOG.md` entry.
- Business rules unchanged (BR-89/BR-90 adoption outcome + BR-46 metrics parity preserved).

## Final Source Changed
- `app/backend/services/translation_service.py` — round-based critique loop + new
  `_batched_critique_adopt` (interleaved blocks, index-mapped read-back, `>= len`
  full-count-or-keep-draft degradation, QE-unavailable heuristic fallback).
  `_critique_gate_adopt` and `quality_evaluator.score_blocks()` unchanged.

## Final Tests / Verification
- NEW `tests/test_critique_loop_batching.py` (8): AC-1 parity vs a hand-scripted
  baseline (not a diff against the new code), call-count ≤ iterations, cache-skip,
  per-segment exception + timeout isolation, batched-`[]` keep-draft, metrics parity.
- `tests/test_critique_gate.py` (+4, incl. exact index-mapping guard) and
  `tests/test_quality_evaluation.py` (+2, OOM ladder on 2N list, batch_size invariance).
- **Existing critique/QE tests pass UNCHANGED** — the primary behavior-preservation guard.
- Full suite 1164 passed, 0 failed. `cdd-kit validate --contracts`/`--versions` green.
  4 evidence phases green.

## Production Reality Findings
- **Orphaned mock after refactor (CER-002):** `tests/test_fewshot_glossary.py::
  test_revised_draft_recorded_in_tmap` patched `_critique_gate_adopt` directly; the
  round loop now routes adoption through `_batched_critique_adopt`, so the mock became
  a no-op and the real COMET path ran, flipping the assertion. Fixed with a one-line
  mechanical mock retarget (no production-behavior change). The file was outside the
  original manifest Allowed Paths → CER-002 approved (in-scope-by-necessity).
- Index-mapping (the highest-risk detail) verified correct by main Claude: `blocks`
  interleaves `(src,draft)/(src,revised)` per segment; `scores[2*i]`/`[2*i+1]` read-back;
  guarded by the scripted-baseline parity test + exact-`blocks`-arg assertions.

## Lessons Promoted to Standards
None promoted to CLAUDE.md. The orphaned-mock-after-refactor gotcha is an instance of
the existing `mock.patch` / tautological-tests learnings (a mock targeting a now-bypassed
symbol silently runs the real path); the batched call-shape lives in
`data-shape-contract.md` v0.17.0; adoption/metrics semantics are unchanged
(BR-89/BR-90/BR-46). No new durable cross-change rule warranted.

## Follow-up Work
`translation-progress-detail-ui` (#7) shares the critique loop and will wire its
observational progress hooks against this final round-based shape.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
