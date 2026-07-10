# Change Classification

## Change Types
- primary: business-logic-change, data-shape-change
- secondary: bug-fix (subsumes the deferred phantom-column defect), refactor

## Lane
- feature

Symptom-adjacent — the table path fixes `parse() returned None` — but the root cause is already known from live source, and this is a designed wire-format migration, not a location-unknown symptom hunt. The bug is subsumed and its regression evidence is required in the test plan.

## Atomic-split assessment

**No split.** The classifier assessed this explicitly and the coupling is real, not incidental:

1. **One shared invariant governs both paths**: on unparseable or schema-invalid JSON, fall back to today's path, never fail the job, emit INFO via the BR-109 `log(...)` channel. Splitting duplicates that discipline across two changes and invites divergence.
2. **Both paths converge on the same seam and the same two clients** (`client.translate_once` on Ollama and OpenAI-compatible). The largest open design question — which seam carries the JSON, and whether the providers expose a native JSON/response-format mode — has one answer that both paths consume.
3. **Shared schema-validation machinery.** Building the parse-or-fall-back validator once is the point.
4. **Explicit recorded user scope**: the user was asked and chose both paths.

**Conditional-split exit**: if `spec-architect` or `implementation-planner` find that the provider-capability answer diverges per path, or the consumer verification balloons, they should recommend a split then.

## Bug Symptom Type
- n/a (lane is feature)

## Diagnostic Only
- no

## Risk Level
- high

Every translation call in the product goes through one of these two paths — this is the default path for all users. The mandatory never-fail fallback caps blast radius but does not remove it. Changing a shared wire format is the class of change that has silently orphaned modules in this repo before.

## Impact Radius
- system-wide

**Consumer inventory (verified on disk by main Claude before this file was written — the classifier's list was wrong):**

| file | role | note |
|---|---|---|
| `app/backend/processors/xlsx_processor.py` | calls `serialize()` + `parse()` | L206 / L213 — the phantom-column site |
| `app/backend/processors/pptx_processor.py` | calls `serialize()` + `parse()` | L357 / L364 |
| `app/backend/processors/docx_processor.py` | calls `serialize()` + `parse()` | L846 / L853 — **missed entirely by the classifier** |
| `app/backend/processors/pdf_processor.py` | calls `serialize()` + `parse()` | L173 / L179 |
| `app/backend/services/translation_service.py` | calls `serialize()` + `parse()` | L901 / L908 — the PDF cell-batch path |
| `app/backend/clients/openai_compatible_client.py` | `_build_table_translate_prompt()` | L280 is a docstring, not a call; but this method tells the model the wire format |
| `app/backend/clients/ollama_client.py` | `_build_table_translate_prompt()` | same |

The classifier asserted that `contracts/data/data-shape-contract.md` §Table Serialization Wire Format carries a "named consumers table". **It does not** — the consumers table belongs to the IR section (`### Known consumers of the IR`, L249). The wire-format section (L452) has no consumer registry at all. That *raises* the orphaning risk rather than lowering it: a grep of the call sites is the only defense, and one consumer (`docx_processor.py`) was already invisible to both the contract and the classifier.

## Tier
- 1

Tier 0 was considered given system-wide + high risk. Tier 1 is correct because the change carries a mandatory safe fallback to today's behavior, is reversible, adds no data migration or DDL, and adds no required env var unless the plan proves a rollback flag is needed. The built-in fallback is the de-risking factor that distinguishes 1 from 0.

## Architecture Review Required
- yes
- reason: three genuine, coupled design decisions gate implementation. (a) Which seam carries the table JSON — reuse `translate_once`, which prepends "Translate the following text…" framing, or a new dedicated unwrapped seam (the BR-109 `complete()` seam is system-prompt-free and therefore wrong for translation). (b) Whether the body path needs an envelope for every segment or only above a length threshold. (c) Whether PANJIT and DeepSeek expose a native JSON / response-format mode — this must be probed against the live endpoint, not assumed. These are module-boundary and data-flow decisions with a rollback dimension, so `spec-architect` writes `design.md` before `implementation-planner` runs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior is captured in change-request §Known Context; do not duplicate. |
| proposal.md | no | The behavior decision (both paths, JSON, fallback-to-existing) is already made by the user. |
| spec.md | no | No user-facing spec beyond the acceptance criteria. |
| design.md | yes | Architecture Review is yes; the three open seam/envelope/provider-mode questions plus the consumer verification plan need a durable design record. |
| qa-report.md | yes | High-risk default translation path; durable release-readiness evidence is warranted. |
| regression-report.md | no | Covered by test-plan + agent-log; promote only if a blocking regression surfaces. |
| visual-review-report.md | no | No UI output change. |
| monkey-test-report.md | no | Not applicable. |
| stress-soak-report.md | no | Call volume explicitly out of scope. |

Artifact minimization:
- Prefer optional `agent-log/*.yml` pointers for routine review evidence.
- Later artifacts reference earlier ones by path/section/id instead of duplicating content.

## Required Contracts
- API: none (no endpoint add, rename, or behavior change)
- CSS/UI: none
- Env: conditional — only if `implementation-plan.md` proves a rollback feature flag is required. If added, it must land in `contracts/env/env-contract.md` and `.env.example.template` in the same change, per the Deployment Sync Policy.
- Data shape: yes — `contracts/data/data-shape-contract.md` §Table Serialization Wire Format: replace the Markdown pipe-grid with a JSON cell list (explicit `row`/`col` coordinates, content-bearing cells only). The section currently has **no** consumers table; one must be added, listing all seven files in the inventory above.
- Business logic: yes — `contracts/business/business-rules.md`: the body-path `{"text":…}` / `{"translation":…}` envelope and schema validation, the mandatory fallback discipline bound to BR-109's INFO-via-`log(...)` requirement, and the BR-108 (`is_meta_refusal`) retire-or-keep decision. BR-107 and BR-68 passthrough remain unchanged and must be stated as preserved.
- CI/CD: none unless a new gate or test step is added.

**BR-108 retirement hazard**: `business-rules.md` carries absence-regression tests asserting the literal tokens `BR-92` and `rescore` do not appear. If BR-108 is retired, contract-reviewer must grep the target file against known absence-tests before committing and must not name a purged token.

## Required Tests
- unit: yes — JSON serialize (content-only cells with coordinates), JSON parse/round-trip, body envelope build/parse, schema validation accept/reject, fallback-trigger selection.
- contract: yes — table wire-format conformance against the data-shape contract; body envelope schema conformance.
- integration: yes — xlsx / pptx / docx / pdf-cell-batch → client → parsed translations, asserting on the **captured outgoing request payload** and the real returned translations, never on internal attributes.
- E2E: no — the "real XLS completes its table batch without falling back" criterion is realized as an integration test with a captured payload; a full backend E2E is disproportionate.
- visual: no
- data-boundary: yes — phantom-column / shape-mismatch input, corrupted-JSON and schema-invalid reply → fallback path.
- resilience: yes — corrupted or unparseable JSON never fails the job on either path, and each fallback emits the BR-109 INFO line through the job `log(...)` callback, asserted on the `TranslateTool` channel with a `record.name` filter.
- fuzz/monkey: no
- stress: no (call volume out of scope)
- soak: no

## Required Agents
- spec-architect — writes `design.md` resolving the three open seam / envelope / provider-mode questions and the consumer verification plan.
- contract-reviewer — reviews the data-shape wire-format change plus the new consumers table, and the business-rules change including the BR-108 decision and absence-test safety.
- test-strategist — builds the AC → test mapping, enforces boundary-payload assertions, guards against the five tautology forms.
- implementation-planner — turns design plus contracts plus tests into the execution packet; must verify every named seam and every consumer against live source before wiring.
- backend-engineer — implements the serializer, both LLM clients' prompt builders, the four processors, the PDF cell-batch path in `translation_service`, and `translation_helpers`.
- e2e-resilience-engineer — Tier 1: the corrupted-JSON / never-fail-fallback resilience and data-boundary tests.
- qa-reviewer — release readiness for a high-risk default path; owns `qa-report.md`.

Not required: frontend-engineer, ui-ux-reviewer, visual-reviewer (no UI output); monkey-test-engineer, stress-soak-engineer (call volume out of scope).

## Inferred Acceptance Criteria
- AC-1: The table path serializes only content-bearing cells as JSON carrying explicit `(row, col)` coordinates; the phantom-column sheet from job `53676512617243fcbbc60dbac0201102` (logged `expected 9×257` and `16×257` against 47 real cells) completes its table batch WITHOUT falling back to per-cell BR-82.
- AC-2: A valid table JSON reply is validated against a schema and restores whole-table context, asserted on the captured outgoing request payload and the real returned translations — never on internal attributes.
- AC-3: The body path sends `{"text": …}` and parses `{"translation": …}` validated against a schema, replacing after-the-fact BR-108 string classification on the happy path.
- AC-4: On unparseable or schema-invalid JSON, the table path falls back to per-cell BR-82 and the body path falls back to plain-text `translate_once`. The job never fails for this reason.
- AC-5: Each fallback emits an INFO line through the job `log(...)` callback — the `TranslateTool` channel that reaches `translator.log` per BR-109 — verified with a `record.name` filter. A `logging.getLogger(__name__)` call does not satisfy this.
- AC-6: BR-107 (body passthrough) and BR-68 (numeric-cell passthrough) still bypass the LLM before any JSON envelope is constructed.
- AC-7: All five `table_serializer` call sites (xlsx, pptx, docx, pdf processors and `translation_service`) and both `_build_table_translate_prompt` implementations are updated and verified against live source in this change. No consumer of the old grid format remains **on the flag-ON path** — grep the call sites; do not trust archive status. (Amended after implementation-planner surfaced the contradiction and main Claude probed the live endpoint. The original wording, "no consumer of the old grid format remains", cannot coexist with the env contract's promise that `JSON_STRUCTURED_TRANSLATION_ENABLED=0` restores byte-for-byte legacy behaviour. The probe settled it: pipe-grid DOES succeed on a clean table — a 2×2 returns `GRID OK` and even yields the correct row-context translation `制作日期` → `Ngày lập` — and fails in production only because `xlsx_processor` feeds it a 9×257 phantom grid. Deleting it would make flag-OFF a DEGRADATION to per-cell translation, not a revert, defeating the kill switch. The legacy `serialize()`/`parse()` and both `_build_table_translate_prompt` methods are therefore RETAINED, frozen, and reachable only when the flag is off. Recorded in data-shape-contract.md's consumers table.)
- AC-8: `data-shape-contract.md` §Table Serialization Wire Format is updated and gains a consumers table naming all seven files; `business-rules.md` is updated; and the BR-108 retire-or-keep decision is recorded, with absence-test safety checked if retired.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.6, 3.4, 3.5, 4.2, 4.4, 5.1, 5.2

Rationale: 2.1 no API surface; 2.2 no CSS/UI; 2.6 no CI/CD contract; 3.4 no fuzz/monkey surface; 3.5 no stress/soak (call volume out of scope); 4.2 no frontend surface; 4.4 existing CI gates suffice; 5.1/5.2 no UI surface. **Task 1.3 (design) is APPLICABLE and must not be skipped.** Task 2.3 (env contract) stays `pending` until the implementation plan settles whether a rollback flag is needed.

## Clarifications or Assumptions
- Encoded as constraints, not open questions: the fallback is to the EXISTING path (per-cell BR-82 for tables, plain-text `translate_once` for body) — not "retry once", not "strict / no fallback". The job never fails for this reason. This is the user's explicit choice.
- Encoded constraint: the fallback must be observable at INFO through the job `log(...)` callback (BR-109), and acceptance is asserted at the real boundary, never on internal attributes.
- Out of scope and not to be touched: critique-loop call volume; the residual double LibreOffice `.xls` conversion; BR-109 doc-context delivery; BR-110 constructor parity; BR-78 system-channel neighbor context; ADR-0016 routing.
- Open for `design.md`, not classification: which seam carries the table JSON; whether short body segments need an envelope; whether PANJIT/DeepSeek support a native JSON / response-format mode.
- Corrections applied by main Claude before writing this file: (1) the classifier inferred `tests/test_meta_refusal.py`, which does not exist — the meta-refusal tests live in `tests/test_nontranslatable_segment_guard.py`; (2) it omitted `app/backend/processors/docx_processor.py`, a real `serialize()`/`parse()` consumer; (3) it asserted the wire-format contract section carries a named consumers table, which it does not. All paths in the manifest were verified to exist on disk.

## Context Manifest Draft

See `context-manifest.md` for the authoritative read boundary. Affected surfaces:

- Table wire format — `app/backend/utils/table_serializer.py` and its five call sites plus the two `_build_table_translate_prompt` implementations
- Body wire format — `translate_merged_paragraphs` in `app/backend/utils/translation_helpers.py` → `client.translate_once`
- Contracts — `contracts/data/data-shape-contract.md` §Table Serialization Wire Format, `contracts/business/business-rules.md`
