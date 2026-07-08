# Change Classification

## Change Types
- primary: bug-fix, business-logic-change (BR-78 in `contracts/business/business-rules.md` must change)
- secondary: llm-client-interface-change (adds a system-channel context seam across the client protocol), prompt-assembly-change

## Lane
- bug-fix

## Bug Symptom Type
- data (translation output content is wrong: segment N's translation contains the verbatim text of preceding segments)

## Diagnostic Only
- no (the first correct step is a behavior fix; deterministic repro already exists)

## Bug Evidence Required
- symptom: translating one 8D segment ("3、此失效模式…") returns Vietnamese for points 1 + 2 + 3 — preceding segments bled into the output.
- expected: only the target segment N is translated; the to-translate user payload for segment N contains only segment N.
- actual: `build_context_prefix` (BR-78) prepends the previous `CONTEXT_WINDOW_SEGMENTS` raw source segments inline; `translate_merged_paragraphs` glues that prefix onto segment N before `client.translate_once`, so the "translate the following text" wrapper translates the "do not translate" context too.
- reproduction: deterministic, no live LLM — `build_context_prefix` + real 8D segments + `CONTEXT_WINDOW_SEGMENTS=2` yields a `prompted_text` whose translatable body contains points 1 and 2 verbatim. bug-fix-engineer records per ADR 0006 §6/§7.
- regression: RED before / GREEN after with the real 8D segments fixture; existing context/few-shot prompt tests remain green.

## Risk Level
- medium

## Impact Radius
- cross-module (the translation prompt-assembly path + the shared LLM client protocol feed every processor's cloud translation output)

## Tier
- 2

## Architecture Review Required
- yes
- reason: the fix introduces a "context via system channel" seam that changes the shared LLM client protocol (`base_llm_client` + `openai_compatible_client` + `ollama_client`) — a module-boundary + data-flow decision with a real choice between "delete context (smallest safe fix)" vs "route context through the system message." `spec-architect` records that decision in `design.md` before `implementation-planner` runs.

## Required Artifacts
The 7 always-required: change-request, change-classification, implementation-plan, test-plan, ci-gates, tasks, context-manifest.

## Optional Artifacts (default: no)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current behavior + root cause fully traced in change-request + Bug Evidence |
| proposal.md | no | no user-facing product decision beyond the design seam |
| spec.md | no | behavior decision fits in design.md + implementation-plan.md |
| design.md | yes | Architecture Review Required = yes; system-channel context seam across the client protocol |
| qa-report.md | no | routine pass/fail → agent-log/qa-reviewer.yml; upgrade only on blocking/approved-with-risk |
| regression-report.md | no | regression evidence in agent-log/bug-fix-engineer.yml + test-plan |
| visual-review-report.md | no | no UI/visual surface |
| monkey-test-report.md | no | n/a |
| stress-soak-report.md | no | no high-load/queue/long-running behavior |

## Required Contracts
- API: none. CSS/UI: none. Env: none (`CONTEXT_WINDOW_SEGMENTS`=2 / `CONTEXT_MAX_CHARS`=300 keep their values). Data shape: none. CI/CD: none.
- Business logic: yes — `contracts/business/business-rules.md` BR-78 text update: preceding context segments are no longer injected into the translatable payload (context, if kept, moves to the system channel / is structurally separated).

## Required Tests
- unit: yes — `build_context_prefix` output and `translate_merged_paragraphs` assembly assert the to-translate user payload for segment N contains ONLY segment N (excludes the preceding N segments verbatim).
- contract: yes — BR-78 business-rule test; LLM client-protocol test if `translate_once` gains an optional system-channel context param.
- integration: yes — drive `translate_merged_paragraphs`/`translate_blocks_batch` with a fake client that "translates whatever it is asked to translate"; assert only segment N's translation returns (no bleed), using the real 8D 3-point fixture. Anti-tautology: assert the payload EXCLUDES neighbors and the fake echoes/translates its input — do not merely count segments.
- E2E / visual / data-boundary / resilience / fuzz-monkey / stress / soak: none.

## Required Agents
- spec-architect (design.md: delete-vs-system-channel + exact context-passing signature), implementation-planner, bug-fix-engineer (lead fix + reproduction/regression evidence), backend-engineer (client-protocol + translation_helpers/context_prompts), test-strategist, contract-reviewer (BR-78 + client-protocol conformance), qa-reviewer.
- Not required: frontend-engineer, ui-ux-reviewer, visual-reviewer (no UI), e2e/monkey/stress-soak.

## Inferred Acceptance Criteria
- AC-1: For a sequence of segments, the to-translate USER payload handed to `client.translate_once` for segment N contains ONLY segment N's source text — no verbatim text from the preceding `CONTEXT_WINDOW_SEGMENTS` segments.
- AC-2: A fake client that "translates whatever it is asked to translate" returns only segment N's translation (no bleed of preceding points), verified with the real 8D 3-point fixture.
- AC-3: The reproduction test fails (RED) against pre-fix code and passes (GREEN) after the fix, using the real 8D PDF segments as the fixture.
- AC-4: Retained context is delivered via the system channel or otherwise structurally separated from the translatable user payload; deletion is used only if `design.md` records it as the chosen smallest safe fix.
- AC-5: BR-78 is updated to state that preceding context segments are no longer injected into the translatable payload.
- AC-6: `CONTEXT_WINDOW_SEGMENTS` (2) and `CONTEXT_MAX_CHARS` (300) retain their existing values; no config value change.
- AC-7: Existing context/few-shot/client tests stay green; any test double reproducing the `translate_once` signature is updated in the SAME change if the signature gains an optional context param (CLAUDE.md "additive kwargs to translation seams break test doubles").

## Tasks Not Applicable
- applicable — DO NOT skip: 1.3 (design — arch review yes).
- not-applicable: 2.1 (API), 2.2 (CSS/UI), 2.3 (Env), 2.4 (Data shape), 2.6 (CI/CD), 3.3 (E2E/resilience), 3.4 (data-boundary/monkey), 3.5 (stress/soak), 4.2 (frontend), 4.3 (env/deploy), 4.4 (CI/CD workflows), 5.1 (UI/UX), 5.2 (visual), 6.4 (nightly/manual).

## Clarifications or Assumptions
- The fix is prompt-assembly correctness, not a semantic change to context-window intent — BR-78 keeps providing N preceding segments as reference; only their LOCATION in the prompt changes so they are not translated.
- Tier-floor override recommended: trigger vocab present ("cache" via SCENARIO_CACHE/translation_cache nearby, "endpoint"/"route", "session") — none correspond to a real auth/secret/migration/endpoint/session change. Apply `tier-floor-override` if the gate vocab-matches.
- Providers cloud-only (PANJIT/DeepSeek); `ollama_client.py` still in scope because the shared `translate_once` signature changes for all three clients if the system-channel seam is chosen.
- QE/COMET-adjacent test collection (if touched) runs under `conda run -n translate-tool`; the core repro test is torch-free.
