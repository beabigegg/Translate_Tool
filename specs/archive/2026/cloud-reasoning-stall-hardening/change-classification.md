# Change Classification

## Change Types
- primary: business-logic-change, feature-enhancement (reliability/quality hardening)
- secondary: none (no API/CSS/data/CI surface; env is conditional — see Required Contracts)

## Lane
- feature

Rationale: proactive hardening with root causes ALREADY diagnosed (faulthandler
stacks, live PANJIT probes) that REQUIRES contract changes (BR-100 default,
BR-109/ADR-0016 system-message composition, critique-loop policy). A bug-fix that
needs a contract change is promoted to feature/business-logic.

## Risk Level
- high

Item 1 rewrites the SYSTEM-channel composition carrying the ADR-0016 no-leak
invariant on EVERY cloud translation call; item 4 risks silently degrading
translation quality — both threaten the standing "no-drop / 100% correct" goal.
Items 2-3 change production abort/hang behavior. Pre-existing machinery + a
verified reference edit for item 1 cap this below critical.

## Impact Radius
- cross-module (clients + config + services/translation path)

## Tier
- 1

## Architecture Review Required
- yes
- reason: Item 4 is a genuine non-obvious design decision with a quality
  trade-off (gate vs cap-rounds vs cache-hit-skip). Item 1 changes the ADR-0016
  out-of-band system-channel composition (needs an ADR for the harmony
  `Reasoning:` prefix + outline-seam carve-out). Items 2-3 are
  operational-risk/timeout decisions. spec-architect must fix these in design.md
  before implementation-planner runs.

## Required Artifacts
Standard 7: change-request.md, change-classification.md, implementation-plan.md,
test-plan.md, ci-gates.md, tasks.yml, context-manifest.md.

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Captured in change-request + design.md |
| proposal.md | no | Scope/mechanism decided |
| spec.md | no | No user-facing spec beyond design.md |
| design.md | yes | Architecture Review = yes (critique mechanism + ADR-0016 composition + BR-100 + embed bound); spec-architect authors |
| qa-report.md | yes | Item 4 "must not silently degrade quality" needs durable sign-off |
| regression-report.md | no | Fits agent-log pointer + regression tests unless blocking findings |
| visual-review-report.md | no | No UI |
| monkey-test-report.md | no | N/A |
| stress-soak-report.md | no | Bounds hang exposure rather than adding load; resilience tests cover it |

## Required Contracts
- API: none
- CSS/UI: none
- Env: conditional — `OPENAI_TRANSLATION_REASONING` is a hardcoded constant (no
  env contract). `OPENAI_TOTAL_TIMEOUT_SECONDS` default change syncs
  env-contract.md + .env.example.template ONLY if that timeout is env-documented
  (contract-reviewer/planner verify against live config.py).
- Data shape: none
- Business logic: yes — BR-100 (ceiling default 480→~120; embed() inside the
  bound), BR-109/ADR-0016 (harmony `Reasoning:` directive in SYSTEM channel,
  never leaked to user payload; outline seam exempt), and a critique-loop
  cost/quality policy rule (new or updated BR).
- CI/CD: none

## Required Tests
- unit: config constants; `_post_completion` reasoning-prefix composition;
  critique gate/cap/skip logic
- contract: ADR-0016/BR-109 system-message no-leak tests UPDATED for the prefix
  (exact-equality on outgoing SYSTEM message AND directive absent from every
  user-role message); BR-100 ceiling contract
- integration: cloud translate path emits `Reasoning: low`; outline `complete()`
  retains reasoning and `_detect_document_context` still returns a valid summary
- E2E: manual/authorized live PANJIT probe only — never a gated test, never reads docs/TEST_DOC/
- visual: none
- data-boundary: none
- resilience: stalled/half-closed `_post_completion` aborts within the lowered
  ceiling; `embed()` bounded stall aborts and degrades to `[]`
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- spec-architect, implementation-planner, backend-engineer, test-strategist,
  contract-reviewer, e2e-resilience-engineer, qa-reviewer
- (ci-cd-gatekeeper runs to author the required ci-gates.md per skill policy)

## Inferred Acceptance Criteria
- AC-1: On every cloud translation call (`translate_once`, `translate_json`, the
  critique loop, the JSON-fallback, the judge), the outgoing SYSTEM message begins
  with the harmony `Reasoning: low` directive sourced from
  `OPENAI_TRANSLATION_REASONING`, and that directive appears in NO user-role
  message content (captured-payload exact-equality on the receiving field).
- AC-2: The outline seam `complete()` passes `reasoning=None` (no directive in its
  SYSTEM message) and `_detect_document_context` still returns a valid non-empty
  summary.
- AC-3: `OPENAI_TOTAL_TIMEOUT_SECONDS` default lowered to ~120s; a simulated
  stalled/half-closed `_post_completion` aborts within the new ceiling (well under
  480s) and the job degrades gracefully instead of hanging.
- AC-4: `embed()` is routed through `_run_bounded_post`; a stalled embedding POST
  aborts within the ceiling and degrades to `[]` rather than hanging indefinitely.
- AC-5: Under `CRITIQUE_LOOP_ENABLED`, the critique loop's live `translate_once`
  exposure is reduced by the chosen bounded/opt-out mechanism (per design), with a
  test proving no segment is dropped/emptied and quality is not lowered below
  current behavior.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.4, 4.2, 5.1, 5.2, 3.4, 3.5
- conditional (leave pending until contract-reviewer / ci-cd-gatekeeper resolve): 2.3, 4.4

## Clarifications or Assumptions
- Lane = feature (root causes diagnosed AND contract changes required).
- No-shell caveat: candidate seams (`_run_bounded_post` home, `_batched_critique_adopt`
  module, `system_context` composition) are pattern-matched, NOT read from source;
  planner/backend MUST grep-confirm every seam before wiring and correct the
  design/contract if wrong.
- Live PANJIT E2E evidence is manual/authorized; never a gated test; never reads
  docs/TEST_DOC/.
- Watch tautological-test forms (assignment-without-delivery, order-without-location,
  caplog root-logger bleed) — assert on the captured outgoing payload at the real
  boundary.

## Context Manifest Draft
See context-manifest.md (written from this draft).
