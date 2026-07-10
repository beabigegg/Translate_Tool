# Archive — json-structured-translation-io

## Change Summary

Step 4, the last step, of the user's translation-prompt realignment: source JSON
in, translated JSON out. The table wire format moved from a Markdown pipe-grid
sized `ws.max_row × ws.max_column` to a coordinate-carrying JSON cell list, and
the body path moved from plain text to a `{"text"}` / `{"translation"}` envelope.
Both travel through a new `translate_json` seam on the two concrete LLM clients,
kept off the five-method Protocol. Every failure mode falls back to the
pre-change path and never fails the job, with the reason logged at INFO through
the job `log(...)` callback.

The table change subsumes the long-deferred phantom-column defect. Real
spreadsheets report 257 columns against 47 content cells, so `parse()` could
never match the demanded shape: `translator.log` records 148 all-time parse
failures and not one recorded success. Each sheet burned a large LLM call for
nothing before the BR-82 per-cell fallback did the real work, losing whole-table
context every time.

## Final Behavior

- **Table**: only content-bearing, non-numeric cells are sent, each carrying its
  original `(row, col)`. There is no grid shape to echo, so the phantom-column
  failure mode is structurally impossible. Assignment is by coordinate lookup; a
  missing coordinate rejects the whole reply (never a partial assignment); an
  unsent coordinate is ignored. A reply in which *every* returned cell is
  byte-identical to its source is an untranslated echo and triggers fallback; a
  *single* unchanged cell is legitimate and does not.
- **Body**: `{"text": …}` out, `{"translation": …}` back, structurally validated.
  One segment per call — the user chose this over batching. Unparseable JSON,
  empty `content`, a missing or wrong-typed key, or `translation == text` each
  fall back to plain-text `translate_once`.
- **Both**: BR-108's meta-refusal guard is retained and now applies to the value
  actually written, on either branch. BR-107 and BR-68 passthrough are unchanged:
  trivial and numeric cells still bypass the LLM before any envelope is built.
- **Kill switch**: `JSON_STRUCTURED_TRANSLATION_ENABLED` (default on). Flag-OFF is
  a true whole-table revert, not a degradation — the legacy pipe-grid is retained
  and frozen.

## Final Contracts Updated

- `contracts/data/data-shape-contract.md` 0.17.4 → **0.18.0**. §Table
  Serialization Wire Format rewritten. The section also **gains a consumers table
  it never had** — that absence is precisely why `docx_processor.py` was invisible
  to both the contract and the change-classifier.
- `contracts/business/business-rules.md` 0.29.0 → **0.30.0**. BR-111
  (`json-translation-seam`) and BR-112 (`body-json-translation-envelope`) added;
  BR-79, BR-80, BR-82, BR-83 amended off the pipe-grid mechanism; BR-108 retained
  and widened to the value actually written.
- `contracts/env/env-contract.md` 0.18.0 → **0.19.0**. `JSON_STRUCTURED_TRANSLATION_ENABLED`,
  synced across `env-contract.md`, `.env.example.template` and `env.schema.json`
  per the Deployment Sync Policy.
- `docs/adr/0017-json-structured-translation-seam.md` added, superseding ADR-0006.

Evidence: `agent-log/contract-reviewer.yml`, `agent-log/spec-architect.yml`.

## Final Tests Added / Updated

New: `tests/test_json_translation_prompt.py` (phrasing pin, seam presence on both
clients), `tests/test_json_translation_body.py` (envelope, five fallback triggers,
INFO logging). Extended: `test_table_serialization.py` (legacy pipe-grid cases
retained; coordinate-JSON cases added), `test_table_context_translation.py`
(`TestHostileTableJsonReplies`, 12 hostile-reply tests), `test_openai_compatible_client.py`
and `test_ollama_client_dynamic_strategy.py` (`translate_json` system-channel
delivery), `test_nontranslatable_segment_guard.py` (meta-refusal both directions),
`test_pdf_layout_table_fixes.py` (`_StubTableClient` / `_FailingClient` gained the
seam), `test_context_prefix_bleed.py` (`_FakeEchoClient` pinned to flag-OFF),
`test_env_contract.py` (flag declaration).

Final: **1361 passed, 4 skipped, 0 failed**. `tests/test_llm_client_protocol.py`
and `app/backend/clients/base_llm_client.py` untouched.

Evidence: `test-evidence.yml` (collect / targeted / changed-area / contract / full
all passed, zero waivers), `agent-log/backend-engineer.yml`,
`agent-log/e2e-resilience-engineer.yml`, `qa-report.md`.

## Final CI/CD Gates

One step added to `.github/workflows/contract-driven-gates.yml` in the
merge-blocking `contract-and-fast-tests` job: an env-sync grep asserting
`JSON_STRUCTURED_TRANSLATION_ENABLED` is present in both `.env.example.template`
and `env.schema.json`, mirroring the `JUDGE_MAX_ITERATIONS` precedent. No other
workflow edit — the blanket `pytest tests/ -x -q` already sweeps every new and
extended test file, and the transport boundary is mocked so there is no
silent-skip hazard. CI run `29069604884`: 8 jobs success.

Accepted risk, recorded in `ci-gates.md`: **no CI gate catches a systemic quality
regression on well-formed-but-wrong JSON.** The kill switch is the only
mitigation, and it is operator-triggered.

## Production Reality Findings

1. **A live probe, run before a line of code, reshaped the design and would have
   made a naive implementation a net loss.** `gpt-oss:120b` (PANJIT's translate
   model) is a reasoning model: the phrasings `Reply ONLY with JSON` and `Output a
   JSON object with a single key` make it spend its budget in `reasoning_content`
   and return `content == ""` with `finish_reason: stop`. Every call would have
   fallen back. `Return: {"translation": <your translation>}` works, 3/3.
   `response_format` (both `json_object` and `json_schema`) is accepted with HTTP
   200 and is inert. All of this is now pinned in BR-111 and in a test.

2. **Schema-valid is not translated.** Under the bad phrasing DeepSeek returned
   `{"translation": "制作日期"}` — well-formed, schema-valid, completely
   untranslated. A parse-plus-schema validator would accept it. Hence the
   echoed-source trigger, at the right grain on each path.

3. **The table envelope fixes the motivating defect, and the pipe-grid could have
   too.** Sending row-neighbours together makes both providers translate
   `制作日期` as `Ngày tạo` rather than `Ngày sản xuất`. But a probe also showed
   the *pipe-grid* succeeds on a clean 2×2 and yields the same correct answer. Its
   production failure was never the format — it was `xlsx_processor` feeding it a
   9×257 phantom grid. This overturned `implementation-planner`'s recommendation to
   delete the legacy path and produced Resolution A: retain it, frozen, behind the
   flag, so flag-OFF is a revert rather than a degradation to per-cell.

4. **Three agents each caught a contradiction authored by main Claude.**
   `implementation-planner` found that the env contract's "byte-for-byte revert"
   and AC-7's "no consumer of the old grid format remains" cannot both hold.
   `spec-architect` found ADR-0017's Decision line claimed the seam sat on the
   Protocol while design.md had ratified keeping it off. `contract-reviewer`
   overruled the classifier's proposal to amend BR-109, correctly observing that
   BR-109's mechanism was never violated. Main Claude also wrongly challenged the
   architect's ADR-0006 citation and retracted within one message.

5. **The implementation shipped "all green" with two real defects that only
   sabotage revealed.** Deleting the entire system-channel merge from
   `translate_json` left all 1326 tests passing — BR-109's preamble, BR-110's base
   prompt and BR-78's neighbor context were unguarded on the new seam, the exact
   defect family that had already shipped twice in this subsystem. Separately, a
   new `_META_REFUSAL_PATTERNS` entry `"need more context"` suppressed the
   legitimate translation `"Need more context."` and wrote the Chinese source back
   into the document. Both were found by main Claude, not reported by the agent.

6. **`spec-architect`'s sign-off found the first fix incomplete.** The narrowed
   pattern `"more context to translate"` was still an unanchored substring: *"The
   translator needs more context to translate this document."* is a legitimate
   translation and was being suppressed. Main Claude reproduced it, found a third
   case, and anchored on the first-person refusal frame. Both reviewers had been
   willing to accept it as a tracked residual; shipping a demonstrated
   false positive that this change introduced was not acceptable.

7. **`qa-reviewer` blocked on a gap main Claude had missed.** The recorded
   `test-evidence.yml` was written at 11:43; the resilience tests landed at 11:56
   and two production files were reconstructed at 12:07–12:08. The recorded full
   junit contained **zero** `TestHostileTableJsonReplies` testcases. The green
   evidence did not cover the bytes being merged. Evidence was regenerated, twice
   in the end — once after the QA block, once after the meta-refusal anchor fix.

8. **An agent destroyed uncommitted work with `git checkout`.**
   `e2e-resilience-engineer` ran `git checkout -- app/backend/utils/table_serializer.py`
   during a falsifiability toggle. Uncommitted work is invisible to git's safety
   net, so this deleted `serialize_json`/`parse_json` entirely. It caught this on
   the next test run, disclosed it, and reconstructed the file from its own earlier
   `Read` output. Main Claude then independently exercised `parse_json` against all
   nine contract rules — correct accept/reject with a distinct named reason for
   each — and regenerated the evidence over the reconstructed bytes.

9. **`spec-architect` sharpened a delivery invariant main Claude got half-right.**
   Index-ordering alone would prove order and presence but not *location*, missing
   the ADR-0016 case where context leaks into the translatable user payload. The
   shipped test also asserts `user_messages[0]["content"] == json_payload` exactly.
   That equality is the load-bearing, collision-immune assertion.

## Lessons Promoted to Standards

Classified by `contract-reviewer` at close-out. `CLAUDE.md`'s managed region held 21
bullets before and 21 after — net-zero growth; all three guidance lessons were
folded into existing entries.

| Lesson | Decision | Where it landed |
|---|---|---|
| L1 — `git checkout` / `stash` / `restore` silently destroy uncommitted work, which is the normal state of an in-flight change | promote-to-guidance | Folded into the existing bug-fix-lane recipe bullet, and **generalized** at `spec-architect`'s request beyond falsifiability toggles to ANY temporary revert-and-restore technique — including that bullet's own `git show main:<file> > <file>` recipe. Adds the rule that a reconstructed file is untrusted until a fresh full `cdd-kit test run` covers the current bytes. Evidence: archive.md finding 8. |
| L2 — test evidence must postdate every file it covers; the gate never checks | promote-to-contract | `contracts/ci/ci-gate-contract.md` §Known Validator Gaps (new), 0.6.0 → 0.7.0. Assigns the check to `qa-reviewer` by name until the tool closes it. Evidence: archive.md finding 7; qa-report.md. |
| L3 — a fake that merely ACCEPTS a kwarg is not proof it is delivered | promote-to-guidance | Folded into the existing additive-kwarg bullet as its mirror image: deleting the whole system-channel merge from `translate_json` left all 1326 tests green. Evidence: archive.md finding 5. |
| L4 — index-ordering alone is an insufficient delivery invariant | promote-to-guidance | Folded into the tautological-tests bullet as a newly named form, **order-without-location**: order and presence do not prove the value stayed OUT of a payload it must never enter. Evidence: archive.md finding 9; `agent-log/spec-architect.yml`. |
| L7 — `cdd-kit validate --contracts` does not enforce a paired CHANGELOG entry | promote-to-contract | Same `ci-gate-contract.md` §Known Validator Gaps section and bump. Assigns the check to `contract-reviewer` by name. Evidence: `agent-log/ci-cd-gatekeeper.yml` from the prior change, which was right to overrule `contract-reviewer` on this point. |
| L5 — a live-endpoint probe before designing saved this change | do-not-promote | BR-111 already encodes every testable consequence, pinned by `tests/test_json_translation_prompt.py`. The residual generic principle is already carried by the no-shell-agents entry. |
| L6 — BR-108's substring meta-refusal detector is architecturally the wrong shape | do-not-promote | Elegantly self-blocked: `business-rules.md` §Change Policy — a paragraph promoted at the close of the PREVIOUS change — forbids grafting a mechanism redesign onto a rule already changed twice in the current review cycle, which BR-108 was. Correctly deferred to its own change. |

`cdd-kit validate --contracts` green after the `ci-gate-contract.md` bump; the
absence-tested tokens (`BR-92`, `rescore`) remain absent from `business-rules.md`.

## Follow-up Work

- **Nested-table silent drop (next change).** `docx_processor.py` walks `<w:tbl>`
  and reads only `cell.paragraphs`, never `cell.tables`. Inner-table cells are
  never collected, never translated, and stay as source text in the output.
  Measured on the user's real files: `EN-P-QC1102-D7 量测系统分析(MSA)程序.docx`
  drops 7,359 of 43,134 chars (17.1%); `W-RM0901-G6 机器设备保养及维护管理准则.docx`
  drops 11,172 of 31,169 chars (35.8%). The coordinate cell list makes the fix
  tractable — the old pipe-grid demanded a `num_rows × num_cols` matrix a nested
  table cannot occupy.
- **BR-108's substring meta-refusal detector is architecturally the wrong shape.**
  A refusal is a property of the *whole reply* standing in place of a translation,
  so the detector should match reply-dominant patterns, not substrings that can
  legitimately appear inside a genuine translation. Anchoring is a patch. Its own
  change. (`spec-architect`)
- **Body-envelope batching.** Sending N paragraphs per envelope with an index
  would give cross-paragraph context and divide the call count. Rejected for this
  change by the user; the reasoning is in `change-request.md`.
- **Critique-loop call volume.** Each segment issues 1 translate + 3 critique
  calls. Measured to be conservative (it returns any draft unchanged, 3/3, right or
  wrong), so it is a cost problem, not a correctness one.
- **The residual double LibreOffice `.xls` conversion**, carried from
  `doc-context-sampling-fix`.
- **`test_fallback_logs_warning_on_parse_failure`** (`test_table_context_translation.py`
  ~L432) asserts `levelno >= WARNING` with no `record.name` filter; that WARNING is
  emitted via `logging.getLogger(__name__)` and never reaches `translator.log`.
  Redundant weak assertion, pre-existing, not a coverage hole.
- **Do not let a future refactor reduce `TestTranslateJsonSystemChannelDelivery`**
  to an index-order-only check — the `user content == envelope` equality is what
  carries the ADR-0016 no-leak guarantee.
- **`cdd-kit validate --contracts` does not enforce a paired CHANGELOG entry** for
  a schema-version bump (tested: exit 0 with the entry deleted). A toolchain gap,
  not this change's to fix.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
