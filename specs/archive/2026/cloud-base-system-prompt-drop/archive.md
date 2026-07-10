# Archive — cloud-base-system-prompt-drop

## Change Summary

`OllamaClient.__init__` accepted a `system_prompt` parameter;
`OpenAICompatibleClient.__init__` did not. The orchestrator constructed the cloud
client without one, then read `base_system_prompt = client.system_prompt`, which
for a cloud client was always the class-attribute default `""`. `build_strategy`
therefore composed the scenario appendix, the few-shot block, and the BR-109
`Document context:` preamble on top of an empty base, and the translation
profile's own prompt never reached PANJIT or DeepSeek. For the `semiconductor`
profile that meant its role declaration and terminology/register guidance — the
entire reason to select a profile — were silently inert on the cloud path, which
is the default path. Local Ollama was unaffected. Discovered by intercepting the
real pipeline's outgoing `/v1/chat/completions` bodies while investigating why the
newly-working BR-109 summary did not improve certain header-cell translations.

## Final Behavior

- `OpenAICompatibleClient.__init__` accepts an additive optional
  `system_prompt: Optional[str] = None`, normalized exactly as `OllamaClient` does
  (`self.system_prompt = (system_prompt or "").strip()`).
- The orchestrator passes the caller's prompt at its two cloud-client construction
  sites only — the primary client and the fallback chain.
- The five other construction sites are deliberately left at the default: the
  quality judge (`provider_id="judge-panjit"`), the term extractor
  (`provider_id="panjit-term"`), and three diagnostic provider probes
  (`model=""`). None is translation dispatch.
- Composition order is unchanged and now verified: base prompt → scenario
  appendix → few-shot block → `Document context:` preamble.

Verified live against PANJIT: `base_system_prompt` is 1107 characters (was `""`),
the role declaration appears in the outgoing system message, and the ordering
base < `Document context:` holds.

## Final Contracts Updated

- `contracts/business/business-rules.md` — BR-110 (`llm-client-prompt-parameter-parity`)
  added at `schema-version` 0.28.0, then narrowed to 0.28.1. BR-109's row gained a
  cross-reference sentence stating that population is BR-110's concern, not its own.
- `contracts/CHANGELOG.md` — `[business 0.28.0]` and `[business 0.28.1]` entries.

Evidence: `agent-log/contract-reviewer.yml`, `agent-log/implementation-planner.yml`.

## Final Tests Added / Updated

6 new tests, all asserting on the captured outgoing request payload (the `json=`
kwarg of the mocked `requests.Session.post`), never on `client.system_prompt`:

- `tests/test_orchestrator_context_detection.py` —
  `test_cloud_client_delivers_profile_base_system_prompt_semiconductor` (the RED),
  `test_base_prompt_precedes_document_context_preamble_in_composition` (positional
  ordering via `.index()`, not membership),
  `test_fallback_chain_client_delivers_profile_base_system_prompt` (covers
  `orchestrator.py` L567, which no prior test exercised).
- `tests/test_openai_compatible_client.py` —
  `TestSystemPromptConstruction::test_default_construction_without_system_prompt_stays_empty`
  (anti-vacuity guard for AC-6) and
  `test_constructor_system_prompt_kwarg_delivered_to_outgoing_payload`.
- `tests/test_ollama_client_dynamic_strategy.py` —
  `test_ollama_outgoing_payload_base_system_prompt_unchanged`.

Falsifiability, checked by main Claude rather than taken on the engineer's word:
removing the two cloud pass-throughs turns exactly 3 tests red; removing the
Ollama pass-through turns the pre-existing
`test_local_ollama_context_detection_unchanged` red; restoring returns 64/64 green
across the three touched files. Full suite: 1276 passed, 4 skipped.

Evidence: `agent-log/bug-fix-engineer.yml`, `test-evidence.yml`,
`test-runs/20260709-195033` (pre-fix behavioral RED).

## Final CI/CD Gates

No workflow edit. Per `ci-gates.md`, the merge-blocking `contract-and-fast-tests`
job already runs both `cdd-kit validate --contracts` (catching a stale
schema-version / CHANGELOG mismatch for BR-110) and the blanket
`pytest tests/ -x -q`. Unlike the preceding change there is no silent-skip hazard:
the transport boundary is mocked, so the payload assertions have no network or
binary dependency. No OpenAPI re-export needed — no endpoint or schema surface was
touched. CI run `29017295531`: 8 jobs success, `scheduled-stress-soak` skipped.

## Production Reality Findings

1. **`contract-reviewer` overruled the classifier, correctly.** The classifier
   proposed amending BR-109. The reviewer refused: BR-109's clauses were never
   violated by this defect — the empty string was still merged ahead of the
   per-segment BR-78 `system_context`, still delivered via the system channel,
   never leaked into the translatable user payload. The *input* to BR-109's
   mechanism was wrong, not the mechanism. It also noted BR-109 had been amended
   twice in two days (0.27.0 → 0.27.1 → 0.27.2) and that a fourth graft onto one
   overloaded rule would degrade what its single test-pointer column can mean.
   BR-110 states the durable invariant instead — constructor prompt-parameter
   parity across sibling LLM client classes — which prevents the *next* provider
   client from repeating the bug regardless of whether it ever touches
   document-context summaries.

2. **`implementation-planner` caught that BR-110, as first written, contradicted
   itself** — and the wrong text was main Claude's, written from the reviewer's
   proposal. The rule's opening clause is conditional ("instantiated by a caller
   that supplies a base `system_prompt`") but its second sentence enumerated all
   seven construction sites as obligated. Verified against live source: the
   quality judge, the term extractor, and the diagnostic probes are not
   translation dispatch and must not receive the translation profile's prompt.
   The rule was narrowed to 0.28.1 **before any code was written**. This is the
   second consecutive change in which the first shell-capable agent corrected a
   specification authored by the human/main Claude rather than by another agent.

3. **The classifier's construction-site inventory was wrong in both directions.**
   It named `services/model_router.py` (which contains no reference to the class
   at all) and omitted `services/term_extractor.py` (which constructs one at
   L570). Main Claude greped the tree before writing the manifest and corrected
   both. The same grep found 39 constructions across six test files, three of
   which the classifier's draft manifest did not list.

4. **The additive-optional-kwarg design meant zero test doubles broke.** The
   documented repo hazard (adding a parameter to a shared seam breaks doubles
   mirroring the signature) did not materialize because the parameter has a
   default and no existing construction passes it. `test-strategist` recognized
   this and added an explicit default-omitted assertion so that AC-6 ("39 existing
   constructions needed no edit") is proven rather than assumed by silence.

5. **The RED had to be routed through `process_files()`, not the constructor.**
   A test constructing `OpenAICompatibleClient(system_prompt=…)` against unfixed
   source raises `TypeError` — a collection-adjacent failure, not a faithful
   behavioral RED. `test-strategist` designed the reproduction to run through the
   real `process_files()` → `build_strategy()` → `translate_once()` seam, which
   already accepted `system_prompt=`/`profile_id=`/`provider_id=`, so it fails on
   a missing-role-declaration assertion about the outgoing payload.

6. **`qa-reviewer` flagged a coverage gap that turned out not to exist.** It
   observed that the new Ollama regression test constructs its client directly and
   so would not go red if the orchestrator's Ollama pass-through were removed.
   Main Claude tested this: deleting that line turns the pre-existing
   `test_local_ollama_context_detection_unchanged` red across the full suite. AC-4
   is guarded, by a different test than the one QA inspected.

7. **The fix does not improve the translation that led to its discovery.** A
   deterministic 5×-repeated live trial shows `制作日期` renders as
   `Ngày sản xuất` with the profile prompt, with the document summary, and with
   both. A four-character header cell translated in isolation lacks the row
   context that disambiguates it; the profile prompt is not a substitute for that.
   What this change buys is that the semiconductor terminology discipline now
   actually reaches the model.

## Lessons Promoted to Standards

Classified by `contract-reviewer` at close-out. `CLAUDE.md`'s managed region held
21 bullets before and 21 after — net-zero growth; the two guidance lessons were
folded into one existing entry.

| Lesson | Decision | Where it landed |
|---|---|---|
| L1 — a newly-written contract rule can over-reach, and the first shell-capable agent is the one who catches it | promote-to-guidance | Folded into the existing `CLAUDE.md` no-shell-agents entry, whose "duty extends to..." clause now covers a self-contradictory acceptance criterion **or business rule** authored by the human/main Claude, citing BR-110's 0.28.0 → 0.28.1 narrowing. Evidence: archive.md finding 2; `agent-log/implementation-planner.yml`. |
| L2 — a defect in the INPUT to a rule's mechanism is not a violation of that rule | promote-to-contract | New paragraph in `contracts/business/business-rules.md` `## Change Policy`; `schema-version` 0.28.1 → 0.29.0 plus a `[business 0.29.0]` CHANGELOG entry. Mirrors the `Deployment Sync Policy` precedent in `env-contract.md`: a meta-policy governing how the contract is maintained, not a rule row. Evidence: archive.md finding 1; `agent-log/contract-reviewer.yml`. |
| L3 — the classifier's construction-site inventory was wrong in both directions | promote-to-guidance | Folded into the same entry as L1: it now names `change-classifier` among the no-shell agents and records that an inventory has been wrong in both directions, with "grep before writing the manifest" as the duty. Evidence: archive.md finding 3. |
| L4 — a bug-fix RED must route through an entry point that already accepts the new parameter | do-not-promote | Already covered: the existing bug-fix-lane entry requires a behavioral assertion failure, "not a collection/import error". A `TypeError` from a changed constructor signature is the same category. |
| L5 — an additive optional kwarg with a default broke zero of the 39 test doubles | do-not-promote | A counter-example that confirms the existing kwarg-breaks-doubles entry's own logic rather than revealing a gap. Qualifying it would add words to state something already implied. |
| L6 — the profile prompt does not fix `制作日期` | do-not-promote | A single-trial product-quality observation, not a durable contract fact. Stays in finding 7; it is part of the empirical case for the JSON structured-I/O change. |

`cdd-kit validate --contracts` green after the Change Policy addition; the
absence-tested tokens (`BR-92`, `rescore`) remain absent from `business-rules.md`.

## Follow-up Work

- **xlsx table-batch phantom-column defect**: `ws.max_column` is 257 against 47
  real cells, so `table_serializer.parse()` can never match the demanded shape,
  always returns `None`, and each sheet wastes one large LLM call before the BR-82
  per-cell fallback. Deferred to the JSON structured-I/O change, where the
  pipe-grid round-trip disappears.
- **Critique-loop call volume**: each segment issues 1 translate + 3 critique
  calls. Observed while intercepting payloads; not investigated.
- **Residual double conversion** of `.xls` (sampler plus the untouched
  `xlsx_processor`), carried over from `doc-context-sampling-fix`.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
