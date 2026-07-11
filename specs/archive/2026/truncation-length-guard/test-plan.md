---
change-id: truncation-length-guard
schema-version: 0.1.0
last-changed: 2026-07-11
risk: high
tier: 1
---

# Test Plan: truncation-length-guard

## Fixtures
All fixtures are built in-test (Python literals / small builder helpers already
present in `tests/test_docx_nested_tables.py` and `tests/test_table_context_translation.py`).
No `docs/TEST_DOC/` files are used or added.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit (pure model) | tests/test_length_guard.py::test_flags_recorded_bug_ratio | 0 |
| AC-1 | integration (cell seam, both wire formats) | tests/test_docx_nested_tables.py::test_layout_cell_truncated_reply_flagged_and_recovered | 1 |
| AC-2 | integration (recovery) | tests/test_length_guard.py::test_cell_seam_flags_and_recovers_truncated_reply | 1 |
| AC-3 | data-boundary | tests/test_length_guard.py::test_zero_false_positives_calibration_fixtures | 0 |
| AC-4 | data-boundary (fail-safe) | tests/test_length_guard.py::test_failsafe_unknown_target | 0 |
| AC-4 | data-boundary (fail-safe) | tests/test_length_guard.py::test_failsafe_short_source_below_min_chars | 0 |
| AC-4 | data-boundary (fail-safe) | tests/test_length_guard.py::test_failsafe_zero_expected_length_numeric_source | 0 |
| AC-5 | unit/integration (BR-68 exempt) | tests/test_length_guard.py::test_numeric_cell_never_reaches_guard | 0 |
| AC-6 | resilience (bounded recovery) | tests/test_length_guard.py::test_recovery_bounded_single_attempt_no_reentry | 1 |
| AC-6 | resilience (keep-longest/never-source) | tests/test_length_guard.py::test_recovery_keeps_longest_on_exhaustion_never_source | 1 |
| AC-7 | integration regression | tests/test_length_guard.py::test_normal_length_reply_unaffected_no_recovery_no_warning | 1 |
| AC-7 | regression (out-of-scope confirmation) | tests/test_json_translation_body.py::test_body_path_unaffected_by_length_guard | 1 |
| AC-8 | unit (composition model) | tests/test_length_guard.py::test_mixed_composition_excludes_numeric | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Pure `is_suspiciously_short()` / composition model — no I/O, no LLM, <30s. |
| data-boundary | 0 | THE load-bearing family (AC-3/AC-4): a FP re-translates a correct output, worse than the bug. Table of calibration-derived legitimate-short (src, tgt) pairs across CJK-heavy AND latin-heavy sources at k=0.3, asserted directly on the guard's boolean return. Each of the 3 fail-safe clauses (unknown target, source<15, E==0) asserted independently. |
| integration | 1 | Cell-seam wiring in `docx_processor.py`: a mocked `client.translate_json`/`translate_once` returning a short reply must route through the guard into BR-82 recovery; assert the WRITTEN `final_tmap` cell value (selection/assignment-delivery, not call-wiring). |
| resilience | 1 | Bounded-retry / never-loop / keep-longest / never-source invariants (ADR-0020 reversal-guarded). Assert exact `translate_texts` call count (no re-entry) and the terminal written value. |
| monkey | 3 (nightly) | Owned by monkey-test-engineer (monkey-test-report.md): adversarial short-translation fuzz (empty, whitespace, single-token, mixed-script, degenerate) probing the FP boundary. Not authored in this plan; referenced only. |

## Falsifiability (per family — the line whose reversal turns the test RED)
- **unit/data-boundary**: hardcoding `is_suspiciously_short()` to always return `False` turns `test_flags_recorded_bug_ratio` RED; the `translated_len < k * E` comparison is the load-bearing line. Removing any ONE of the three fail-safe early-returns (target-not-in-coefficient-table, `normalized_source_len < MIN_SOURCE_CHARS`, `E == 0`) turns the corresponding `test_failsafe_*` case RED (it would now flag instead of pass-through).
- **AC-5**: removing the BR-68 pre-guard numeric exclusion, or the `E == 0` backstop, turns `test_numeric_cell_never_reaches_guard` RED.
- **integration/resilience (recovery)**: replacing the keep-longest comparison at the exhaustion branch with "always keep source" or "always keep original short reply" turns `test_recovery_keeps_longest_on_exhaustion_never_source` RED (must never equal source, must equal the longer of the two attempts). Removing the `MAX_RECOVERY_ATTEMPTS = 1` bound, or letting recovery re-enter the guard seam, turns `test_recovery_bounded_single_attempt_no_reentry` RED (a second `translate_texts` call or an unbounded loop is observed).
- **AC-7**: any change that fires recovery or the WARNING log for a plausible-length reply turns `test_normal_length_reply_unaffected_no_recovery_no_warning` RED.

## Existing-fake sweep
Grepped `tests/` for `translate_json`/`parse_json`/`translate_texts` fakes reaching
the DOCX cell-acceptance seam: `test_table_context_translation.py` and
`test_docx_nested_tables.py` mock `client.translate_json` with short fixed cells
(e.g. `"Apple" → "苹果"`), all with source text under `MIN_SOURCE_CHARS = 15` —
green by construction under the AC-4 fail-safe, no change needed. `translate_texts`
fakes elsewhere (`test_fewshot_glossary.py`, `test_critique_loop_batching.py`,
`test_translation_strategy.py`, `test_glossary_enforcement.py`, `test_doc_chunker.py`,
`test_translation_service*.py`, `test_translate_document_parity.py`) are body-path
doubles, out of this change's DOCX-cell-only scope (D1). No fake needs modification.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

Conda-scoped commands (mirrors project convention, `translate-tool` env):
```
conda run -n translate-tool pytest tests/test_length_guard.py -q
conda run -n translate-tool pytest tests/test_docx_nested_tables.py -k truncat -q
conda run -n translate-tool pytest tests/test_json_translation_body.py -k length_guard -q
conda run -n translate-tool pytest tests/ -q   # full-suite regression, AC-7 evidence
```

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | Additive-only change (new pure module + one call site); no existing test's expected behavior changes. |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- Body/segment path guard adoption (D1) — helper is target-agnostic, deferred to evidence.
- PPTX/XLSX table cells sharing `parse_json` — no reusable BR-82 recovery block there yet.
- `tests/metrics/truncation_rate.py` — counts `render_truncated` (a RENDER-time bbox concept, ADR-0004/BR-38); it is NOT this change's regression metric and is not used for AC-7.
- Any new IR/data-shape field — D5 rejected this; the WARNING log is the only mark, observability-only, no consumer test needed.

## Notes

Recovery/guard is a pure-function-plus-single-call-site design; most assertions
belong at unit tier. Integration tests assert the WRITTEN cell value at the
`final_tmap` boundary, never mock-call-wiring alone (CLAUDE.md tautological-test
lesson, forms 1/3). monkey-test-engineer owns adversarial fuzz separately.
