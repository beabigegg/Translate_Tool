---
change-id: json-structured-translation-io
schema-version: 0.1.0
last-changed: 2026-07-10
---

# Implementation Plan: json-structured-translation-io

## Objective
Move both LLM translation paths (whole-table and body/paragraph) from
line-shaped wire formats to JSON envelopes, delivered through a new
system-prompt-preserving client seam, with a shared validator that falls back to
the existing per-cell / plain-text path (never failing the job) and logs one INFO
line per fallback through the job `log(...)` callback. Gate the whole mechanism
behind `JSON_STRUCTURED_TRANSLATION_ENABLED` (default true). Delivers change-request
point 4 (JSON I/O) and subsumes the phantom-column defect. Contracts are already on
disk (data-shape 0.18.0, business-rules 0.30.0, env 0.19.0) and authoritative.

## Live-source verification performed (first shell-capable agent)
Every seam, symbol, signature and consumer below was read from live source, not
pattern-matched. Confirmations:
- Five `serialize()`/`parse()` call sites confirmed at the exact lines main Claude
  recorded: `xlsx_processor.py` L206/L213, `pptx_processor.py` L357/L364,
  `docx_processor.py` L846/L853, `pdf_processor.py` L173/L179 (function
  `_translate_pdf_tables_with_context`), `translation_service.py` L901/L908
  (the `TableStructure` cell-batch path).
- Both clients' `_build_table_translate_prompt` are `@staticmethod`s that BUILD a
  string only; the caller then passes it into `translate_once(prompt, tgt, src)`.
  Confirmed the double-instruction: `openai_compatible_client.translate_once`
  L323-326 prepends `"Translate the following text from {src} to {tgt}. Output only
  the translation, no explanations.\n\n{text}"` around whatever `text` it is given —
  so today's table prompt is wrapped twice. This is the empty-`content` shape from
  the probe and the new seam MUST NOT reproduce it.
- `OpenAICompatibleClient._post_completion` (L179-237) already returns `ok=False`
  on empty `content` (L223-232) — the "empty content surfaces as ok=False" the
  design relies on. It has NO `response_format` parameter today.
- `translate_once` system merge order confirmed: `openai_compatible_client.py`
  L327-328 merges `self.system_prompt` then `system_context` into one leading
  system message; the new seam reuses this exact merge (BR-109/BR-110/BR-78 parity).
- `complete()` exists on both clients (openai L336, ollama L900) and is
  system-prompt-free — correctly rejected for translation.
- `LLMClient` Protocol has exactly five methods (`base_llm_client.py` L14-72);
  `translate_json` stays OFF it (design Protocol-surface decision, option b).
- `text_utils.is_numeric_cell` (L23), `should_translate` (L75),
  `is_meta_refusal` (L157) all exist.
- `log(...)` job callback is in scope at every one of the five table sites
  (xlsx L241, pptx L394, docx L925, pdf_processor L207, translation_service L867/896)
  and in `translate_merged_paragraphs` (`log` param, L145) — so the INFO fallback
  line can be emitted at every caller. `table_serializer.py` is a pure utility with
  no logger; it MUST NOT emit — the caller emits (see IP-9).
- Test doubles confirmed: `_StubTableClient` (test_pdf_layout_table_fixes.py L342)
  and `_FailingClient` (L520) both implement `_build_table_translate_prompt` +
  `translate_once`; both drive `_translate_pdf_tables_with_context`.
- `config.QE_ENABLED`/`CRITIQUE_LOOP_ENABLED` are module-level constants computed
  from `os.environ` at import (config.py L141/L146).

## Flag-OFF semantics — DECIDED: Resolution A (coordinator, with live pipe-grid probe)
The earlier flag-OFF contradiction (env-contract "byte-for-byte" vs AC-7 "no old-grid
consumer remains") is resolved as **Resolution A: retain the legacy pipe-grid path,
frozen, reachable only when `JSON_STRUCTURED_TRANSLATION_ENABLED=0`.** The coordinator
drove the real PANJIT endpoint through the pipe-grid path and proved it is not dead:
a clean 2×2 grid round-trips and delivers the same row-context win as JSON
(`制作日期` → `Ngày lập`); a 1×2 grid round-trips; the 1×1 fails only on
leading/trailing pipes. The pipe-grid never succeeds in production ONLY because
`xlsx_processor` feeds it a 9×257 phantom grid so `parse()` always returns `None`.
Deleting it (the earlier Resolution R) would make flag-OFF a **degradation** — clean
tables would drop to context-less per-cell — defeating the kill switch. Decision is
final; do not re-litigate.

Corrections already applied on disk by the coordinator (do NOT re-edit): AC-7 →
"No consumer of the old grid format remains **on the flag-ON path**" (probe evidence
inline); data-shape consumers table (L501) → legacy `serialize()`/`parse()` RETAINED,
frozen, reachable only at flag=0, `validate --contracts` green; ADR-0017 Decision →
seam on both concrete clients and OFF the five-method Protocol (matches design.md
option b).

**What Resolution A means for this plan:**
- KEEP the legacy pipe-grid `table_serializer.serialize(cells)` /
  `parse(text,num_rows,num_cols)` — frozen, unchanged. ADD the JSON functions under
  NEW names (`serialize_json` / `parse_json`); the legacy names are not reused and no
  new caller uses them.
- KEEP both clients' `_build_table_translate_prompt` staticmethods — frozen, used only
  by the flag-OFF path. ADD the new `translate_json` seam alongside.
- Each of the five table sites gets an `if config.JSON_STRUCTURED_TRANSLATION_ENABLED:`
  (new JSON block) `else:` (the retained legacy pipe-grid block, unchanged) branch.
  The body path gets the same branch once, inside `translate_merged_paragraphs`.
- Accepted cost: two live table wire paths to maintain and test (see §Resolution A
  cost).

## Execution Scope

### In Scope
- New shared module `app/backend/utils/json_translation.py`: pinned instruction
  phrasing (BR-111), body envelope build/parse+validate (BR-112), table reply
  validator helper.
- ADD JSON build/parse (`serialize_json` / `parse_json`) to
  `app/backend/utils/table_serializer.py` alongside the RETAINED, frozen legacy
  pipe-grid `serialize`/`parse` (data-shape §Table Serialization Wire Format; BR-79/BR-83).
- New `translate_json` seam on BOTH `OllamaClient` and `OpenAICompatibleClient`
  (BR-111); OFF the Protocol; RETAIN both `_build_table_translate_prompt` (frozen,
  flag-OFF only).
- Flag-branch the five table call sites: flag-ON JSON content-cells-only path (kills
  phantom columns); flag-OFF retained legacy pipe-grid block, unchanged.
- Body path in `translate_merged_paragraphs`: flag-ON JSON envelope with plain-text
  fallback; flag-OFF plain-text `translate_once` (retained); BR-108 guard on the final
  written value in every case.
- `JSON_STRUCTURED_TRANSLATION_ENABLED` read in `config.py`.
- INFO fallback line via `log(...)` at every fallback site.
- Update test doubles (`_StubTableClient`, `_FailingClient`); add/extend tests per
  test-plan.md.

### Out of Scope (do not touch, do not let creep in)
- Critique-loop call volume (change-request §Non-goals).
- Residual double LibreOffice `.xls` conversion.
- Body-envelope batching / N-segment index envelopes (rejected; one segment per call).
- Nested-table collection in `docx_processor.py` (next change; the measured
  17.1%/35.8% silent text loss stays as-is here).
- `base_llm_client.py` and `tests/test_llm_client_protocol.py` — unmodified.
- BR-107 (body passthrough) and BR-68 (numeric passthrough) behavior — preserved.
- Contract files (data-shape/business/env/schema/.env.example.template) — already
  written and Resolution-A-correct; do NOT re-edit. (The only open contract item is
  the env-contract "restart required" column, resolved below — contract-reviewer's
  edit if any, not backend-engineer's.)

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `JSON_STRUCTURED_TRANSLATION_ENABLED` module constant in `config.py` (define like QE_ENABLED L141). Consumers MUST read `config.JSON_STRUCTURED_TRANSLATION_ENABLED` (module-attribute access at call time), NEVER `from config import ...` (that is the CRITIQUE_LOOP_ENABLED import-bound pattern, which a `config` monkeypatch cannot flip). Attribute access lets runtime behavior tests toggle via `monkeypatch.setattr(config, ...)`; test_env_contract's default test uses `importlib.reload(config)` (mirror the QE_ENABLED test). | backend-engineer |
| IP-2 | shared module | Create `app/backend/utils/json_translation.py`: pinned framing constants + `build_body_payload`, `parse_body_reply`, and the table instruction framing used by `build_table_payload`. See §File-Level Plan for signatures. | backend-engineer |
| IP-3 | client seam | Add `translate_json` to both concrete clients (BR-111); reuse each `translate_once`'s system-channel merge but frame the user payload with the shared JSON phrasing, NOT the "Output only the translation" wrapper. RETAIN `_build_table_translate_prompt` on both (frozen, flag-OFF only). Do NOT modify `base_llm_client.py`. | backend-engineer |
| IP-4 | table serializer | ADD `serialize_json`/`parse_json` (JSON coordinate cell-list build + coordinate-remap parse with reject/echoed-whole-grid logic) to `table_serializer.py`. RETAIN the legacy pipe-grid `serialize`/`parse` unchanged and frozen (data-shape §Table Serialization Wire Format L501; BR-79/BR-82/BR-83). | backend-engineer |
| IP-5 | table callers x4 | `xlsx/pptx/docx/pdf_processor`: wrap each existing block in `if config.JSON_STRUCTURED_TRANSLATION_ENABLED:` [new JSON block: content-bearing non-numeric cells at ORIGINAL `(row,col)`, `serialize_json`, `translate_json`, `parse_json`, per-cell/flatten fallback on reject] `else:` [the retained legacy pipe-grid block, unchanged]. | backend-engineer |
| IP-6 | pdf cell-batch | `translation_service.py` cell-batch path: same flag-branch; flag-ON serializes only `translatable_cells` via `serialize_json` + `translate_json` + `parse_json` + BR-82 fallback; flag-OFF keeps the existing `serialize`/`_build_table_translate_prompt`/`parse` block. | backend-engineer |
| IP-7 | body path | `translate_merged_paragraphs`: after BR-107 guard, `if config.JSON_STRUCTURED_TRANSLATION_ENABLED:` send `{"text":...}` via `translate_json`, parse `{"translation":...}`, fall back to `translate_once` on any trigger; `else:` call `translate_once` (retained legacy). BR-108 `is_meta_refusal` applies to the FINAL written value in every branch. | backend-engineer |
| IP-8 | flag-OFF wiring | The `else:` branch at each of the five table sites is the RETAINED legacy pipe-grid block (true revert, not a per-cell degradation — coordinator's probe); the body `else:` is plain-text `translate_once`. Branch lives PER CALL SITE for tables (each processor builds cells differently — no shared table entry point) and ONCE for body. `config.JSON_STRUCTURED_TRANSLATION_ENABLED` is readable at all six points (each module does `from app.backend import config` and reads the attribute). | backend-engineer |
| IP-9 | observability | At every flag-ON fallback site emit ONE INFO line via the in-scope `log(...)` callback (reaches `TranslateTool` logger); keep existing `logger.warning`. Parser returns a reason string for the message. (Flag-OFF legacy blocks keep their current logging unchanged.) | backend-engineer |
| IP-10 | test doubles | `_StubTableClient` + `_FailingClient`: KEEP `_build_table_translate_prompt` (drives the flag-OFF path in the existing PDF tests) AND ADD `translate_json` (echo cells JSON translated / return garbage respectively); keep `translate_once` for the body path. | backend-engineer / e2e-resilience-engineer |
| IP-11 | tests | Add `test_json_translation_prompt.py`, `test_json_translation_body.py`; EXTEND `test_table_serialization.py` (keep legacy pipe-grid cases for the frozen fns, ADD `serialize_json`/`parse_json` coordinate cases); parameterise `test_table_context_translation.py` over the flag (do NOT duplicate); extend `test_nontranslatable_segment_guard.py`, `test_pdf_layout_table_fixes.py`, `test_env_contract.py`. See §Resolution A cost. | test-strategist / e2e-resilience-engineer / backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Key Decisions (new seam; shared pinned builder; Protocol option b; no native JSON mode; coordinate JSON; fallback trigger set; keep BR-108; kill-switch) | binding implementation constraints |
| business-rules.md | BR-79, BR-80, BR-82, BR-83, BR-107, BR-108, BR-111, BR-112; BR-68 preserved | seam/format/fallback/log rules |
| data-shape-contract.md | §Table Serialization Wire Format (request/response envelope, coordinate remap, reject/echoed rules, round-trip, consumers table) | serializer build/parse conformance |
| env-contract.md | `JSON_STRUCTURED_TRANSLATION_ENABLED` row (0.19.0) | flag semantics; caching column resolved in §Contract Updates |
| ADR-0017 | Decision + Consequences invariants | non-reversible invariants |
| test-plan.md | AC->test map; New/Extended test files; Test Update Contract; Execution Ladder; Notes | tests to write/run + assertion discipline |
| ci-gates.md | Required Gates table; env-sync step; tier-floor-override | verification commands |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/config.py` | edit | add `JSON_STRUCTURED_TRANSLATION_ENABLED: bool = os.environ.get("JSON_STRUCTURED_TRANSLATION_ENABLED","1").lower() in ("1","true","yes")` near L146. Definition mirrors QE_ENABLED; consumers read it via attribute access (IP-1). |
| `app/backend/utils/json_translation.py` | create | `build_body_payload(text, src, tgt) -> str` (frames `{"text": text}` with pinned `Return: {"translation": <your translation>}`); `build_table_payload(cells, src, tgt) -> str` (frames the `{"cells":[...]}` JSON from `table_serializer.serialize_json` with `Return: {"cells": [{"row": R, "col": C, "translation": <text>}]}`); `parse_body_reply(content, source_text) -> tuple[str\|None, str]` returns (translation, "") or (None, reason) on unparseable / missing-or-wrong-typed `translation` / `translation == source_text`. Phrasing constants live here, pinned by test. MUST NOT import a logger for emission. |
| `app/backend/utils/table_serializer.py` | edit (add, retain legacy) | ADD `serialize_json(cells) -> str`: `json.dumps({"cells":[{"row":c.row,"col":c.col,"text":c.content} ...]})`, ONLY content-bearing (`content!=""`) non-numeric (`not c.is_numeric`) cells, ORIGINAL coords, never renumbered. ADD `parse_json(content, sent_cells: dict[(int,int),str]) -> tuple[dict[(int,int),str]\|None, str]`: parse JSON, require `cells` list of `{row:int,col:int,translation:str}`; reject (None+reason) on unparseable / missing key / non-int coord / any sent coord absent; ignore extra coords; echoed-whole-grid (every present sent coord's translation == its source) -> reject. RETAIN legacy `serialize`/`parse` unchanged and frozen. Update docstring to note the flag-gated dual format + ADR-0017. |
| `app/backend/clients/openai_compatible_client.py` | edit | RETAIN `_build_table_translate_prompt` (L272-293) frozen (flag-OFF only); add `translate_json(self, user_payload, system_context=None, cancel_event=None)`: `parts=[p for p in ((self.system_prompt or "").strip(),(system_context or "").strip()) if p]; merged="\n\n".join(parts) or None; return self._post_completion(user_payload, cancel_event=cancel_event, system_context=merged)`. Do NOT re-wrap with translate framing. `response_format` NOT sent (inert per Finding 3; contract says MAY, so omitting is conformant). |
| `app/backend/clients/ollama_client.py` | edit | RETAIN `_build_table_translate_prompt` (L645-665) frozen; add `translate_json` mirroring OpenAI's contract: base payload via `_build_no_system_payload(user_payload)` then inject merged `self.system_prompt`+`system_context` into `payload["system"]` (mirror translate_once L460-466), `return self._call_ollama(payload)`. |
| `app/backend/processors/xlsx_processor.py` | edit | wrap L196-246 in the flag branch. Flag-ON: content-cells list from `cells_by_pos` (exclude empty; exclude numeric via `is_numeric_cell`), coords `(r0,c0)`, `serialize_json` + `translate_json` + `table_serializer.parse_json(content, sent_cells)`; assign `tmap[(tgt,src_text,c0)] = mapping[(r0,c0)]`; BR-82 per-cell fallback on reject + `log(...)` INFO. Flag-OFF: the existing L196-246 block unchanged. |
| `app/backend/processors/pptx_processor.py` | edit | same flag branch at L347-399; flag-ON coords `(seg[3],seg[4])`, `final_tmap[(tgt,txt,c)] = mapping[(r,c)]`, real `log(...)` INFO (module `log` in scope L394); flag-OFF the existing block unchanged. |
| `app/backend/processors/docx_processor.py` | edit | same flag branch at L836-870+; flag-ON content-cells only from `t_segs`, `final_tmap[(tgt,s.text,c)] = mapping[(r,c)]`, keep the stop-flag/should_translate fallback + `log(...)` INFO; flag-OFF the existing block unchanged. |
| `app/backend/processors/pdf_processor.py` | edit | `_translate_pdf_tables_with_context` L140-208: flag branch. Flag-ON: content-cells from `by_cell` (skip empty joins), coords `(r,c)`, `serialize_json` + `translate_json` + `parse_json`; on reject `continue` (existing flatten fallback) + `log(...)` INFO. Flag-OFF: existing block unchanged. |
| `app/backend/services/translation_service.py` | edit | cell-batch path L898-935: flag branch. Flag-ON: `serialize_json(translatable_cells)`, `sent_cells={(c.row,c.col):c.content}`, `translate_json` + `parse_json`; assign per-`(r,c)`; BR-82 per-cell fallback + `log(...)` INFO (in scope L867). Flag-OFF: existing `serialize`/`_build_table_translate_prompt`/`parse` block unchanged. |
| `app/backend/utils/translation_helpers.py` | edit | `translate_merged_paragraphs` L196-209: `if config.JSON_STRUCTURED_TRANSLATION_ENABLED:` build `json_translation.build_body_payload`, `client.translate_json(payload, system_context=system_ctx)`, `parse_body_reply`; fall back to `translate_once(text,tgt,src_lang,system_context=system_ctx)` on trigger with `log(...)` INFO. `else:` the existing `translate_once(...)` call unchanged. BR-108 `is_meta_refusal` on the final value in both branches (keep "skip on_segment_done for fallback"). `config` already imported at L8 — read `config.JSON_STRUCTURED_TRANSLATION_ENABLED`. |
| `tests/*` | create/edit | per test-plan.md §New/Extended/Update Contract (IP-11). |

## Contract Updates
- API: none (no endpoint surface).
- CSS/UI: none.
- Env: `JSON_STRUCTURED_TRANSLATION_ENABLED` already on disk in env-contract 0.19.0,
  `.env.example.template`, `env.schema.json` (ci-gates verified). **Caching / "restart
  required" column — RESOLVED with a live-source finding:** `config.py` CACHES
  `CRITIQUE_LOOP_ENABLED` at module load (L146, `os.environ.get(...)` evaluated once at
  import) — it is NOT read inline per call — and consumers bind it via `from
  app.backend.config import CRITIQUE_LOOP_ENABLED` (e.g. translation_service.py L12), so
  its value is frozen at first import. `JSON_STRUCTURED_TRANSLATION_ENABLED` is defined
  the SAME way (module constant, os.environ read once at import), so an operator env
  change takes effect only on process restart. The one deliberate divergence: consumers
  READ it as `config.JSON_STRUCTURED_TRANSLATION_ENABLED` (attribute access), not
  `from config import`, purely so runtime tests can `monkeypatch.setattr(config, ...)`.
  Consequence for the contract column: the value is module-load-cached (restart needed
  to change the env), the SAME as every other application-team boolean flag in the table
  (QE_ENABLED, CRITIQUE_LOOP_ENABLED, DYNAMIC_SCENARIO_STRATEGY_ENABLED), all of which
  the table marks "no". Recommendation to contract-reviewer: keep the current "no" for
  table-wide consistency (the flag is set-at-deploy config; the revert action is
  flip-env + restart the backend process, no rebuild/redeploy). It is NOT read inline
  from `os.environ` each call, so if the column is meant strictly as "changeable without
  any restart," that is false for this flag and for its three siblings alike — a
  table-wide wording question, not specific to this change. No code change is required
  either way.
- Data shape: already written (0.18.0) — implementation must CONFORM to
  §Table Serialization Wire Format; do not re-edit.
- Business logic: already written (0.30.0) BR-79/80/82/83/107/108/111/112 — conform.
- CI/CD: env-sync grep step already added (ci-gates.md); no further gate edits.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_table_serialization.py::TestSerializeContentCellsOnly::test_47_content_cells_against_257_phantom_columns_no_grid_shape | serialize emits exactly 47 cell objects, no grid shape |
| AC-1 | tests/test_table_context_translation.py::TestPhantomColumnRegression::test_xlsx_257_col_sheet_completes_without_fallback | captured payload holds 47 cells; no per-cell fallback fires |
| AC-2 | tests/test_table_serialization.py::TestParseCoordinateRemap::test_valid_reply_restores_translations_by_row_col | parse remaps by (row,col), not position |
| AC-2 | tests/test_table_context_translation.py::TestJsonTableRoundTrip::test_row_neighbor_context_delivered_in_outgoing_payload | row neighbors present in captured outgoing payload |
| AC-3 | tests/test_json_translation_body.py::TestBodyEnvelope::test_body_payload_sends_text_key_parses_translation_key | `{"text":...}` out, `{"translation":...}` parsed |
| AC-3 | tests/test_json_translation_body.py::TestBodyEnvelope::test_schema_rejects_missing_translation_key | reject -> fallback |
| AC-4 table | tests/test_table_context_translation.py::TestFallbackBehavior::test_unparseable_json_falls_back_to_per_cell_batch | per-cell BR-82 runs; job completes |
| AC-4 body | tests/test_json_translation_body.py::TestBodyFallback::test_unparseable_json_falls_back_to_translate_once | plain-text call fires |
| AC-4 never-fail | tests/test_json_translation_body.py::TestBodyFallback::test_job_completes_normally_on_corrupted_json | no exception, result returned |
| AC-5 table | tests/test_table_context_translation.py::TestFallbackLogging::test_fallback_emits_info_via_translatetool_logger | INFO record with `record.name == "TranslateTool"` |
| AC-5 body | tests/test_json_translation_body.py::TestBodyFallback::test_fallback_emits_info_via_translatetool_logger | same, body path |
| AC-6 | tests/test_table_recognizer.py::TestNumericPassthroughWiring (extend) | numeric cell never in JSON payload |
| AC-6 | tests/test_nontranslatable_segment_guard.py (extend) | BR-107 passthrough bypasses envelope; BR-108 catches meta-in-JSON |
| AC-7 | tests/test_table_context_translation.py::TestOneCallPerTableOffice + ::TestPdfTableCellSerialization (extend) | all four office/PDF sites drive the seam |
| AC-7 | tests/test_json_translation_prompt.py::TestSharedBuilderConsumers::test_both_prompt_builders_delegate_to_shared_module | both clients expose `translate_json`; phrasing from shared module |
| AC-8 | `cdd-kit validate --contracts` | exit 0 |

Required phases (test-plan §Execution Ladder): collect, targeted, changed-area,
contract; then full at gate. Generate evidence with `cdd-kit test run --phase <p>`.
Scope by node-id only; never widen to `test_pdf_*` globs or QE/COMET files
(documented env artifacts). QE-touching runs go through
`conda run -n translate-tool cdd-kit test run ...`.

## Resolution A cost (two live table wire paths)
Accepted, per the coordinator's decision. Concretely:
- `table_serializer.py` carries BOTH the frozen legacy pipe-grid `serialize`/`parse`
  and the new `serialize_json`/`parse_json`; both clients carry both
  `_build_table_translate_prompt` (frozen) and `translate_json`.
- Five table sites + the body site each carry an `if/else` flag branch.
- **Tests: parameterise over the flag, do NOT duplicate.** In
  `test_table_context_translation.py`, drive `TestOneCallPerTableOffice`,
  `TestPdfTableCellSerialization`, `TestPromptBuilder` and `TestFallbackBehavior`
  with a flag fixture (`@pytest.mark.parametrize("json_enabled",[True,False])` +
  `monkeypatch.setattr(config,"JSON_STRUCTURED_TRANSLATION_ENABLED",json_enabled)`)
  so the SAME assertions run against both wire paths; the JSON-specific cases
  (phantom-column, coordinate remap, echoed-source) run only under `json_enabled=True`
  and the pipe-grid shape-echo cases only under `False`.
- `test_table_serialization.py`: KEEP the existing legacy pipe-grid `serialize`/`parse`
  shape cases for the frozen functions; ADD separate `serialize_json`/`parse_json`
  coordinate cases. This DIVERGES from test-plan.md §Test Update Contract line for
  `test_table_serialization.py` (which said "wire format moves from positional
  pipe-grid to coordinate JSON" i.e. replace) — under Resolution A the legacy cases
  are retained, not replaced. Flag to test-strategist to correct that one row of the
  Test Update Contract.
- A flag-OFF integration case must prove the legacy pipe-grid path still round-trips a
  clean table (the coordinator's 2×2 evidence), so the kill switch is verified as a
  true revert.

## Suggested Work Ordering (suite never left broken mid-way)
Land as one coherent change; within it:
1. IP-1 config flag; IP-2 `json_translation.py`; IP-4 ADD `serialize_json`/`parse_json`
   to `table_serializer.py` (legacy `serialize`/`parse` untouched).
2. IP-3 add `translate_json` seam on both clients (retain `_build_table_translate_prompt`).
3. IP-11 write the two new test files + ADD the `serialize_json`/`parse_json` cases to
   `test_table_serialization.py` (RED — the bounded-ladder RED target; the legacy cases
   stay green throughout; run `collect` then `targeted`).
4. IP-5/IP-6/IP-7/IP-8 add the flag branch at all five table callers + body path
   (imports resolve because seam+serializer already exist; the `else:` blocks are the
   unchanged legacy code, so nothing breaks mid-way).
5. IP-10 update `_StubTableClient`/`_FailingClient` (keep old method, add `translate_json`);
   IP-11 parameterise `test_table_context_translation.py` over the flag and extend
   `test_nontranslatable_segment_guard.py`, `test_pdf_layout_table_fixes.py`,
   `test_env_contract.py`. Run targeted -> changed-area -> contract -> full green.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into code
  comments; reference by BR/AC/section id.
- Flag-OFF semantics are DECIDED (Resolution A): the `else:` branches are the retained,
  frozen legacy pipe-grid (tables) / plain-text `translate_once` (body). No sign-off
  pending; implement both branches in this change.
- Assert every payload at the captured transport boundary, never on
  `client.system_prompt` or any internal attribute. Filter every fallback/log
  assertion on `record.name == "TranslateTool"`. Assert WHICH echoed condition fired
  (whole-grid vs single-cell), never a changed-cell count (test-plan §Notes).
- If any required file, behavior, contract, or test is missing, stop and report
  `blocked`. Keep within this file-level plan unless a Context Expansion Request is
  approved.

## Known Risks
- **Two live table wire paths (Resolution A)** — the frozen legacy pipe-grid and the
  new JSON path both ship. Risk is drift/rot in the frozen path; mitigate by
  parameterising existing table tests over the flag (see §Resolution A cost), not by
  duplicating them. No new caller may use the legacy `serialize`/`parse` or
  `_build_table_translate_prompt` (data-shape L501).
- **Echoed-source granularity** — table trigger is whole-grid-unchanged only; a
  single unchanged cell (proper noun / product code / number) is legitimate and MUST
  NOT trigger. Body trigger is `translation == text`. Get the boundary right in the
  parser, not the caller.
- **Office numeric exclusion** — BR-79 requires non-numeric only; the office proxies
  historically sent numeric cells (`is_numeric=False` default). Excluding them means
  numeric cells get no tmap entry and must correctly stay = source (passthrough,
  BR-68) at restore; verify each office restore path leaves absent cells as source.
- **Per-model non-uniformity (Finding 5)** — pinned phrasing validated on 3 models;
  a future routed model could need different framing. Universal fallback caps blast
  radius; a silent quality dip on well-formed JSON is only caught by the kill-switch,
  not by any gate (ci-gates §Accepted risk).
- **Shared-seam test-double breakage** — grep the WHOLE `tests/` tree for any other
  fake implementing `_build_table_translate_prompt` or a fixed-arg `translate_once`
  before marking done (the two confirmed are in `test_pdf_layout_table_fixes.py`, but
  this repo has repeatedly hidden such fakes in unexpected files).
- **ADR-0017 wording** — corrected on disk by the coordinator; the seam is OFF the
  five-method Protocol (design.md option b). No action.
- `.cdd/code-map.yml` currency was not independently reverified, but every cited line
  was read from live source above.
