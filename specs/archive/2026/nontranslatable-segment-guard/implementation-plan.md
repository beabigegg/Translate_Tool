---
change-id: nontranslatable-segment-guard
schema-version: 0.1.0
last-changed: 2026-07-08
---

# Implementation Plan: nontranslatable-segment-guard

## Objective

Add two additive guards to the body (non-table) translation path so a trivial/
non-translatable segment can never round-trip through the cloud LLM into a
meta/refusal reply written verbatim into output:

- **INPUT guard (BR-107)** — in `translate_merged_paragraphs`, before the
  `client.translate_once` call, skip trivial/non-translatable segments by
  **reusing the existing `text_utils.should_translate` predicate**; on `False`,
  set the result to the source unchanged with **no LLM call** (mirrors the table
  BR-68 numeric passthrough at `translation_service.py:887`, applied at
  body-segment granularity).
- **OUTPUT guard (BR-108)** — after `ok=True`, run a NEW precise `is_meta_refusal`
  detector; if the reply is a meta/refusal (ask-back for source text,
  question-back, language-detection/notes remark), discard it and write the
  **source** instead — never the meta string.

Reuse the existing `passthrough`/`failed` dispositions in prose only. **No new
`translation_status` enum value, no data-shape field, no config value change**
(a small module-level threshold constant is permitted if documented). Deliver a
RED-before / GREEN-after reproduction from the real 8D trivial segments + a fake
client. BR-107, BR-108, and Table Z are **already applied** in
`contracts/business/business-rules.md` (0.26.0) — do not re-edit them.

## Execution Scope

### In Scope
- INPUT guard in `translate_merged_paragraphs` (`app/backend/utils/translation_helpers.py`, L133-199) reusing `should_translate`.
- NEW `is_meta_refusal(reply, source)` pure helper in `app/backend/utils/text_utils.py`, and its application in `translate_merged_paragraphs` after `ok=True`.
- NEW test file `tests/test_nontranslatable_segment_guard.py` (bug-fix lane: RED repro first, then GREEN).
- Keep BR-68 table path, context-window seam, and existing translate_once/translate_merged_paragraphs fakes green.

### Out of Scope (do NOT touch — see change-request.md `## Non-goals`)
- The table-cell path and its BR-68 numeric passthrough (`translation_service.py:887`, `_translate_table_element`).
- The legacy sentence-level branch in `translate_blocks_batch` (L436+) and the non-batch per-text loop in `translation_service.py` (L395-420) — BR-107/BR-108 scope only `translate_merged_paragraphs → client.translate_once`.
- Step-2 cloud doc-summary and step-3 JSON structured I/O (separate changes).
- Office (docx/pptx/xlsx) output modes, judge loop, QE/COMET, layout detection.
- Any `contracts/data/data-shape-contract.md` edit or new `translation_status` value (default plan reuses `passthrough`/`failed`). Introducing one flips Architecture Review to `yes` → stop and route to spec-architect.
- Any change to `client.translate_once` signature (guards live above the client call).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | `text_utils.py` | Add NEW pure helper `is_meta_refusal(reply: str, source: str) -> bool` (BR-108 detector) with a precise allowlist + length gate; document the module-level `META_REFUSAL_MAX_CHARS` constant. Do NOT modify `should_translate`/`is_numeric_cell`. | bug-fix-engineer |
| IP-2 | `translation_helpers.py` | INPUT guard (BR-107): in `translate_merged_paragraphs`, replace the empty/whitespace early-continue (L169-174) with `if not should_translate(text, src_lang or "auto"): results[i] = (True, text or ""); continue` (no client call). Add import of `should_translate, is_meta_refusal` to L19. | bug-fix-engineer |
| IP-3 | `translation_helpers.py` | OUTPUT guard (BR-108): after `ok, translated = client.translate_once(...)` and inside `if ok:`, `if is_meta_refusal(translated, text): results[i] = (True, text)` (source fallback; do not call `on_segment_done`); else keep existing `results[i] = (True, translated)` + `on_segment_done`. | bug-fix-engineer |
| IP-4 | `tests/test_nontranslatable_segment_guard.py` (NEW) | Write RED repro first, then the full AC-1..AC-6 suite per test-plan.md node IDs (call-counter fake for passthrough; ask-back fake for refusal; negative case for AC-3). | bug-fix-engineer |
| IP-5 | regression | Grep `tests/` for `translate_once`/`translate_merged_paragraphs` fakes; keep them green (see `## Test Execution Plan` grep list). Update any fake broken by the new branches **in this change**. | bug-fix-engineer |
| IP-6 | bug-fix evidence | Record `agent-log/bug-fix-engineer.yml` `bug-fix:` block: RED-before / GREEN-after per ADR 0006 §6/§7; reproduction command == recorded run minus runner flags. | bug-fix-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | `## Acceptance Criteria → Test Mapping` (AC-1..AC-7), `## Notes` | exact test node IDs to write; anti-tautology rules |
| ci-gates.md | `## Required Gates` table, `## Merge Eligibility Decision` | verification commands (contract + blanket pytest via `contract-and-fast-tests`) |
| change-request.md | `## Root cause`, `## Desired behavior` (a)/(b), `## Non-goals`, `## Constraints` | fix intent + scope boundaries |
| change-classification.md | `## Inferred Acceptance Criteria` AC-1..AC-7; `Bug Evidence Required` | AC list + bug-fix-lane evidence requirements |
| business-rules.md | BR-107 (L118), BR-108 (L119), Table Z (L446-457), BR-68 (L80), BR-25 (Table F L172-183) | implementation constraints (already applied — reference only, do not edit) |
| context-manifest.md | `## Allowed Paths` | read boundary |
| — | ADR 0006 §6/§7 (cdd-kit README bug-fix evidence rules) | RED/GREEN evidence format |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/utils/text_utils.py` | edit (add helper) | ADD `is_meta_refusal(reply, source) -> bool` + `META_REFUSAL_MAX_CHARS` near `should_translate` (L75-133) / `is_numeric_cell` (L23-43). Do NOT change `should_translate` (sig `should_translate(text: Any, source_lang: str)`; ignores `source_lang`; returns `False` for empty/whitespace/pure-punct/pure-number/number+punct/`<3` non-CJK letters). |
| `app/backend/utils/translation_helpers.py` | edit | L19 import: add `should_translate, is_meta_refusal`. L133-199 `translate_merged_paragraphs`: INPUT guard replaces L169-174; OUTPUT guard inside the `if ok:` block at L189-192. No signature change. |
| `app/backend/services/translation_service.py` | **no code change** | Verify only: the existing tmap mapping (L374-388) already treats `(True, source)` as success and writes source into `tmap[(tgt, text)]`; passthrough/fallback need no result-mapping edit. BR-68 site (L887) untouched. |
| `contracts/business/business-rules.md` | **no change** | BR-107/BR-108/Table Z ALREADY applied (0.26.0). Do not re-edit. |
| `contracts/data/data-shape-contract.md` | **no change** | Conditional only; reusing `passthrough`/`failed` needs no edit. |
| `tests/test_nontranslatable_segment_guard.py` | create | Full AC suite per test-plan.md; RED first. |

### Exact INPUT-guard reuse (BR-107)

`should_translate(text: Any, source_lang: str) -> bool` (text_utils.py L75-133)
already returns `False` for: empty/`None`, whitespace-only, pure punctuation/
symbols, pure digits, number-with-punctuation (`"5."`, `"1.4"`, `"-10"`,
`"3,900"`), no-letter strings, and very short single tokens (`<3` alphabetic
chars, non-CJK). It ignores `source_lang` by design. **Call it as
`should_translate(text, src_lang or "auto")`** — the arg is inert.

Guard (replaces the L169-174 empty/whitespace early-continue, which
`should_translate` subsumes):

```
for i, text in enumerate(texts):
    if not should_translate(text, src_lang or "auto"):   # BR-107 input passthrough
        results[i] = (True, text or "")                  # output = source, NO client call
        completed += 1
        if progress_log: progress_log(completed)
        continue
    ...  # existing context-prefix + translate_once path unchanged
```

Note `text or ""` preserves the current `(True, "")` result for the truly-empty/
`None` case while giving `(True, text)` (exact source) for whitespace-only and
all other trivial classes, satisfying Table Z "output = source". This is
**conservative**: any segment with ≥3 non-CJK letters (or any CJK) still goes to
the LLM. The "already-target-language single token" Table Z row is covered only
insofar as such a token is ALSO short (`should_translate` False); a longer
already-target-language label is intentionally left to the LLM and caught by the
OUTPUT guard if the model refuses — do NOT add target-language detection (that
would risk dropping real text and violates the conservative constraint). Choose
the AC-1 `test_already_target_language_token...` fixture accordingly (a short
token the predicate already rejects, e.g. the 8D lone page-number/label).

### Exact OUTPUT-guard spec (BR-108)

NEW helper in `text_utils.py`:

```
META_REFUSAL_MAX_CHARS = 200   # module constant (NOT config/env); documented per plan

def is_meta_refusal(reply: str, source: str) -> bool:
    r = (reply or "").strip()
    if not r:
        return False
    # length gate: a genuine translation of a real paragraph is not a terse meta
    # sentence — only short replies are refusal candidates (false-positive guard).
    if len(r) > META_REFUSAL_MAX_CHARS:
        return False
    low = r.lower()
    return any(pat in low for pat in _META_REFUSAL_PATTERNS)
```

`_META_REFUSAL_PATTERNS` = a SMALL allowlist of self-referential ask-for-source /
meta signatures (case-insensitive substrings/regex), e.g.: `"provide the text"`,
`"text you'd like translated"`, `"text you would like translated"`,
`"what would you like me to translate"`, `"which language"`, `"no text"` +
`"provided"`, `"i don't see any text"` / `"i do not see any text"`,
`"please provide"` (+ `"text"`). Cover the 8D reply
"Could you please provide the text you'd like translated?" and the July-2 log
"Please provide the text you would like translated".

**False-positive guard (AC-3 — mandatory):** the detector triggers ONLY on an
allowlist match within the length gate. It MUST NOT fire merely because the reply
contains `"?"` or "reads like a note" — a naive "suppress anything with a
question mark" implementation MUST FAIL
`TestRefusalDetectorNegative::test_genuine_translation_containing_question_mark_is_not_suppressed`.

**Application** (translation_helpers.py, inside `if ok:` at L189-192):

```
if ok:
    if is_meta_refusal(translated, text):     # BR-108 output guard
        results[i] = (True, text)             # source fallback; do NOT call on_segment_done
    else:
        results[i] = (True, translated)
        if on_segment_done:
            on_segment_done(text, translated)
```

Fallback is **source** (not the BR-25 failed placeholder) so AC-2 tests assert
the exact SOURCE value is written. Skipping `on_segment_done` avoids caching a
fallback.

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: none.
- Data shape: none — reuse existing `passthrough`/`failed` dispositions in prose; NO new `translation_status` value; NO `data-shape-contract.md` edit. (Introducing one flips Architecture Review to `yes` — stop and route to spec-architect.)
- Business logic: BR-107, BR-108, Table Z ALREADY applied in `contracts/business/business-rules.md` (0.26.0). No further edit; `cdd-kit validate --contracts` verifies structurally.
- CI/CD: none (existing `contract-and-fast-tests` blanket pytest auto-collects the new test file).

## Test Execution Plan

TDD sequence for bug-fix-engineer (bug-fix lane):

1. **RED** — write `tests/test_nontranslatable_segment_guard.py::TestReproduction8D::test_8d_trivial_segment_fixture_ask_back_fake_red_pre_fix_green_post_fix` (and the AC-1/AC-2 core cases) using real 8D trivial segments (lone page-number, already-English label, punctuation-only) + a **call-counter fake** `LLMClient` (assert `call_count == 0` for trivial and result == exact SOURCE) and a fake returning the ask-back string (assert SOURCE written, meta string NOT written). Run against current code → **RED**.
2. Implement IP-1..IP-3.
3. **GREEN** — re-run; all AC-1..AC-6 pass.
4. **Grep + keep fakes green** — `grep -rn "translate_once\|translate_merged_paragraphs" tests/`. Directly-affected: `tests/test_context_prefix_bleed.py` (calls `translate_merged_paragraphs([SEG1,SEG2,SEG3], "vi", "zh-CN", client)` — SEG1-3 are substantial CJK sentences → `should_translate` True → still sent; must stay green), `tests/test_pdf_layout_table_fixes.py` (translate_once fakes serve the body path), `tests/test_sentence_mode_consistency.py` (sentence-branch fake — unaffected). Keep green: `tests/test_table_recognizer.py`, `tests/test_table_context_translation.py` (AC-5 BR-68), `tests/test_context_window_segments.py`.
5. **Bounded ladder** — run scoped to the NEW node-ids via the conda env (torch/CI-parity per CLAUDE.md):
   `conda run -n translate-tool cdd-kit test run --phase collect`
   `... --phase targeted` / `... --phase changed-area` / `... --phase contract`, scoped to `tests/test_nontranslatable_segment_guard.py` (+ the regression files above for changed-area). Required floor: collect, targeted, changed-area; add contract for BR-107/BR-108. Full ladder detail lives in test-plan.md / `references/sdd-tdd-policy.md`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_nontranslatable_segment_guard.py::TestTrivialPassthrough | fake `call_count == 0`; result == exact source (pure-number, punctuation-only, whitespace-only, already-target token, very-short token) |
| AC-2 | tests/test_nontranslatable_segment_guard.py::TestRefusalOutputGuard | ask-back/question-back/language-note reply → SOURCE written, meta string NOT written |
| AC-3 | tests/test_nontranslatable_segment_guard.py::TestRefusalDetectorNegative | genuine translation with `?` / note-like text NOT suppressed |
| AC-4 | tests/test_nontranslatable_segment_guard.py::TestConservativePassthrough | genuine sentence IS sent to client and translated |
| AC-1,2,4 | tests/test_nontranslatable_segment_guard.py::TestTranslateMergedParagraphsEndToEnd | trivial + refusal + normal segments in one `translate_merged_paragraphs` call |
| AC-6 | tests/test_nontranslatable_segment_guard.py::TestReproduction8D | RED pre-fix, GREEN post-fix, no live LLM |
| AC-5 | tests/test_table_recognizer.py; tests/test_table_context_translation.py | unchanged, green (BR-68 unaffected) |
| AC-7 | `cdd-kit validate --contracts` | exit 0 (BR-107/BR-108/Table Z structurally valid) |
| n/a | tests/test_context_window_segments.py; tests/test_context_prefix_bleed.py | unchanged, green (context seam unaffected) |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Guards live ONLY in `translate_merged_paragraphs` + `text_utils.py`. Do NOT touch the BR-68 table path, `client.translate_once` signature, or the legacy sentence/non-batch loops.
- If the fix would need a new `translation_status` value, STOP and report `blocked` (routes to spec-architect + design.md + data-shape-contract.md).
- Regression suites are run via `cdd-kit test run` (execution, not Read). If step 4 reveals a fake that must be READ/EDITED and its file is outside `context-manifest.md` Allowed Paths (e.g. `test_context_prefix_bleed.py`, `test_pdf_layout_table_fixes.py`), file a Context Expansion Request before editing.

## Known Risks

- **Whitespace-only semantics:** the INPUT guard changes the whitespace-only result from `(True, "")` to `(True, text)` to satisfy Table Z "output = source". Confirm no downstream consumer of `translate_merged_paragraphs` relies on `""` for whitespace input (empty/`None` still yields `(True, "")` via `text or ""`).
- **Over-passthrough hazard:** any borderline segment MUST default to the LLM. Do not add language detection or lower `should_translate`'s `<3` threshold — conservative by mandate (change-request `## Constraints`).
- **Refusal false-positive (AC-3):** the allowlist + length gate must be precise; a naive `"?"`/note heuristic must fail the negative test. Keep `_META_REFUSAL_PATTERNS` small and self-referential ("provide the text", not generic verbs).
- **Fake-double breakage:** additive branches can break test doubles that count calls or fake `translate_once` — grep and update in the SAME change (CLAUDE.md learning; recurred 3×).
- **New constant:** `META_REFUSAL_MAX_CHARS` is a module-level constant in `text_utils.py`, NOT a `config.py`/env value — document its purpose in a comment; no env-contract change.
- **Cloud-only providers:** PANJIT/DeepSeek only; Ollama never used — the "cache"/"provider" vocab in the artifacts is evidence, not a routing change.
- **code-map:** plan scoping used `.cdd/code-map.yml`-equivalent line pointers from the change-request/test-plan (translation_helpers.py L133-199, text_utils.py L75-133, translation_service.py L887), verified against source; no stale-map risk noted.
