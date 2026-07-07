---
change-id: br92-rescore-resolution
schema-version: 0.1.0
last-changed: 2026-07-07
---

# Implementation Plan: br92-rescore-resolution

Direction: **RETIRE** (user-confirmed; change-request Open Questions, design.md
Direction A). This is a deletion/cleanup change only — remove the phantom BR-92
rescore rule and `QE_RESCORE_THRESHOLD` from every live artifact so contracts,
config, and tests stop claiming behavior no code implements. No product/runtime
behavior changes; no build path.

## Objective

After this change, `QE_RESCORE_THRESHOLD` and the BR-92 "post-job rescore
threshold triggers re-translation" claim exist in zero live artifacts
(contracts, config, env schema/template, tests). A repo-wide sweep of the live
surface returns no residual reference, and every previously-asserting test now
asserts absence. No runtime code path is added or altered — the var was already
inert (change-request Original Request; design.md Migration/Rollback).

## Execution Scope

### In Scope
- Delete BR-92 row from `contracts/business/business-rules.md:104`.
- Delete `QE_RESCORE_THRESHOLD` constant + comment from `app/backend/config.py:133-136`.
- Delete `QE_RESCORE_THRESHOLD` row (`env-contract.md:38`) AND scrub the "post-job
  rescore threshold (AC-2)" clause from the `QE_ENABLED` row (`env-contract.md:37`)
  so no "rescore" substring survives in the file (test-plan.md Notes; test-strategist finding).
- Delete `QE_RESCORE_THRESHOLD` property from `contracts/env/env.schema.json:116-121`.
- Delete `QE_RESCORE_THRESHOLD` comment + sample from `contracts/env/.env.example.template` (lines 68 and 72).
- Correct BOTH stale BR-92 "wired" claims in `contracts/data/data-shape-contract.md`
  — the intro sentence at line 780 and the "Post-job threshold usage" table row at line 787
  (test-strategist found two sites, not just the one design.md flagged).
- Delete 4 tests in `tests/test_quality_evaluation.py`; add 2 absence tests there.
- Invert the 4 `TestQeDefault` presence-tests in `tests/test_env_contract.py`
  into absence-tests under a new `TestQeRescoreThresholdRetired` class; add 2 more; keep the 2 QE_ENABLED tests.
- Author an ADR recording the repo's first formal BR retirement (design.md ADR note) —
  see Handoff Constraints (implementation-stage task, not this planning pass).

### Out of Scope
- Any build path: no rescore→re-translate hook, no re-render/re-archive, no
  `job_manager.py` runtime edits (design.md Direction B; test-plan.md Out of Scope).
- BR-89/90 critique loop (`translation_service.py`), BR-72-77 LLM-judge gate
  (`quality_judge.py`), BR-55/56 dashboard COMET scoring — non-goals, untouched (AC-7).
- `.cdd/code-map.yml` — auto-regenerates; not hand-edited (test-plan.md Out of Scope).
- `specs/archive/**` and sibling `specs/changes/*` narrative docs — historical, excluded from the sweep.
- Any frontend, API, CI/CD, or CSS surface (change-classification Required Contracts/Tests).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | business contract | Delete BR-92 row (`business-rules.md:104`) | backend-engineer |
| IP-2 | config | Delete `QE_RESCORE_THRESHOLD` comment+constant (`config.py:133-136`) | backend-engineer |
| IP-3 | env contract | Delete row 38; scrub "rescore" clause from QE_ENABLED row 37 (`env-contract.md`) | backend-engineer |
| IP-4 | env schema | Delete `QE_RESCORE_THRESHOLD` property (`env.schema.json:116-121`) | backend-engineer |
| IP-5 | env template | Delete comment (line 68) + sample (line 72) (`.env.example.template`) | backend-engineer |
| IP-6 | data-shape contract | Correct BR-92 claims at BOTH `data-shape-contract.md:780` and `:787` | backend-engineer |
| IP-7 | unit tests | Delete 4 rescore tests; add 2 absence tests (`tests/test_quality_evaluation.py`) | test-engineer |
| IP-8 | contract tests | Invert 4 presence tests → `TestQeRescoreThresholdRetired`; add 2; keep 2 QE_ENABLED (`tests/test_env_contract.py`) | test-engineer |
| IP-9 | regression sweep | Repo-wide `grep -rn QE_RESCORE_THRESHOLD` on live surface returns nothing after IP-1..IP-8 | test-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | AC→Test Mapping table (rows AC-4/AC-2/AC-6/AC-3) | test files/node ids to add or invert |
| test-plan.md | Test Update Contract table | which existing tests delete vs delete→replace |
| test-plan.md | Notes (lines 55-66) | exact live-reference list; env-contract:37 scrub rule; data-shape 780+787 |
| design.md | Direction A — Retire | edit set, cost, compatibility (env var not covered by deprecate-2-minors) |
| design.md | ADR note (lines 88-94) | first-BR-retirement ADR required at implementation time |
| design.md | Open Risks (lines 104-115) | data-shape-contract.md:787 stale-claim gap (now CER-001 approved) |
| change-classification.md | Required Contracts / Inferred AC (AC-2..AC-7) | scope + coherence guarantees |
| context-manifest.md | Allowed Paths + CER-001 approved | read/write boundary (data-shape-contract.md added) |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| contracts/business/business-rules.md | delete | Remove entire BR-92 row at line 104. Do NOT touch BR-91 or BR-93. No renumbering. |
| app/backend/config.py | delete | Remove comment lines 133-135 + constant line 136. Leave `QE_DEVICE` (132) and `CRITIQUE_LOOP_ENABLED` (138+) intact. |
| contracts/env/env-contract.md | edit | Line 38: delete the whole `QE_RESCORE_THRESHOLD` table row. Line 37: rewrite the QE_ENABLED cell to drop "and post-job rescore threshold (AC-2)"; verify substring "rescore" no longer appears anywhere in the file. |
| contracts/env/env.schema.json | delete | Remove the `"QE_RESCORE_THRESHOLD": {...}` property block (lines 116-121). Keep JSON valid — the preceding `QE_ENABLED` block (110-115) ends with `}`; ensure trailing comma/braces stay well-formed after removal. |
| contracts/env/.env.example.template | delete | Remove line 68 (`# QE_RESCORE_THRESHOLD: ... (AC-2).`) and line 72 (`#QE_RESCORE_THRESHOLD=0.5`). Keep QE_ENABLED/QE_MODEL_NAME/QE_DEVICE lines. |
| contracts/data/data-shape-contract.md | edit | Line 780: drop "and the post-job rescore threshold check (BR-92)" so the sentence names only the critique adoption gate (BR-89). Line 787: delete the "Post-job threshold usage" table row (its entire content is the false BR-92/CER-002 wiring claim). |
| tests/test_quality_evaluation.py | edit | DELETE `test_below_threshold_triggers_retranslation` (538), `test_threshold_env_var_parsed_as_float` (559), `test_rescore_threshold_has_correct_type_and_default` (604), `test_rescore_threshold_out_of_range_rejected` (616). ADD `test_qe_rescore_threshold_not_in_config` (assert `not hasattr(config, "QE_RESCORE_THRESHOLD")`) and `test_br_92_removed_from_business_rules` (assert "BR-92" / "rescore" absent from business-rules.md). Keep `test_qe_enabled_config_default_is_true` (581). |
| tests/test_env_contract.py | edit | In `TestQeDefault`: DELETE the 4 presence tests (164,173,188,197). ADD new class `TestQeRescoreThresholdRetired` with `test_qe_rescore_threshold_removed_from_contract`, `_removed_from_schema`, `_removed_from_env_template`, `_removed_from_config` (inverted assertions). ADD `test_env_contract_qe_enabled_row_scrubbed_of_rescore_claim` (assert "rescore" not in contract text) and `test_qe_rescore_threshold_zero_references_repo_wide` (live-surface grep, excluding specs/archive + specs/changes narrative + .cdd/code-map.yml). KEEP `test_qe_enabled_default_true_in_contract` (148) and `test_qe_enabled_default_true_in_config` (208). |

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: delete `QE_RESCORE_THRESHOLD` from `env-contract.md`, `env.schema.json`,
  `.env.example.template`; scrub "rescore" clause from the QE_ENABLED row.
  Env-var removal is NOT a policy-defined breaking change — `deprecate-2-minors`
  is API-field-scoped only, and the var is operationally inert (design.md Direction A Compatibility).
- Data shape: correct the two stale BR-92 "wired" claims in `data-shape-contract.md:780,787`.
- Business logic: delete BR-92 (`business-rules.md:104`).
- CI/CD: none.

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-4 | tests/test_quality_evaluation.py::test_qe_rescore_threshold_not_in_config | `hasattr(config, "QE_RESCORE_THRESHOLD")` is False |
| AC-4 | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_contract | "QE_RESCORE_THRESHOLD" absent from env-contract.md |
| AC-4 | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_schema | property absent from env.schema.json |
| AC-4 | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_env_template | var absent from .env.example.template |
| AC-4 | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_config | var absent from config.py |
| AC-2 | tests/test_quality_evaluation.py::test_br_92_removed_from_business_rules | "BR-92" row absent from business-rules.md |
| AC-2 | tests/test_env_contract.py::test_env_contract_qe_enabled_row_scrubbed_of_rescore_claim | "rescore" substring absent from env-contract.md |
| AC-6 | tests/test_env_contract.py::test_qe_rescore_threshold_zero_references_repo_wide | zero live-surface references (excludes archive/narrative/code-map) |
| AC-3 | tests/test_env_contract.py::TestQeDefault::test_qe_enabled_default_true_in_contract | unchanged — QE_ENABLED default still "true" (regression guard) |
| AC-2 (data-shape) | contracts/data/data-shape-contract.md | manual contract-review at gate (lines 780,787 no longer claim BR-92 wiring) — no pytest |

Required test phases (floor): `collect`, `targeted`, `changed-area`. Add
`contract` — this change edits contract files (business-rules, env-contract,
env.schema.json, .env.example.template, data-shape-contract), so the contract
phase trigger applies. Implementation agents generate evidence with
`cdd-kit test run`; the gate validates `test-evidence.yml`. Full ladder lives in
test-plan.md / references/sdd-tdd-policy.md — not restated here.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- ADR authoring (design.md ADR note) is a required implementation-stage task —
  first formal BR retirement in this repo. It is NOT written in this planning
  pass. The implementing agent must add the ADR (retire convention rationale +
  `git revert` rollback) before the change is gate-ready.
- Deletions must be surgical: no renumbering of surviving BRs, no reflow of
  unrelated contract rows, no opportunistic refactor of neighbouring config/env entries.
- After IP-8, run IP-9 sweep and confirm `test_qe_rescore_threshold_zero_references_repo_wide` passes.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- **No file-region overlap with the 3 sibling QA changes** — `qa-judge-provider-consistency`
  and `qa-judge-hang-recovery` touch `job_manager.py`'s judge call site and
  `quality_judge.py`; `batch-critique-qe-scoring` touches the QE batching path. This
  change touches `config.py:133-136`, `business-rules.md:104`, `env-contract.md:37-38`,
  `env.schema.json`, `.env.example.template`, `data-shape-contract.md:780,787`, and two
  test files only — none of the sibling edit regions. It can land independently, in any
  order, without merge conflict.
- **env.schema.json is JSON** — deleting the property must preserve valid JSON
  (trailing comma/brace balance). A malformed file breaks the whole env-contract test module, not just one assertion.
- **Two data-shape sites, not one** — design.md originally flagged only line 787;
  test-strategist found line 780 also cites BR-92. Missing either leaves a stale claim (AC-6 fails).
- **env-contract.md:37 substring scrub** — the AC-2 test asserts "rescore" is
  absent from the WHOLE file, so deleting row 38 alone is insufficient; the
  QE_ENABLED row wording must also change.
- **Downstream doc dependency** — sibling `qa-mechanism-docs` depends on this
  change completing first (change-request Known Context); it reflects final
  post-retire behavior. Not blocking this plan, but the retire must land before that doc work.
