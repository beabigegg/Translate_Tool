# Archive — doc-context-sampling-fix

## Change Summary

BR-109 shipped the one-sentence document-context summary to cloud providers, but
live verification of job `d19484ce43f94fa4b076ef0a0d07abae` showed it never fired
on real documents: the sampler feeding it (`_sample_file_text` in
`app/backend/processors/orchestrator.py`) returned an empty string for legacy
`.xls` files and for `.docx`/`.pptx` documents whose text lives in tables, and the
skip left no trace at INFO. This change repairs the sampler for all three document
shapes and makes every context-detection outcome observable, so a skipped summary
can never again masquerade as a successful one.

## Final Behavior

- `.xls` sampling converts the file through the existing LibreOffice
  `xls_to_xlsx` helper into a `tempfile.TemporaryDirectory()` and reads the result
  with openpyxl, guarded by `is_libreoffice_available()`; when LibreOffice is
  absent it returns `""` without raising.
- `.docx` sampling includes `doc.tables` cell text after paragraphs; `.pptx`
  sampling includes table/graphic-frame cell text alongside `has_text_frame`
  shapes. Both honor the `max_chars` budget.
- `_detect_document_context` now emits, through the job `log(...)` callback (the
  channel that reaches `translator.log`), one of four distinct outcomes:
  `[CONTEXT] Detected: …` on success; `[CONTEXT] Skipped: provider call failed`;
  `[CONTEXT] Skipped: provider returned an empty summary`; and
  `[CONTEXT] Detection failed: <exc>`. `process_files` emits
  `[CONTEXT] Skipped context detection for <file>: empty sample` when the gates
  are open but no sample could be obtained.
- `_sample_file_text` still never raises into the job pipeline; a sampling failure
  degrades to no preamble, preserving BR-109's graceful fallback.

Verified in production on job `53676512617243fcbbc60dbac0201102`: both the legacy
`.xls` and the table-only `.docx` emitted `[CONTEXT] Detected:` for the first time,
and `cache_variant` changed from `technical_process_crit` to
`technical_process_ctx_crit`, confirming the summary reached `build_strategy`.

## Final Contracts Updated

- `contracts/business/business-rules.md` — BR-109 amended in place (no new rule
  id); `schema-version` 0.27.0 → 0.27.1. The rule now defines what a valid sample
  is (must include table-resident text and legacy-format text via the existing
  conversion path, not only top-level paragraphs; an empty string for a document
  that in fact contains text is a defect, not a valid graceful-fallback trigger)
  and requires that a skip never be silently indistinguishable from a success in
  the job log.
- `contracts/CHANGELOG.md` — `[business 0.27.1]` entry.

Evidence: `agent-log/contract-reviewer.yml`.

## Final Tests Added / Updated

12 new tests in `tests/test_orchestrator_context_detection.py` (24 total in file;
the 12 prior-change tests are unmodified):

- Sampling: legacy `.xls` via mocked-Popen conversion, table-only `.docx`,
  table/graphic-frame `.pptx` — each asserts a distinctive fixture token
  (`PANJIT-XLS-TOKEN-771`, `PANJIT-TABLE-TOKEN-771`, `PANJIT-PPTX-TABLE-TOKEN-556`),
  never mere non-emptiness.
- Observability: success, exception, `ok=False`, empty-summary, and empty-sample
  skip — each asserts on the `"TranslateTool"` logger or the captured `log`
  callback, i.e. the channel that reaches `translator.log`.
- Data-boundary: a sampler that raises yields a completed job with no
  `Document context:` preamble in the outgoing request.
- AC-7: with `translate_xlsx_xls` stubbed, `subprocess.Popen` is invoked exactly
  once per `.xls` on the sampler side.

Falsifiability check (main Claude): removing the four `log(...)` delivery calls
while keeping the additive `logger.info(...)` turns 7 tests red; restoring returns
24/24 green. Full suite: 1270 passed, 4 skipped.

Evidence: `agent-log/bug-fix-engineer.yml`, `test-evidence.yml`,
`test-runs/20260709-145117` (pre-fix behavioral RED).

## Final CI/CD Gates

No workflow edit. Per `ci-gates.md`, the merge-blocking `contract-and-fast-tests`
job already runs the blanket `pytest tests/ -x -q`, so every AC is proven by a
non-skippable assertion. `ci-cd-gatekeeper` explicitly declined to add this file
to `libreoffice-conversion-gate`, whose LibreOffice install is `continue-on-error`
— a real-binary requirement there could skip silently while all gates report green.
The AC-1/AC-7 tests therefore mock the LibreOffice process boundary
(`subprocess.Popen`) so they run on every runner. CI run `29001218918`: 8 jobs
success, `scheduled-stress-soak` skipped.

## Production Reality Findings

1. **The observability fix initially reproduced the very defect it was repairing.**
   The new INFO lines used `logging.getLogger(__name__)`. `translator.log`'s
   `RotatingFileHandler` is attached to the `"TranslateTool"` logger and root has
   no handlers, so those records were dropped at runtime while `caplog` tests
   passed. Proven by executing `setup_logging()` and probing both channels. Every
   outcome now goes through the job `log(...)` callback.

2. **A fifth form of tautological test.** `caplog.at_level(level, logger="X")`
   sets `X`'s level but does NOT restrict which loggers' records land in
   `caplog.records` — pytest attaches its handler to the ROOT logger. Three
   assertions lacked a `record.name` filter and stayed green with the real
   delivery channel removed. AC-8 — the criterion encoding the user's own success
   condition — was among them.

3. **A genuinely silent failure path survived the first implementation pass.**
   `_detect_document_context` returned `""` with no log when `client.complete()`
   reported `ok=False` or an empty summary; no exception was raised, so the
   exception handler never ran. This violates BR-109 as written.

4. **AC-7 as originally stated was self-contradictory, and the contradiction came
   from the change-request, not an agent.** "Does not double-convert AND does not
   change the processor's per-file timing" cannot both hold: leaving
   `xlsx_processor` untouched necessarily converts a `.xls` twice per run.
   `implementation-planner` — the first shell-capable agent — caught this against
   live source and refused to plan around it. AC-7 was amended to the provable
   claim (sampler-side conversion at most once per file).

5. **The summary reaches the model but is not sufficient for isolated header
   cells.** A controlled 5×-repeated live trial against PANJIT (deterministic,
   not sampling noise): `制作者` improves with the preamble (`người tạo` →
   `người soạn`), but `制作日期` returns `Ngày sản xuất` under every condition.
   The summary describes the document, not the role of a given cell; a 4-character
   header field translated in isolation still lacks the row context that
   disambiguates it. The remedy is whole-table context, which is blocked by the
   deferred phantom-column defect and restored by the planned JSON structured I/O.

6. **A sibling bug was discovered during that investigation, out of scope here.**
   `OpenAICompatibleClient.__init__` takes no `system_prompt` parameter while
   `OllamaClient.__init__` does, so `base_system_prompt = client.system_prompt`
   (orchestrator.py:608) is always `""` on cloud providers. The profile's base
   system prompt (e.g. the semiconductor role declaration and terminology
   guidance) never reaches PANJIT/DeepSeek — only the scenario appendix, few-shot
   block, and document-context preamble do. Same family as the BR-109 defect:
   there, a write was silently discarded; here, the write never happens.

7. **The classifier's proposed file paths were all real.** Every path in the
   context manifest (including `libreoffice_helpers.py`, `context_prompts.py`,
   `logging_utils.py`) was verified on disk before the manifest was written. CER-001
   was never exercised and is recorded as withdrawn.

## Lessons Promoted to Standards

Classified by `contract-reviewer` at close-out. `CLAUDE.md`'s managed region held
21 bullets before and 21 after — net-zero growth; both guidance lessons were folded
into existing entries rather than appended.

| Lesson | Decision | Where it landed |
|---|---|---|
| L1 — `caplog.at_level(..., logger="X")` does not filter `caplog.records` by logger, because pytest attaches its handler to ROOT | promote-to-guidance | Folded into the existing `CLAUDE.md` tautological-tests bullet, which now names **five** forms (added: caplog root-logger bleed). Evidence: archive.md finding 2; `agent-log/qa-reviewer.yml` tautology-audit. |
| L2 — only the logger named `TranslateTool` reaches `translator.log`; a `getLogger(__name__)` INFO call is dropped in production | promote-to-contract | `contracts/business/business-rules.md` BR-109 amended in place; `schema-version` 0.27.1 → 0.27.2 (patch, clarification) plus a `[business 0.27.2]` CHANGELOG entry. Evidence: archive.md finding 1; `agent-log/bug-fix-engineer.yml`. |
| L3 — the first shell-capable agent must also catch a self-contradictory acceptance criterion authored by the human, not only a wrong seam name | promote-to-guidance | Folded into the existing `CLAUDE.md` no-shell-planning-agents bullet as an appended clause + pointer to AC-7. Evidence: archive.md finding 4; `agent-log/implementation-planner.yml`. |
| L4 — a document-context summary does not disambiguate an isolated header cell | do-not-promote | Roadmap rationale from a single controlled trial, not a standing rule. Stays in finding 5 and Follow-up Work; it is the empirical case for the JSON structured-I/O change. |
| L5 — cloud providers silently drop the profile's base system prompt | do-not-promote | An OPEN, unfixed defect. Promoting it would encode a bug as accepted behavior. Tracked in Follow-up Work and handed to the next change. |

`cdd-kit validate --contracts` green after the BR-109 amendment; the absence-tested
tokens (`BR-92`, `rescore`) remain absent from `business-rules.md`.

## Follow-up Work

- **Cloud providers drop the profile's base system prompt** (finding 6). Tracked
  as the next change; user has approved starting it.
- **xlsx table-batch phantom-column defect**: `ws.max_column` is 257 against 47
  real cells, so `table_serializer.parse()` can never match the demanded shape,
  always returns `None`, and each sheet wastes one large LLM call before the BR-82
  per-cell fallback. Deferred to the JSON structured-I/O change, where the
  pipe-grid round-trip disappears. Confirmed still failing in the post-fix run
  (`expected 9×257`, `expected 16×257`).
- **Residual double conversion**: a `.xls` is converted by the sampler and again
  by the untouched `xlsx_processor`. Sharing/caching one conversion is a separate
  refactor.
- **Critique-loop cost**: each segment issues 1 translate + 3 critique calls.
  Observed, not investigated; the 134-segment `.docx` took ~47 minutes.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
