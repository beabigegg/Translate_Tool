# Change Classification

## Change Types
- primary: bug-fix (behavior-changing, data/output correctness in the translation body path)
- secondary: business-logic-change (new/extended BR mirroring BR-68 for the non-table path + a meta/refusal output guard)

## Lane
- bug-fix

## Bug Symptom Type
- data

## Diagnostic Only
- no

## Bug Evidence Required
- symptom: a trivial/non-translatable body segment yields a meta/refusal reply ("Could you please provide the text you'd like translated?") written verbatim into the output (8D PDF English run, task 42265c0b).
- expected: trivial body segments pass through untranslated (output = source); the model's meta/refusal reply is never written to output.
- actual: body segments have no non-translatable passthrough (unlike table cells, BR-68); trivial segments are sent to the LLM which asks back, and the ask-back is stored as the "translation."
- reproduction: deterministic with fakes (no live LLM) — a call-counter fake for the passthrough case; a fake returning the ask-back string for the output-guard case; 8D trivial segments as fixture. Cache empty → live reply. PRE-EXISTING (July-2 log). bug-fix-engineer records per ADR 0006 §6/§7.
- hypotheses: no input passthrough for body segments; no output-side meta/refusal guard.
- root cause pointer: `app/backend/utils/translation_helpers.py` (translate_merged_paragraphs) + `app/backend/services/translation_service.py` (result mapping; BR-68 numeric passthrough precedent at :887).
- regression: table-cell BR-68 path unchanged; genuinely translatable text still translated (no over-passthrough / no refusal-detector false positive).

## Risk Level
- medium

## Impact Radius
- module-level (translation body path: `utils/translation_helpers.py` + `services/translation_service.py`; no auth/payments/migration/concurrency)

## Tier
- 2

## Architecture Review Required
- no
- reason: The placement questions (where the guards live; refusal-detector precision) are localized with an existing precedent (table BR-68 numeric passthrough at `translation_service.py:887`); they fit inside `implementation-plan.md`. IF the fix introduces a NEW `translation_status` enum value (rather than reusing `passthrough`/`failed`), promote to design review and add `contracts/data/data-shape-contract.md`. Default plan: reuse existing dispositions → no design.

## Required Artifacts
The 7 always-required: change-request, change-classification, implementation-plan, test-plan, ci-gates, tasks, context-manifest.

## Optional Artifacts (default: no)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | root cause + current behavior captured in change-request |
| proposal.md | no | fix scope is fixed |
| spec.md | no | no behavior decision beyond the two guards |
| design.md | no | no architecture review (unless a new translation_status value is introduced) |
| qa-report.md | no | routine pass/fail → agent-log/qa-reviewer.yml |
| regression-report.md | no | regression scope captured in test-plan + bug-fix-engineer.yml |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | n/a |
| stress-soak-report.md | no | n/a |

## Required Contracts
- API/CSS/Env/CI: none.
- Data shape: none — UNLESS a new `translation_status` value is introduced for the body path (reusing `passthrough`/`failed` needs no change); if introduced, `contracts/data/data-shape-contract.md` becomes required + Architecture Review flips to yes.
- Business logic: `contracts/business/business-rules.md` — a NEW BR (next free number above BR-106; BR-38/104/105/106 live) mirroring BR-68 for the body/non-table passthrough + documenting the meta/refusal output guard. Extending an existing passthrough rule is acceptable.

## Required Tests
- unit: trivial/non-translatable classifier — client NOT called (call-counter fake); meta/refusal detector positive AND negative cases; source-fallback writer.
- contract: behavioral test proving the new/extended body-path passthrough BR + the meta/refusal output-guard BR.
- integration: `translate_merged_paragraphs` → `on_segment_done` → `tmap` mapping with a fake client — both guards end-to-end; assert the SOURCE is written (not merely non-empty).
- data-boundary: edge inputs (empty, punctuation-only, lone number, single short token, already-target-language) classified as passthrough; genuinely translatable text NOT passed through.
- resilience: fake client returns ask-back / question-back / language-note → pipeline degrades to source, never emits the meta string.
- E2E / visual / fuzz-monkey / stress / soak: none.

## Required Agents
- implementation-planner, bug-fix-engineer (implementation owner + folds backend-engineer for the data symptom), test-strategist, contract-reviewer, qa-reviewer.
- Not required: spec-architect (no design), frontend-engineer, ui-ux-reviewer, visual-reviewer, e2e/monkey/stress-soak.

## Inferred Acceptance Criteria
- AC-1: A trivial/non-translatable body segment (pure number, punctuation-only, already-target-language label, very short single token) is passed through untranslated — output equals source AND the LLM client is NOT called (call-counter fake).
- AC-2: When the LLM returns a meta/refusal reply, the pipeline writes the SOURCE (or marks the segment failed) into results — never the meta string.
- AC-3: The meta/refusal detector does not misfire on a genuine translation that legitimately contains a question mark or reads like a note (no false-positive suppression).
- AC-4: Genuinely translatable body content is still sent to the LLM and translated normally (conservative passthrough — no dropped/altered real text).
- AC-5: The table-cell path and its BR-68 numeric passthrough are unchanged (no table regression).
- AC-6: A reproduction test from the real 8D trivial segments + a fake client returning the ask-back string FAILS pre-fix (RED) and PASSES post-fix (GREEN); no live LLM.
- AC-7: A new/extended business rule documents the body-path non-translatable passthrough + the meta/refusal output guard, consistent with BR-68.

## Tasks Not Applicable
- not-applicable: 1.3 (design — arch review no), 2.1 (API), 2.2 (CSS/UI), 2.3 (Env), 2.4 (Data shape — conditional; skip unless a new translation_status value is introduced), 2.6 (CI/CD), 3.3 (E2E/resilience — resilience folded into unit), 3.4 (data-boundary/monkey engineer — boundary folded into unit tests), 3.5 (stress/soak), 4.2 (frontend), 4.3 (env/deploy), 4.4 (CI/CD workflows), 5.1 (UI/UX), 5.2 (visual), 6.4 (nightly/manual).

## Clarifications or Assumptions
- Secondary business-logic-change promotion is deliberate: a bug-fix needing a contract change follows the contract path.
- Tier-floor override watch: "cache"/"provider" vocab appears as EVIDENCE only ("the translation cache is empty", "PANJIT/DeepSeek") — no cache or provider-routing change. Apply `tier-floor-override` if the gate vocab-matches.
- CLAUDE.md learnings: additive branches/kwargs to translation seams break test doubles — grep + update fakes same change; anti-tautology (call-counter for "not called"; assert SOURCE value); conda `translate-tool` env for torch/QE collection.
- Data-shape conditional: introducing a NEW `translation_status` value flips Architecture Review to yes + requires design.md + `data-shape-contract.md`. Default plan reuses `passthrough`/`failed`.
