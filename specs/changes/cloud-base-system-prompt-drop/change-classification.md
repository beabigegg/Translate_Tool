# Change Classification

## Change Types
- primary: bug-fix, business-logic-change
- secondary: (none)

Rationale for the second primary: the request is symptom-driven (bug-fix lane), but the correct fix crosses into contract territory. BR-109 governs how the cloud client *delivers* `self.system_prompt`; it is silent on how that attribute is *populated*, and that silence is exactly the gap this defect (and its sibling) exploited. Pinning the population requirement forces the contract path and `contract-reviewer`.

## Lane
- bug-fix

The request starts from a wrong/inert existing behavior (the profile base prompt never reaches cloud models), reproduced by live payload interception. The root cause is already located but the lane is still symptom-driven and requires a RED reproduction plus a regression guard, which is bug-fix-engineer's job. The `business-logic-change` promotion adds the contract path on top of the bug-fix lane; it does not turn this into greenfield feature work.

## Bug Symptom Type
- api

The defect lives at the outbound LLM client request boundary: the `/v1/chat/completions` POST body is missing the profile base system prompt. The assertable surface is the captured outgoing request payload, and a business contract (BR-109) is touched — so `api` routing (backend owner + contract-reviewer) fits better than `data`.

## Diagnostic Only
- no

The root cause is identified and the fix is a concrete behavior correction (populate the cloud client's `system_prompt`), not instrumentation.

## Bug Evidence Required
- symptom: on the cloud path (PANJIT/DeepSeek, the default path), the translation profile's base system prompt — role declaration plus terminology/register guidance — never reaches the model; only the scenario appendix, the few-shot block, and the BR-109 `Document context:` preamble do.
- expected behavior: the cloud client's outgoing system message contains the profile's base prompt (e.g. the semiconductor role declaration), exactly as `OllamaClient` already delivers it.
- actual behavior: `base_system_prompt = client.system_prompt` reads the class-attribute default `""` for the cloud client, so `build_strategy` composes everything on top of an empty base; confirmed by intercepting real POST bodies while investigating job `53676512617243fcbbc60dbac0201102`.
- reproduction status: reproduced against the live pipeline via outgoing-POST-body interception; must be pinned as a deterministic RED test that captures the outgoing payload (never `client.system_prompt`).
- hypotheses: `OpenAICompatibleClient.__init__` lacks a `system_prompt` parameter; the orchestrator constructs the cloud client without it and passes `system_prompt=` only to the Ollama client; the class-attribute default `""` is then read.
- root cause pointer: `app/backend/clients/openai_compatible_client.py` `__init__` signature (no `system_prompt`) plus `app/backend/processors/orchestrator.py` cloud-client construction and the `base_system_prompt = client.system_prompt` read after `client` is reassigned to the cloud client.
- regression evidence: add a payload-boundary regression test asserting the base prompt appears in the outgoing system message; audit and update every constructor call site and test double mirroring the `OpenAICompatibleClient` signature.

## Risk Level
- medium

Not auth/payments/migrations, but it changes a shared LLM-client constructor seam whose signature ripples to several construction sites and to test doubles that reproduce the signature — a documented repo hazard that hides in unexpected test files. It also affects the quality of every cloud translation, which is the default path.

## Impact Radius
- cross-module

Touches `clients/` and `processors/orchestrator.py`, and every other `OpenAICompatibleClient` construction site.

**Construction-site inventory (verified on disk by main Claude before this file was written — the classifier's list was incomplete):**

| file | sites | note |
|---|---|---|
| `app/backend/processors/orchestrator.py` | 2 (L532 primary, L560 fallback-chain) | the defect site |
| `app/backend/api/routes.py` | 3 (L977, L1068, L1181) | provider health / models / test-translation |
| `app/backend/services/quality_judge.py` | 1 (L111) | judge client |
| `app/backend/services/term_extractor.py` | 1 (L570) | **missed by the classifier** |
| `app/backend/services/model_router.py` | 0 | **classifier was wrong — no reference at all** |

Test constructions: 39 across `tests/test_openai_compatible_client.py`, `tests/test_provider_fallback.py`, `tests/test_term_extractor.py`, `tests/test_term_extractor_resilience.py`, `tests/test_cloud_total_timeout.py`, `tests/test_llm_client_protocol.py`.

## Tier
- 2

## Architecture Review Required
- no
- reason: the single open design question — constructor kwarg vs. post-construction assignment — is a localized implementation choice, not a module-boundary, data-flow, or migration decision. The change-request assigns it to the implementation plan, and `implementation-planner` can settle it while auditing all construction sites.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current behavior is fully captured in change-request.md "Known Context" |
| proposal.md | no | no product/user-facing decision to investigate |
| spec.md | no | no separate spec needed |
| design.md | no | no architecture review |
| qa-report.md | no | routine pass/fail goes in agent-log; upgrade to yes only on a blocking or approved-with-risk finding |
| regression-report.md | no | test-double audit and regression guard are covered by tests and agent-log pointers |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | not applicable |
| stress-soak-report.md | no | no load/soak surface |

Artifact minimization:
- Prefer optional `agent-log/*.yml` pointers for routine review evidence.
- Create report markdown only for blocking findings, approved-with-risk, visual evidence bundles, or high-risk load/soak results.
- Later artifacts should reference earlier artifacts by path/section/id instead of duplicating full content.

## Required Contracts
- API: none (endpoints are audited as construction sites only; no endpoint behavior or shape change)
- CSS/UI: none
- Env: none (explicit non-goal: no new env vars or flags)
- Data shape: none
- Business logic: `contracts/business/business-rules.md` — amend BR-109 to state that the cloud client must be populated with the caller's profile base `system_prompt`, so BR-109's delivery clause carries a non-empty base. This is NOT a pure implementation correction: BR-109 as written governs only delivery and merge order (ADR-0016) and is silent on population, which is the exact gap the defect used. Bump `schema-version` from the LIVE value and add a `contracts/CHANGELOG.md` entry.
- CI/CD: none

## Required Tests
- unit: yes — `OpenAICompatibleClient` construction populates and delivers the caller's `system_prompt`; assert on the outgoing request payload captured at the transport boundary, never on `client.system_prompt`.
- contract: yes — BR-109 conformance: with `profile_id=semiconductor` and provider `panjit`, the captured outgoing system message contains the profile role declaration, composed base → scenario appendix → few-shot → `Document context:` preamble (preamble last, not replacing the base).
- integration: yes — the orchestrator builds the cloud client and `base_system_prompt` is non-empty end to end; local Ollama outgoing payload unchanged; the construction-site audit does not regress the fallback chain, judge client, term extractor, or the provider endpoints.
- E2E: no (payload interception at the client boundary is sufficient)
- visual: no
- data-boundary: no
- resilience: no
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
- implementation-planner — settles the constructor-kwarg vs. post-construction-assignment decision; audits EVERY `OpenAICompatibleClient` construction site (see the verified inventory above) and all test doubles mirroring the signature; produces the execution packet before implementation. As the first shell-capable agent it must verify every named seam against live source.
- bug-fix-engineer — implementation owner; records the RED reproduction and regression guard in `agent-log/bug-fix-engineer.yml`, with evidence asserted on the outgoing payload, not on `client.system_prompt`. No separate backend-engineer is added for this localized seam fix.
- test-strategist — designs the payload-boundary tests and the AC → test mapping; ensures the assertion sits at the real HTTP boundary.
- contract-reviewer — reviews the BR-109 amendment; verifies no api/env/data drift.
- qa-reviewer — release readiness; confirms the full suite passes with all constructor doubles updated and no carried failures.

## Inferred Acceptance Criteria
- AC-1: With `profile_id=semiconductor` and provider `panjit`, the system message in the captured outgoing `/v1/chat/completions` POST body contains the semiconductor profile's role-declaration text.
- AC-2: The acceptance assertion is made on the captured outgoing request payload, never on `client.system_prompt` (the assignment-without-delivery tautology is explicitly avoided).
- AC-3: Composition order is preserved: base prompt → scenario appendix → few-shot block → BR-109 `Document context:` preamble, with the preamble last and not replacing the base.
- AC-4: Local Ollama outgoing-payload behavior is unchanged (the base prompt is still present exactly as before).
- AC-5: Every `OpenAICompatibleClient` construction site in the verified inventory is audited and either consistently populated or intentionally left, with no signature-mismatch regression.
- AC-6: Every test double across `tests/` that reproduces the `OpenAICompatibleClient` constructor signature is updated; the full suite passes with no new or carried failures.
- AC-7: A pre-fix RED test on the outgoing payload reproduces the empty-base defect (a behavioral assertion failure, not a collection or import error); post-fix the same test passes and remains as a regression guard.
- AC-8: BR-109 is amended to require population of the cloud client's base `system_prompt`, and `contracts/CHANGELOG.md` records the bump.

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 5.1, 5.2

Rationale: 1.3 no design/architecture review; 2.1/2.2/2.3/2.4/2.6 no API, CSS/UI, env, data-shape or CI/CD contract touched; 3.3 no E2E/resilience surface; 3.4 no data-boundary surface; 3.5 no load/soak risk; 4.2 no frontend surface; 4.3 no new env vars; 4.4 existing CI gates suffice; 5.1/5.2 no UI surface.

## Clarifications or Assumptions
- Assumption: the `system_prompt` value flows unchanged from `_get_translation_profile(group.profile_id).system_prompt` (job_manager); this change only ensures it reaches the cloud client, so job_manager profile resolution is read-only context, not edited (consistent with the non-goal).
- Assumption: the BR-109 amendment is additive (it clarifies population), not a breaking change to the delivery mechanism or ADR-0016 routing. The `schema-version` bump must be taken from the LIVE `business-rules.md` value at edit time, never a number pre-baked in a plan.
- Open decision deferred to implementation-planner: constructor kwarg (mirrors `OllamaClient`, harder to forget, but ripples to all construction sites and doubles) vs. post-construction assignment (one file, but easy to forget at a new site). Either is acceptable if AC-1..AC-7 hold; the planner must pick one and justify it against the construction-site audit.
- Correction applied by main Claude before writing this file: the classifier named `services/model_router.py` as a construction site (it contains no reference to `OpenAICompatibleClient` at all) and omitted `services/term_extractor.py` (which constructs one at L570). The verified inventory above supersedes the classifier's list, and the context manifest reflects it.

## Context Manifest Draft

See `context-manifest.md` for the authoritative read boundary. Affected surfaces:

- Cloud LLM client construction and outbound request assembly — `app/backend/clients/openai_compatible_client.py`
- Orchestrator cloud-client wiring and the `base_system_prompt` read — `app/backend/processors/orchestrator.py`
- Strategy composition and profile sourcing — `app/backend/services/translation_strategy.py`, `app/backend/translation_profiles.py`, `app/backend/services/job_manager.py`
- Other construction sites — `app/backend/api/routes.py`, `app/backend/services/quality_judge.py`, `app/backend/services/term_extractor.py`
- Test doubles mirroring the client constructor signature
- Business rule BR-109 — `contracts/business/business-rules.md`
