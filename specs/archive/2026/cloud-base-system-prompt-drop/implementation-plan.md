---
change-id: cloud-base-system-prompt-drop
schema-version: 0.1.0
last-changed: 2026-07-09
---

# Implementation Plan: cloud-base-system-prompt-drop

## Objective
Make the profile's base `system_prompt` reach cloud translation models. Add an
additive optional `system_prompt` kwarg to `OpenAICompatibleClient.__init__`
(mirroring `OllamaClient`) and pass the caller's `system_prompt` at the two
orchestrator cloud-client construction sites, so `base_system_prompt =
client.system_prompt` (orchestrator L608) is non-empty on the cloud path and
`build_strategy` composes the scenario appendix / few-shot block / BR-109
`Document context:` preamble on top of the real base prompt rather than `""`.
Prove it at the outgoing `/v1/chat/completions` payload boundary, never on
`client.system_prompt`.

## Execution Scope

### In Scope
- `OpenAICompatibleClient.__init__`: additive optional `system_prompt` kwarg,
  normalized and stored as an instance attribute (mirrors `OllamaClient`
  `ollama_client.py:112`).
- `orchestrator.py` L532 (primary cloud client) and L560 (fallback-chain client):
  pass `system_prompt=system_prompt` (the `process_files` parameter already
  passed to `OllamaClient` at L588).
- BR-110 correction (contract-reviewer): narrow the over-reaching "every
  construction site" enumeration — see the Decision Record and Known Risks. Bump
  `schema-version` from the LIVE value and add a `contracts/CHANGELOG.md` entry.
- New test functions per `test-plan.md` "Acceptance Criteria → Test Mapping"
  (test-strategist / bug-fix-engineer own the RED reproduction + regression
  guard, asserted on the captured outgoing payload).

### Out of Scope
- The 5 non-translation `OpenAICompatibleClient` sites — `routes.py` L977/L1068/
  L1181 (provider health / models / test-translation), `quality_judge.py` L111,
  `term_extractor.py` L570 — remain unchanged (default `""`). They do not supply
  a profile base prompt; see the Construction-Site Audit.
- The xlsx table-batch phantom-column defect (`ws.max_column`=257 →
  `table_serializer.parse()` returns `None`). Deferred to the JSON structured-I/O change.
- Critique-loop call volume (1 translate + 3 critique calls per segment).
- BR-109's delivery mechanism, ADR-0016 system-channel routing, `build_strategy`
  composition order, scenario / few-shot blocks, and `job_manager` profile resolution.
- No new env vars or feature flags. No API/schema/data-shape change.
- Local Ollama behavior must be byte-for-byte unchanged.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | `clients/openai_compatible_client.py` | Add optional `system_prompt` kwarg to `__init__`; set `self.system_prompt = (system_prompt or "").strip()` in the body (mirror `OllamaClient:112`); document it in the `__init__` Args docstring. Keep the class-attribute default `""` (L446) as the defensive/omitted-construction fallback. | bug-fix-engineer |
| IP-2 | `processors/orchestrator.py` | Add `system_prompt=system_prompt,` to the `OpenAICompatibleClient(...)` call at L532 (primary) and L560 (fallback). No other orchestrator edit. | bug-fix-engineer |
| IP-3 | `contracts/business/business-rules.md` BR-110 | Narrow the "This applies at every construction site (...)" enumeration to the two orchestrator sites; reclassify judge/term-extractor/diagnostic-route sites as legitimate non-supplying callers that keep the default. Bump `schema-version` from the LIVE value (currently 0.28.0 — do NOT hardcode a pre-baked number) and add a `contracts/CHANGELOG.md` entry. | contract-reviewer |
| IP-4 | `tests/` | Add the AC-mapped test functions (RED integration reproduction + post-fix companions) per `test-plan.md`; assert only on the captured outgoing `json=` payload. No existing test edited. | test-strategist / bug-fix-engineer |

## Decision Record: constructor kwarg vs post-construction assignment

**Chosen: additive optional `system_prompt` kwarg on `OpenAICompatibleClient.__init__`**,
defaulting so omitted construction yields `""` unchanged, with
`self.system_prompt = (system_prompt or "").strip()` — the exact normalization
`OllamaClient.__init__` uses (`ollama_client.py:112`). Passed only at the two
orchestrator sites (IP-2).

Evidence:
- BR-110 (`business-rules.md` L121) requires clients "accept and populate
  `system_prompt` **at construction**." Post-construction assignment does not
  satisfy "at construction" as written.
- Mirrors the sibling `OllamaClient` (already accepts `system_prompt`), so the
  family is uniform and the seam is harder to forget at a future site.
- Additive optional kwarg with an `""`-equivalent default keeps all 39 test
  constructions (across 6 files) and the 5 other production call sites
  source-compatible — none passes `system_prompt`, none needs editing. Confirmed
  against live source: `__init__` is NOT part of the `LLMClient` Protocol
  (`base_llm_client.py` declares exactly 5 methods: `translate_once`,
  `translate_batch`, `health`, `list_models`, `unload`), so
  `test_llm_client_protocol.py::test_protocol_defines_five_methods` is unaffected.

**Rejected: post-construction assignment in the orchestrator**
(`_cloud_client.system_prompt = system_prompt` after each construction).
Rejected because: (1) violates BR-110's "at construction" wording; (2) does not
mirror `OllamaClient`; (3) must be duplicated at both L532 and L560 and is easy
to omit at a new site — the exact class of "silently dropped write" defect this
change repairs; (4) offers no source-compatibility advantage over the optional
kwarg.

## Construction-Site Audit (all 7 verified on live source)

| # | site | role | issues profile-based translations? | supplies base prompt? | action |
|---|---|---|---|---|---|
| 1 | `orchestrator.py` L532 | primary cloud translation client | yes | yes (`system_prompt` param) | **pass** `system_prompt=system_prompt` (IP-2) — the defect site |
| 2 | `orchestrator.py` L560 | fallback-chain translation client (becomes `client` when it wins) | yes | yes | **pass** `system_prompt=system_prompt` (IP-2) |
| 3 | `routes.py` L977 | provider health probe (`.health()`, `model=""`) | no | no | **leave** (default `""`) |
| 4 | `routes.py` L1068 | provider live-models list (`model=""`) | no | no | **leave** |
| 5 | `routes.py` L1181 | diagnostic test-translation (no profile in scope) | no (diagnostic) | no | **leave** |
| 6 | `quality_judge.py` L111 | judge client — issues quality-judgement prompts | no | no | **leave** |
| 7 | `term_extractor.py` L570 | PANJIT embedding-first term extraction | no (embedding/extraction) | no | **leave** |

`services/model_router.py` has **no** reference to `OpenAICompatibleClient`
(classifier error already corrected; re-verified).

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | "Acceptance Criteria → Test Mapping" table (AC-1..AC-8) | tests to write/run |
| test-plan.md | "Test Execution Ladder" (collect/targeted/changed-area/contract/full) | phases + torch note (`conda run -n translate-tool`) |
| ci-gates.md | "Required Gates" table | verification commands (no new/edited gate) |
| business-rules.md | BR-110 (L121), BR-109 (L120) | population + delivery constraints |
| docs/adr/0016-context-out-of-band-system-channel.md | Decision + Invariant | system-channel routing must not change |
| translation_profiles.py | semiconductor role-declaration string (see test-plan.md Notes) | AC-1 assertion substring |
| ollama_client.py:112 | `self.system_prompt = (system_prompt or "").strip()` | normalization pattern to mirror |

## File-Level Plan

| path | action | notes |
|---|---|---|
| `app/backend/clients/openai_compatible_client.py` | edit `__init__` (L59-88) + Args docstring (L50-57) | add `system_prompt: Optional[str] = None`; `self.system_prompt = (system_prompt or "").strip()`; keep class attr `system_prompt: str = ""` (L446) |
| `app/backend/processors/orchestrator.py` | edit L532, L560 | add `system_prompt=system_prompt,`; no change to L608 read, L647 `build_strategy`, or L654/L666/L668 per-file reassignment |
| `contracts/business/business-rules.md` | edit BR-110 + frontmatter `schema-version` | IP-3 — contract-reviewer only; bump from LIVE value |
| `contracts/CHANGELOG.md` | add entry for the BR-110 correction | IP-3 — contract-reviewer only |
| `tests/test_orchestrator_context_detection.py` | add AC-1/2/3/5/7 functions | assert on captured outgoing `json=` payload only |
| `tests/test_openai_compatible_client.py` | add AC-6 default-omitted guard + post-fix kwarg companion | post-fix companions, never the AC-7 RED |
| `tests/test_ollama_client_dynamic_strategy.py` | add AC-4 Ollama payload-unchanged guard | local behavior regression |

## Contract Updates

- API: none (endpoints audited as construction sites only; no route behavior/shape change).
- CSS/UI: none.
- Env: none (explicit non-goal: no new env vars or flags).
- Data shape: none.
- Business logic: BR-110 enumeration narrowed (IP-3); `schema-version` bumped from
  LIVE value; `contracts/CHANGELOG.md` entry added. Do not touch BR-109's delivery
  clause or ADR-0016 routing.
- CI/CD: none.

## Test Execution Plan

Required floor: collect, targeted, changed-area (full ladder in `test-plan.md`
"Test Execution Ladder"; run targeted/QE-touching phases via
`conda run -n translate-tool cdd-kit test run --phase <p>` for the torch interpreter).

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1, AC-2, AC-7 | tests/test_orchestrator_context_detection.py::test_cloud_client_delivers_profile_base_system_prompt_semiconductor | RED pre-fix (payload assertion, not TypeError); GREEN post-fix — semiconductor role text present in outgoing system message |
| AC-3 | tests/test_orchestrator_context_detection.py::test_base_prompt_precedes_document_context_preamble_in_composition | base-prompt index < scenario < few-shot < `Document context:` index in one system string |
| AC-4 | tests/test_ollama_client_dynamic_strategy.py::test_ollama_outgoing_payload_base_system_prompt_unchanged | Ollama `payload["system"]` unchanged |
| AC-5 | tests/test_orchestrator_context_detection.py::test_fallback_chain_client_delivers_profile_base_system_prompt | fallback winner delivers base prompt (primary health probe forced to fail) |
| AC-6 | tests/test_openai_compatible_client.py::test_default_construction_without_system_prompt_stays_empty | omitted-kwarg construction → `system_prompt == ""` |
| AC-8 | `cdd-kit validate --contracts` | BR-110 + CHANGELOG bump consistent; exit 0 |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- Assertions live at the outgoing `/v1/chat/completions` `json=` payload boundary
  (or the Ollama `payload["system"]`), NEVER on `client.system_prompt` — that
  tautology is exactly what let the sibling BR-109 defect ship (AC-2 / BR-110).
- The AC-7 RED must fail on a payload assertion against unfixed source, not on a
  `TypeError` / collection / import error. The lower-level
  `OpenAICompatibleClient(system_prompt=...)` kwarg test is a post-fix companion
  only (pre-fix it raises `TypeError` — a forbidden RED shape).
- Keep implementation within the File-Level Plan. IP-3 (BR-110 + CHANGELOG) is
  contract-reviewer's; bug-fix-engineer must not edit contract files.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- **BR-110 over-reach (flagged prominently).** BR-110's general clause is
  correctly conditional — "instantiated by a caller **that supplies a base
  `system_prompt`**" — which exempts the 5 diagnostic/non-translation sites. But
  its second sentence enumerates "This applies at **every** construction site
  (`orchestrator.py` primary and fallback chain, `quality_judge.py`,
  `term_extractor.py`, and the provider health / models / test-translation routes
  in `api/routes.py`)", naming all 7. Sites 3–7 do NOT supply a profile base
  prompt and semantically should not: the judge issues quality-judgement prompts,
  the term extractor issues embedding/extraction prompts, and the routes are
  diagnostic (`model=""`, no profile in scope). Taken literally the enumeration
  contradicts the conditional clause and would demand meaningless population at 5
  sites. IP-3 narrows the enumeration to the two orchestrator sites; the
  `contracts/CHANGELOG.md` entry's own wording is already the conservative
  conditional form, so the fix aligns the rule row to it. This is a genuine
  self-contradiction in the just-written rule, not a planning nicety — correcting
  it now is far cheaper than encoding an over-broad rule.
- Shared-constructor-seam ripple (documented repo hazard): the additive optional
  kwarg with an `""`-equivalent default means no test double needs editing, but
  bug-fix-engineer must still confirm via the full-suite gate that none of the 39
  constructions regresses — verify, do not assume.
- `schema-version` staleness: contract-reviewer must bump from the LIVE
  `business-rules.md` value at edit time, never a number pre-baked here.
- `.cdd/code-map.yml` was not consulted for symbol ranges; all seams above were
  verified directly against live source (line numbers current as of this plan).
