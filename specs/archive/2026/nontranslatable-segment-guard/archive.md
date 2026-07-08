# Archive — nontranslatable-segment-guard

## Change Summary
Fixed a translation-output bug where a trivial/non-translatable **body** segment (a lone
number, punctuation-only, an already-target-language label like "Executive Summary:", or a
very short token) was sent to the cloud LLM (PANJIT gpt-oss), which replied with a
META/REFUSAL ("Could you please provide the text you'd like translated?") that got written
verbatim into the output document. Reproduced on the 8D PDF English run (task `42265c0b`);
pre-existing (July-2 log, different doc/model), cache empty (live reply), NOT caused by
`context-prefix-bleed-fix`. Root cause: table cells already had a non-translatable
passthrough (BR-68) but body segments had neither an input passthrough nor an output-side
meta/refusal guard.

## Final Behavior
- **Input guard (BR-107)**: a trivial/non-translatable body segment on the
  `translate_merged_paragraphs` path is NOT sent to the LLM — reusing
  `text_utils.should_translate(text, source_lang)` — and its output is set equal to its
  source, mirroring BR-68 at body-segment granularity. Conservative: ambiguous/borderline
  content still reaches the LLM.
- **Output guard (BR-108)**: after a body-path `translate_once` returns `ok=True`, the reply
  is checked by the new `text_utils.is_meta_refusal(reply, source)` (a small allowlist gated
  by `META_REFUSAL_MAX_CHARS=200` — precise, not a bare "?" check). A meta/refusal reply is
  discarded and the SOURCE is kept, never written to output.
- No `translation_service` / client / config-value change. Table-cell BR-68 path unchanged.

## Final Contracts Updated
- `contracts/business/business-rules.md` — NEW **BR-107** (body-segment-passthrough) +
  **BR-108** (meta-refusal-output-guard) + **Table Z**; `schema-version` 0.25.1 → 0.26.0.
- `contracts/CHANGELOG.md` — `[business 0.26.0]` entry.
- No api/env/ci change; **no data-shape change** (contract-reviewer confirmed
  `translation_status` is TableCell-only; the body path has no such field, so the
  passthrough disposition is reused in prose — no new enum value, keeping Architecture
  Review at "no").

## Final Tests Added / Updated
- `tests/test_nontranslatable_segment_guard.py` (NEW) — 18 tests: trivial-passthrough
  (call-counter fake asserts `call_count==0` AND exact SOURCE value), meta/refusal guard
  (source written, meta string absent), the MANDATORY negative case (a genuine translation
  containing "?" is NOT suppressed), conservative-passthrough (`call_count>0` for real
  content), and direct `is_meta_refusal` unit coverage. Real 8D trivial segments as fixture.
- Bounded ladder (collect/targeted/changed-area/contract) + full smoke all passed.

## Final CI/CD Gates
- `contract-and-fast-tests` (required) — `cdd-kit validate --contracts` + blanket `pytest`;
  auto-covers the new test + BR-107/108. **Green on PR #24.**
- `full-regression` (informational) + all format/renderer gates — **green on PR #24.**
- No new workflow/job/secret. Rollback = single `git revert`.

## Production Reality Findings
- **Reproduction faithfulness caught in QA-loop**: the first RED run was a *collection
  ImportError* (the repro test imported the not-yet-existing `is_meta_refusal` at module
  level), which is a WEAK reproduction — it proves the test can't load, not that the bug
  reproduces. It was re-captured via the temporary-restore recipe (keep the new helper in
  `text_utils.py`, restore ONLY the pre-fix `translation_helpers.py` behavior) as a genuine
  *behavioral* assertion failure (`assert 1 == 0`, `FakeLLMClient.call_count` — the trivial
  "1" segment was genuinely sent). qa-reviewer independently reverted-and-ran to confirm.
- **Reuse over duplication**: `text_utils.should_translate` already implemented the trivial
  classifier — the fix extended/reused it rather than writing a new predicate.
- **Residual risk (noted, non-blocking)**: `should_translate` returns False for `<3`
  non-CJK-letter tokens — conservative source-bias, correct on this CJK-source platform; a
  legit 1–2 letter word on an English→CJK job would pass through untranslated (low likelihood).

## Lessons Promoted to Standards
- **A (body-path passthrough + meta/refusal guard)** — do-not-promote-again: fully held by
  BR-107 + BR-108 + Table Z (`business-rules.md` 0.26.0) applied this change. Domain behavior,
  not CLAUDE.md guidance.
- **B (a collection ImportError is not a faithful bug-fix RED)** — promote-to-guidance,
  FOLDED into the existing `cdd-kit:learnings` bug-fix-evidence bullet (net 0 new bullets):
  added that the pre-fix RED must be a BEHAVIORAL (assertion) failure, not a collection/import
  error, and that the temporary-restore recipe must KEEP any new pure helper/symbol the fix
  introduces in place while restoring only the pre-fix behavior file (else importing the fix's
  own new symbol makes the module fail to collect — not a faithful RED). No schema bump.
  Evidence: `agent-log/bug-fix-engineer.yml` (repro → test-runs/20260708-203123 assertion-failure);
  `agent-log/qa-reviewer.yml`; test-runs/20260708-201942 (discarded collection-error) vs
  20260708-203123 (accepted).

## Follow-up Work
- Resume the translation-prompt realignment: **step 2** (make the one-sentence doc-summary
  run on cloud providers — fix the `_cloud_client is None` skip) and **step 3** (JSON
  structured translation I/O + unify context into the system channel).

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
