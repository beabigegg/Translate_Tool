---
change-id: truncation-length-guard
schema-version: 0.1.0
last-changed: 2026-07-11
---

# Implementation Plan: truncation-length-guard

## Objective
Add a pure, composition-aware length guard that flags a DOCX table cell whose
accepted translation is suspiciously short (`translated_len < k·E`,
`E = a·cjk + b·latin_alpha` from a per-target coefficient table), and on a flag
recovers the cell via a bounded, non-re-entrant split-and-retranslate that keeps
the longest attempt and NEVER substitutes source / NEVER applies the BR-25
placeholder. Fail-safe (no flag) on any uncalibrated target, short source, or
`E == 0`. See design.md D1–D6, ADR-0020, BR-117.

## Seam verification result (my first duty — read before implementing)
I verified every seam against LIVE source. One correction to design/BR-117 wording,
NOT a blocker:

- **Guard call site is `docx_processor.py:1054-1058`, not `~L1088-1132`.** BR-117
  and design.md D1 cite the acceptance seam as "the BR-82 fallback/reassembly site
  ~L1088-1132". LIVE source shows the recorded 4827→370 bug flows through the
  whole-table JSON **happy path**: `client.translate_json` (L998) succeeds →
  `table_serializer.parse_json` accepts the schema-valid reply (L1000) →
  `translated_by_pos` is populated (NOT None) → the accepted cell is written at
  the loop `for s in t_segs:` **L1054-1058**. It NEVER reaches the BR-82 else-branch
  (L1059-1132), which runs only when `translated_by_pos is None`. So:
  - The **guard call site** is L1054-1058 — where each accepted cell has BOTH its
    source (`s.text`) and translation (`translated_by_pos[(r, c)]`) co-located.
    Source+translation ARE co-located → no design gap → NOT blocked.
  - L1054-1058 also carries the **legacy pipe-grid path** (JSON flag OFF,
    `translated_by_pos` built from `grid` at L1049-1052), so a single wiring site
    satisfies AC-1's "both the JSON-envelope path AND the legacy pipe-grid path."
  - The block at **L1088-1132 is the recovery machinery** the guard routes INTO
    (its split-on-`"\n"` / `translate_texts` / reassemble pattern), reached in
    normal flow only via the `else` (shape-mismatch) branch — NOT the truncation
    acceptance point.
- **BR-82 block IS reusable non-re-entrantly.** Its per-cell logic (L1101-1119) can
  be replicated for a single flagged cell in a new helper that never calls the
  guard → NOT blocked. See IP-4.
- **Guard home = NEW `app/backend/utils/length_guard.py`.** Grep confirms no
  `is_suspiciously_short` / `count_composition` / composition counter exists
  anywhere in `app/backend`. `translation_verification.py` is about failed-
  translation detection and imports from `translation_service` (LLM-coupled); the
  guard is pure (no I/O), so a small new module is cleaner. `length_guard.py` and
  `tests/test_length_guard.py` are already in Allowed Paths.
- **Composition helper = REUSE `text_utils`.** `has_cjk` (text_utils.py:50-52) uses
  the per-char predicate `"一" <= ch <= "鿿"`; `normalize_text`
  (text_utils.py:46-47) already lowercases + collapses whitespace. No composition
  counter exists → add ONE small `count_composition()` in text_utils.py reusing the
  SAME CJK predicate (do not duplicate the range).
- **config constants location = beside `MAX_GROUP_NESTING_DEPTH` (config.py:139)**,
  which mirrors `MAX_TABLE_NESTING_DEPTH` (config.py:134) with the "Hardcoded
  constant, NOT an env var" comment — the exact pattern the classification requires.

## Execution Scope

### In Scope
- New pure module `app/backend/utils/length_guard.py` (`is_suspiciously_short`).
- New `count_composition()` in `app/backend/utils/text_utils.py`.
- Four `config.py` constants (k, coefficient table, min-source-chars, max-recovery).
- Guard + recovery wiring at `docx_processor.py:1054-1058` (happy-path acceptance,
  covering the whole-table JSON path and the legacy pipe-grid path).
- New recovery helper `_recover_truncated_cell()` in `docx_processor.py`.
- Tests per test-plan.md AC→test mapping.

### Out of Scope
- Body/segment path guard adoption (D1) — helper is target-agnostic; deferred.
- PPTX/XLSX table cells sharing `parse_json` — no reusable recovery block there.
- The BR-82 `else`-branch (L1059-1132) itself — DO NOT refactor it; its output is
  already the bounded recovery result. Guarding-and-recovering it would re-enter
  (D3 forbids). Leave byte-for-byte for AC-7.
- Any IR / data-shape field (D5) — WARNING log is the only mark, observability-only.
- `render_truncated` reuse, `tests/metrics/truncation_rate.py` (unrelated, D5).
- Any env var, `.env`, migration, API/CSS/CI change.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config.py | Add 4 hardcoded constants beside L139 (k, coefficient table, min-source-chars, max-recovery); NOT env vars | backend-engineer |
| IP-2 | text_utils.py | Add `count_composition(text) -> (cjk, latin_alpha)` reusing has_cjk's CJK predicate; digits/punct/whitespace excluded (BR-68) | backend-engineer |
| IP-3 | length_guard.py (new) | Pure `is_suspiciously_short(source, translation, target) -> bool` with the 3 fail-safe early returns | backend-engineer |
| IP-4 | docx_processor.py | New `_recover_truncated_cell()` helper (split/translate_texts/reassemble for ONE cell, non-re-entrant) | backend-engineer |
| IP-5 | docx_processor.py:1054-1058 | Wire guard into the accepted-cell loop; flag→recover→keep-longest→write; one WARNING per flagged cell | backend-engineer |
| IP-6 | tests | Author `test_length_guard.py`; add cell-seam cases to `test_docx_nested_tables.py`; body-path no-op case in `test_json_translation_body.py` | backend-engineer |
| IP-7 | tests (adversarial) | FP-boundary short-translation fuzz; monkey-test-report.md | monkey-test-engineer |
| IP-8 | regression | regression-report.md (non-truncated unchanged; legit-short not flagged) | qa-reviewer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | D1–D6, "Migration/Rollback", "Open Risks" | placement, model, recovery, fail-safe, IR-no-op |
| docs/adr/0020-truncation-length-guard.md | Decision 1–5, reversal-guarded invariants 1–2 | load-bearing constraints (fail-safe, never-source, never-loop) |
| contracts/business/business-rules.md | BR-117 (guard+recovery), BR-68 (numeric passthrough), BR-82 (split-retranslate), BR-25 (failure placeholder — must NOT be applied), BR-109 (TranslateTool logger delivery) | behavior contract |
| change-classification.md | AC-1..AC-8, Tier 1, Required Contracts (env=none) | acceptance + tier-floor override note |
| test-plan.md | AC→test mapping, Falsifiability, Test Execution Ladder, Existing-fake sweep | tests + phases |
| ci-gates.md | Required Gates table, Local Pre-PR sequence | verification commands |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/config.py | edit (~after L139) | `TRUNCATION_GUARD_K = 0.3`; `TRUNCATION_GUARD_COEFFICIENTS = {"vietnamese": (3.51, 0.75)}`  # normalized target -> (a_cjk, b_latin); `TRUNCATION_GUARD_MIN_SOURCE_CHARS = 15`; `TRUNCATION_GUARD_MAX_RECOVERY_ATTEMPTS = 1`. Add the "Hardcoded constant, NOT an env var (mirrors MAX_TABLE_NESTING_DEPTH; truncation-length-guard, BR-117)" comment. These ARE the BR-117 `k` / `MIN_SOURCE_CHARS` / `MAX_RECOVERY_ATTEMPTS` symbols (prefixed for config namespace hygiene); tests import these exact names. |
| app/backend/utils/text_utils.py | edit (add fn near has_cjk, ~L52) | `count_composition(text) -> tuple[int,int]`: iterate chars, `"一" <= ch <= "鿿"` → cjk; elif `ch.isalpha()` → latin_alpha; digits/punct/whitespace ignored. REUSE the has_cjk predicate; do not re-declare a new CJK range constant. |
| app/backend/utils/length_guard.py | create | Imports `config`, `normalize_text`, `count_composition`. See IP-3 body below. |
| app/backend/processors/docx_processor.py | edit (add module-level helper + new import) | `_recover_truncated_cell(...)` — see IP-4. Import `is_suspiciously_short` from `app.backend.utils.length_guard` (new import beside L27/L30). |
| app/backend/processors/docx_processor.py:1054-1058 | edit | Replace the accepted-cell write loop with guard+recover+keep-longest — see IP-5. |
| tests/test_length_guard.py | create | All rows in test-plan.md AC→test mapping keyed to this file. |
| tests/test_docx_nested_tables.py | edit | Add `test_layout_cell_truncated_reply_flagged_and_recovered` (AC-1 integration, both wire formats). |
| tests/test_json_translation_body.py | edit | Add `test_body_path_unaffected_by_length_guard` (AC-7 out-of-scope confirmation). |

## Implementation details (verified against live source)

### IP-3 — `length_guard.is_suspiciously_short(source, translation, target) -> bool`
Pure function, no I/O. Order of fail-safe early returns (each is a Falsifiability
anchor per test-plan.md — removing any one turns the matching `test_failsafe_*`
RED):
1. `key = (target or "").strip().lower()`; if `key not in config.TRUNCATION_GUARD_COEFFICIENTS`: return `False`  (fail-safe 1 — uncalibrated target).
2. `norm = normalize_text(source)`; if `len(norm) < config.TRUNCATION_GUARD_MIN_SOURCE_CHARS`: return `False`  (fail-safe 2 — short source).
3. `cjk, latin = count_composition(norm)`; `a, b = config.TRUNCATION_GUARD_COEFFICIENTS[key]`; `E = a*cjk + b*latin`; if `E == 0`: return `False`  (fail-safe 3 — no CJK/latin, e.g. numeric; BR-68 backstop).
4. return `len(translation or "") < config.TRUNCATION_GUARD_K * E`  (the load-bearing comparison).

**Target normalization / fail-safe for unlisted targets:** the coefficient table is
keyed by `target.strip().lower()`. Any target string whose normalized form is not a
table key fails safe (no flag). NOTE FOR backend-engineer: seed the table key to
match the ACTUAL `tgt` string that `translate_docx` passes at the seam (grep the
`targets` list origin). If the live target is `"Vietnamese"`, key `"vietnamese"`
matches; if it is `"vi"`/`"vi-VN"`, the guard would silently fail-safe (no flag) and
AC-1 integration would not fire. Confirm the live `tgt` value and seed accordingly
(add both `"vietnamese"` and any code form the app actually uses); state the confirmed
value in the agent log. This is the one place a wrong assumption makes the guard inert.

### IP-4 — `_recover_truncated_cell(cell_text, tgt, src_lang, client, max_batch_chars, stop_flag, log) -> str`
Module-level helper in docx_processor.py mirroring the BR-82 per-cell logic
(L1101-1119) for ONE cell. NON-RE-ENTRANT: it never calls `is_suspiciously_short`.
- `lines = cell_text.split("\n")`
- `uniq_lines = list(dict.fromkeys(l for l in lines if l.strip() and should_translate(l, src_lang or "auto")))`
- `fallback_tmap = {}`; if `uniq_lines`: `fallback_tmap, _, _, _ = translate_texts(uniq_lines, [tgt], src_lang, client, max_batch_chars=max_batch_chars, stop_flag=stop_flag, log=log)`
- return `"\n".join(fallback_tmap.get((tgt, l), l) for l in lines)`

All args (`translate_texts`, `should_translate`, `client`, `src_lang`,
`max_batch_chars`, `stop_flag`, `log`) are already imported/in-scope in
`translate_docx`. Do NOT extract or alter the existing L1101-1119 block (AC-7).

### IP-5 — Guard wiring at docx_processor.py:1054-1058
Replace the current body of `if translated_by_pos is not None:` with a loop that,
per accepted cell, runs the guard and recovers on a flag. Enforcement of the
ADR-0020 invariants:
- **bound = 1 / never-loop:** recovery is a single straight-line call to
  `_recover_truncated_cell` per unique flagged cell text (no loop, no retry). The
  helper does not re-enter the guard. `TRUNCATION_GUARD_MAX_RECOVERY_ATTEMPTS = 1`
  documents this and is asserted by `test_recovery_bounded_single_attempt_no_reentry`
  (exact `translate_texts` call count).
- **keep-longest:** `final_value = accepted if len(accepted) >= len(recovered) else recovered`.
- **never-source / never-BR-25:** neither branch writes `s.text` (whole source) nor
  the `[Translation failed|...]` BR-25 format. `recovered` is a per-line translation
  reassembly (missing lines fall back to their original LINE per the BR-82 pattern —
  this is existing partial-recovery, not wholesale source substitution); keep-longest
  picks between the two translation attempts.
- **dedup + one WARNING:** cache recovered values by `s.text` so a merged cell
  spanning multiple `t_segs` is recovered once and emits exactly ONE
  `logger.warning("[DOCX] truncation-guard: ...")` on the `TranslateTool` logger
  (BR-109) per unique flagged cell.

Sketch (final structure to be produced by backend-engineer):
```python
if translated_by_pos is not None:
    _recovered: Dict[str, str] = {}
    for s in t_segs:
        r, c = s.row, s.col
        if s.text.strip() and (r, c) in translated_by_pos:
            accepted = translated_by_pos[(r, c)]
            if is_suspiciously_short(s.text, accepted, tgt):
                if s.text not in _recovered:
                    recovered = _recover_truncated_cell(
                        s.text, tgt, src_lang, client,
                        max_batch_chars, stop_flag, log)
                    kept = accepted if len(accepted) >= len(recovered) else recovered
                    logger.warning(
                        "[DOCX] truncation-guard: table group %s cell recovered "
                        "(target=%s) accepted_len=%d recovered_len=%d kept_len=%d",
                        table_id, tgt, len(accepted), len(recovered), len(kept))
                    _recovered[s.text] = kept
                final_tmap[(tgt, s.text, c)] = _recovered[s.text]
            else:
                final_tmap[(tgt, s.text, c)] = accepted
```

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: none — the 4 constants are `config.py` hardcoded values (NOT env vars).
  Tier-floor false-positive expected on "config"/"threshold"/"coefficient"; use
  `tier-floor-override` with written rationale (change-classification.md §Required
  Contracts). No `.env.example`/env-schema sync.
- Data shape: none — D5 rejected any IR field; `data-shape-contract.md` untouched.
- Business logic: BR-117 already written (contracts/business/business-rules.md L128).
  Implementation must conform to it. If BR-117's "acceptance seam ~L1088-1132"
  wording is revised to match the verified call site (L1054-1058), contract-reviewer
  owns that edit + a `schema-version` bump from the LIVE value — NOT the implementer.
- CI/CD: none — no workflow/Makefile edit (ci-gates.md).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_length_guard.py::test_flags_recorded_bug_ratio | 4827-char CJK src / 370-char reply flagged at k=0.3 |
| AC-1 | tests/test_docx_nested_tables.py::test_layout_cell_truncated_reply_flagged_and_recovered | short whole-table JSON reply routed through guard; written final_tmap cell recovered |
| AC-2 | tests/test_length_guard.py::test_cell_seam_flags_and_recovers_truncated_reply | recovered length ≫10% of E; never equals source |
| AC-3 | tests/test_length_guard.py::test_zero_false_positives_calibration_fixtures | zero flags on legit-short CJK-heavy + latin-heavy pairs at k=0.3 |
| AC-4 | tests/test_length_guard.py::test_failsafe_unknown_target | no flag when target absent from table |
| AC-4 | tests/test_length_guard.py::test_failsafe_short_source_below_min_chars | no flag when normalized source < 15 |
| AC-4 | tests/test_length_guard.py::test_failsafe_zero_expected_length_numeric_source | no flag when E == 0 |
| AC-5 | tests/test_length_guard.py::test_numeric_cell_never_reaches_guard | BR-68 numeric never counted as truncation |
| AC-6 | tests/test_length_guard.py::test_recovery_bounded_single_attempt_no_reentry | exact translate_texts call count; no re-entry |
| AC-6 | tests/test_length_guard.py::test_recovery_keeps_longest_on_exhaustion_never_source | kept == longer attempt; never source; never BR-25 |
| AC-7 | tests/test_length_guard.py::test_normal_length_reply_unaffected_no_recovery_no_warning | plausible-length reply: no recovery, no WARNING |
| AC-7 | tests/test_json_translation_body.py::test_body_path_unaffected_by_length_guard | body path unchanged |
| AC-8 | tests/test_length_guard.py::test_mixed_composition_excludes_numeric | E from composition model, numeric excluded |

Required phases (floor): **collect, targeted, changed-area**; plus **contract**
(business-rules.md touched) and **full** (final, AC-7 regression). Generate evidence
via `cdd-kit test run`; full ladder + falsifiability in test-plan.md and
references/sdd-tdd-policy.md. Conda-scoped (torch/COMET tests resolve only inside
`translate-tool`):
```
conda run -n translate-tool cdd-kit test run --phase targeted
conda run -n translate-tool cdd-kit test run --phase changed-area
conda run -n translate-tool cdd-kit test run --phase full
```

**Ordering:** monkey-test-engineer (IP-7) runs AFTER backend-engineer and ADDS
FP-boundary fuzz tests. The ladder (at minimum targeted + changed-area + full) MUST
be re-run after IP-7 lands so those adversarial tests are covered by evidence before
qa-reviewer sign-off.

**Rollback:** purely additive (new pure module + 4 constants + `count_composition` +
one call site + one helper). Rollback is `git revert` of this change's commit;
acceptance behavior returns to accept-as-is. Guard is fail-safe-by-default (BR-68
exemption + uncalibrated-target no-flag), so even a partial revert cannot re-arm a
false-positive. No schema/data/env/IR change to reverse.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into code;
  follow the source pointers above.
- Do NOT touch the BR-82 `else`-branch (docx L1059-1132) or `render_truncated` or
  `tests/metrics/truncation_rate.py`.
- Verify the live `tgt` string vs the coefficient-table key before claiming AC-1
  integration passes (IP-3 note) — a mismatch makes the guard silently inert.
- If this plan omits a required file, behavior, contract, or test, stop and report
  `blocked`. Keep work within the File-Level Plan unless a Context Expansion Request
  is approved.

## Known Risks
- **Coefficient-key / live-target mismatch** makes the guard fail-safe-inert (no flag,
  AC-1 integration silently green-but-meaningless). Mitigation: IP-3 note — confirm
  and seed the actual `tgt` form.
- **Calibration rests on one language pair** (→Vietnamese). Fail-safe for unlisted
  targets is load-bearing (ADR-0020 invariant 1); do not add a broad default.
- **Recovery's per-line missing-line fallback** can leave original (untranslated) LINE
  fragments in `recovered`; keep-longest still never writes the whole source nor BR-25.
  Assert on the WRITTEN final_tmap value (test-plan.md: not call-wiring).
- **BR-117 line-citation drift** (`~L1088-1132` vs verified L1054-1058). Flagged for
  contract-reviewer; implementers follow this plan's verified site.
- `.cdd/code-map.yml` was accurate for the ranges used here (docx 840-1157,
  text_utils 46-52, config 134-139); no staleness observed.
