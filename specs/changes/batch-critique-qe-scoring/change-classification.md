# Change Classification

## Change Types
- primary: refactor (performance optimization of existing control flow)
- secondary: performance — behavior-preserving; not business-logic-change (adoption rule preserved, not modified) and not api-only-change (no endpoint/schema change)

## Lane
- feature

(Performance refactor, NOT bug-fix — no incorrect/missing/broken behavior is
being corrected; the code works correctly today, only its wall-clock cost is
being reduced.)

## Risk Level
- medium

Rationale: the critique gate decides which translation (draft vs. revised) is
adopted. A batching bug — segment/index misalignment, broken per-segment
failure isolation, or changed timeout granularity — could silently alter
document output without any error. Behavior is preserved by intent, so
correctness must be proven by parity, not by new behavior. GPU/VRAM and
OOM-ladder interaction adds operational sensitivity.

## Impact Radius
- module-level (backend `services/` translation pipeline; `translation_service.py`
  + `quality_evaluator.py`). No cross-module contract or interface change — the
  function signatures consumed by `translation_strategy.py` / processors stay
  stable.

## Tier
- 2

## Architecture Review Required
- no
- reason: n/a — the change restructures control-flow loop nesting
  (per-segment → round-based) within a single service; it does not change
  the data model, module boundaries, public interfaces, contracts, or
  introduce a migration/rollback decision. It stays inside one seam.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior fully captured in change-request.md "Constraints to preserve" |
| proposal.md | no | Direction (round-based batching) already decided in the request |
| spec.md | no | No user-facing behavior decision |
| design.md | no | No architecture/data-model/module-boundary change |
| qa-report.md | no | Use agent-log/qa-reviewer.yml pointer unless parity/regression finds a blocking issue |
| regression-report.md | no | Parity is the core test; record pass/fail via agent-log/ unless a regression is found and accepted with risk |
| visual-review-report.md | no | No UI surface |
| monkey-test-report.md | no | Not applicable to an internal service refactor |
| stress-soak-report.md | no | A micro-benchmark / parity proof suffices at Tier 2 |

Artifact minimization:
- Prefer optional `agent-log/*.yml` pointers for routine review evidence.
- Create report markdown only for blocking findings, approved-with-risk, visual evidence bundles, or high-risk load/soak results.
- Later artifacts should reference earlier artifacts by path/section/id instead of duplicating full content.

## Required Contracts
- API: none — no new/changed/renamed endpoint, no schema change (confirm no drift; conformance gate should stay green)
- CSS/UI: none — no frontend surface
- Env: none — CRITIQUE_LOOP_ENABLED, CRITIQUE_MAX_ITERATIONS, CRITIQUE_TIMEOUT_SECONDS defaults unchanged; no new env var
- Data shape: none — no IR/persistence change
- Business logic: no change intended, but contract-reviewer must read contracts/business/business-rules.md to confirm the critique adoption rule (strict-greater-than, tie-keeps-draft) and any documented critique-loop invariant remain satisfied by the refactor. If the batched flow would alter a documented rule, promote this to business-logic-change.
- CI/CD: none

## Required Tests
- unit: `_critique_gate_adopt` adoption decision (strict-greater-than; tie keeps draft); round-based loop scores each round once; cache-key (":c") skip runs before any scoring
- contract: none (no API/data contract change)
- integration: parity — a multi-segment critique run adopts the identical per-segment draft/revised choices as the pre-refactor path; score_blocks() call count ≤ CRITIQUE_MAX_ITERATIONS (not once per segment×iteration)
- E2E: none required this pass
- visual: none
- data-boundary: none
- resilience: per-segment exception/timeout isolation within a batched round (one segment failing must not abort the round); COMET OOM ladder (8→4→1 + empty_cache) still exercised under the larger batched input
- fuzz/monkey: none
- stress: consideration only — a wall-clock micro-benchmark demonstrating reduced Trainer instantiations is recommended, but a full stress report is not required at Tier 2
- soak: none

## Required Agents
- implementation-planner — turns the round-based direction + preserved invariants + the batched-timeout/isolation decision into the execution packet (runs this pass; STOP after it per the request)
- contract-reviewer — confirm no API/data/env/business contract drift; verify adoption-rule invariant against contracts/business/business-rules.md; confirm the COMET predict() internal-chunking assumption against the installed comet version
- test-strategist — parity + isolation + OOM-ladder test plan and Acceptance-Criteria→Test mapping
- backend-engineer — eventual implementation owner (deferred; do NOT run this pass)
- e2e-resilience-engineer — per-segment failure/timeout isolation and OOM-retry resilience tests (deferred to implementation)
- qa-reviewer — release readiness / regression parity sign-off (deferred to implementation)

(No spec-architect, frontend-engineer, ui-ux-reviewer, or visual-reviewer — no design, UI, or visual surface.)

## Inferred Acceptance Criteria
- AC-1: For identical inputs, the round-based critique loop adopts exactly the same draft-vs-revised choice for every segment as the current per-segment loop (behavior parity).
- AC-2: score_blocks() is invoked at most once per iteration round (≤ CRITIQUE_MAX_ITERATIONS calls total), not once per (segment × iteration).
- AC-3: The strict-greater-than adoption rule is preserved — when revised QE == draft QE (tie), the draft is kept.
- AC-4: The critique cache key scheme (cache_model_key + ":c") is unchanged, and already-cached segments are skipped before any revision or scoring work runs in a round.
- AC-5: A single segment's exception or timeout does not abort revision/scoring/adoption for the other segments in the same round.
- AC-6: The COMET OOM retry batch-size ladder (8→4→1 with torch.cuda.empty_cache()) in score_blocks() still functions correctly with the larger batched input.
- AC-7: No REST API endpoint, data schema, env variable, config default, or frontend surface changes.
- AC-8: Peak GPU/VRAM does not materially increase (COMET's internal batch_size chunking still bounds memory regardless of total list length).

## Tasks Not Applicable
<!-- Comma-separated task IDs from tasks.yml that do NOT apply to this change.
     /cdd-new SKILL marks these as `status: skipped` in tasks.yml.
     Include 1.3 when design.md is not required. -->
- not-applicable: 1.3

## Clarifications or Assumptions
- Assumption: COMET's model.predict() internally chunks by its own batch_size param, so batching more segments into one score_blocks() call raises no material VRAM peak. contract-reviewer should confirm this against the installed comet version before implementation-plan.md finalizes.
- Key design question for implementation-planner: how per-segment timeout (CRITIQUE_TIMEOUT_SECONDS) and per-segment exception isolation are preserved when scoring collapses into one batched call. Current code times out/isolates per segment; the batched call changes that granularity. The plan must state the chosen semantics (e.g. timeout applied around the round vs. per pair, and how a batch-level failure degrades to per-segment "keep draft").
- Assumption: this pass is planning-only. Per the request's explicit STOP instruction, no app/backend/ product code is modified and no backend/frontend/resilience/qa implementation agents run until the user approves implementation-plan.md.

## Context Manifest Draft
<!-- Classifier fills this section. In /cdd-new Step 2.3, Claude copies it verbatim into
     specs/changes/<change-id>/context-manifest.md, replacing the scaffold.
     All paths must be repo-relative. Gate enforces Allowed Paths against agent files-read logs. -->

### Affected Surfaces
- Backend translation pipeline — critique-loop QE (COMET) scoring gate (services/translation_service.py), and the batched scoring service (services/quality_evaluator.py)

### Allowed Paths
<!-- Union of ALL paths any agent will read. Add change-specific paths below the defaults. -->
- specs/changes/batch-critique-qe-scoring/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py
- contracts/business/business-rules.md
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

### Required Contracts
- contracts/business/business-rules.md (read-only; verify adoption-rule invariant, no change expected)

### Required Tests
- tests/test_critique_gate.py (candidate — critique gate / adoption)
- tests/test_quality_evaluation.py (candidate — score_blocks / QE + OOM ladder)

### Agent Work Packets
<!-- One sub-section per required agent (paths must be a subset of Allowed Paths above). -->

#### implementation-planner
- specs/changes/batch-critique-qe-scoring/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py

#### contract-reviewer
- specs/changes/batch-critique-qe-scoring/
- contracts/business/business-rules.md
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py

#### test-strategist
- specs/changes/batch-critique-qe-scoring/
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

#### backend-engineer (deferred)
- specs/changes/batch-critique-qe-scoring/
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

#### e2e-resilience-engineer (deferred)
- specs/changes/batch-critique-qe-scoring/
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

#### qa-reviewer (deferred)
- specs/changes/batch-critique-qe-scoring/
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

### Context Expansion Requests
- (none) — all candidate paths above appear in project-map.md; no reads outside the index are required for planning. If the implementation-planner finds the critique loop delegates to a helper not listed here (e.g. in translation_strategy.py or translation_helpers.py), raise a Context Expansion Request at that point rather than pre-authorizing.
