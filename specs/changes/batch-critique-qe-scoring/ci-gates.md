# CI/CD Gate Review — batch-critique-qe-scoring

## Change ID
batch-critique-qe-scoring

Planning-only pass (per `change-request.md` "Constraints" and
`change-classification.md` §Required Agents — `implementation-planner` runs
this pass, `backend-engineer`/`e2e-resilience-engineer`/`qa-reviewer` are
deferred). No product code, no test files, and no workflow file are touched
in this pass. This document is the gate policy that applies once
implementation lands in a later session.

## Required Gates for This Change

| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 2+ | yes | push / pull_request | `cdd-kit validate --contracts` in `contract-and-fast-tests` job (`.github/workflows/contract-driven-gates.yml`) | exit code 0 |
| change-gate | 2+ | yes | pre-commit (already active) / PR (deferred) | pre-commit: `.git/hooks/pre-commit` auto-runs `cdd-kit gate batch-critique-qe-scoring --strict` on any commit touching `specs/changes/batch-critique-qe-scoring/` — no workflow edit needed for this trigger. PR: `cdd-kit gate batch-critique-qe-scoring` step, to be added to `contract-and-fast-tests` job when implementation PR opens (see Workflow Changes below) | exit code 0 |
| unit-tests | 2+ | yes | push / pull_request | `pytest tests/ -x -q --tb=short` (existing blanket step, `contract-and-fast-tests` job) — already executes `tests/test_critique_gate.py`, `tests/test_quality_evaluation.py`, and the new `tests/test_critique_loop_batching.py` once committed, with zero workflow edits | `test-results/junit.xml` (14 days) |
| full-regression | 2 | informational | pull_request | `pytest tests/ -q --tb=short` (existing `full-regression` job) — same auto-coverage of new/extended test files; new failures escalate to merge blocker per existing policy | `test-results/full-regression.xml` (14 days) |
| targeted critique-batching fast-fail (recommended, not contract-required) | 2 | no (recommended) | pull_request | `pytest tests/test_critique_loop_batching.py tests/test_critique_gate.py tests/test_quality_evaluation.py -x -q --tb=short`, to be added in `contract-and-fast-tests` job ahead of the blanket step, mirroring the existing `table_recognizer` / `quality_judge` / `pdf_render_warnings` targeted-step precedent | step log |

## Gates Not Required for This Change

| gate | reason |
|---|---|
| golden-sample-regression, renderer-equivalence, text-expansion-benchmark, layout-detector-dependency-gate, libreoffice-conversion-gate, expose-output-mode-ui-gate | None of these gate the surface touched by this change (`services/translation_service.py` critique loop, `services/quality_evaluator.py` `score_blocks()`); they gate PDF/DOCX/PPTX rendering, layout detection, office-format conversion, and frontend selectors, which are untouched — see `change-classification.md` §Impact Radius (module-level, `services/` only) |
| e2e / real-infra (Tier 3), stress/soak (Tier 4/5), fuzz/monkey (Tier 3/4) | Not required per `change-classification.md` §Required Tests — a wall-clock micro-benchmark is "consideration only," not a merge gate (see `test-plan.md` §Test Families Required, stress row) |
| env-schema-sync, secret-scan, dead-import-assertion (existing steps) | No new/changed env var, no new credential handling, no new import — `change-classification.md` §Required Contracts confirms Env: none, CI/CD: none |
| OpenAPI sync gate | No endpoint/schema change (`change-classification.md` §Required Contracts, API: none) |

## Workflow Changes Applied

**None.** No `.github/workflows/*.yml`, `Makefile`, or CI config file is edited
in this pass. This is consistent with the change-request's explicit scope
limit (STOP after `implementation-plan.md`; no app code or supporting files
change until a later, separately-approved session) and with
`change-classification.md` §Required Contracts (`CI/CD: none`) and the
contract-reviewer/classifier's confirmation that
`contracts/ci/ci-gate-contract.md` has zero references to this call site.

## Workflow Changes Required When Implementation Lands

1. **No edit is required for test execution.** The existing blanket
   `pytest tests/ -x -q --tb=short` step (`contract-and-fast-tests` job) and
   the existing `pytest tests/ -q --tb=short` step (`full-regression` job)
   already glob-discover every file under `tests/`, so
   `tests/test_critique_loop_batching.py` (new) and the extensions to
   `tests/test_critique_gate.py` / `tests/test_quality_evaluation.py` will run
   automatically the moment they are committed — no test-file path needs to
   be added to any workflow step.
2. **Recommended, not required**: add one targeted fast-fail step ahead of
   the blanket `pytest tests/` step, mirroring the existing
   `table_recognizer` / `quality_judge` / `pdf_render_warnings` precedent in
   `contract-and-fast-tests`:
   ```yaml
   - name: Targeted tests — critique_loop_batching + critique_gate + quality_evaluation (Tier 1 — blocks merge)
     # AC-1..AC-8 (batch-critique-qe-scoring): fast-fail before full suite.
     # See test-plan.md for the full AC → test mapping.
     run: >
       pytest
       tests/test_critique_loop_batching.py
       tests/test_critique_gate.py
       tests/test_quality_evaluation.py
       -x -q --tb=short
   ```
   Justification: `test-plan.md` names the integration parity tests "the
   PR-required critical path, since correctness here is the entire point of
   the change," and `change-classification.md` rates this a medium-risk
   change where "a batching bug ... could silently alter document output
   without any error." A targeted fast-fail step gives faster, more legible
   feedback than waiting on the full `pytest tests/` step, but its absence
   would not leave any AC uncovered — the blanket step already runs the same
   tests.
3. **Change-gate CI registration**: per repo precedent
   (`specs/archive/2026/p1-font-lru-cache/ci-gates.md`,
   `specs/archive/2026/p3-llm-judge/ci-gates.md`), an explicit
   `cdd-kit gate batch-critique-qe-scoring` step was historically added to
   `contract-and-fast-tests` at implementation-PR time and removed again at
   `/cdd-close` (see this repo's `CLAUDE.md` promoted-learnings entry on
   grepping the whole workflow file for stale `cdd-kit gate <id>` lines).
   `.github/workflows/contract-driven-gates.yml` currently has zero active
   `cdd-kit gate <id>` lines (header comment: "Active change gates: none"),
   since every prior change has since been archived. The pre-commit hook
   (`.git/hooks/pre-commit`) already satisfies the "pre-commit" trigger of
   the `change-gate` row in `contracts/ci/ci-gate-contract.md` §Gate
   Inventory today, with no code change needed, because it auto-detects any
   commit touching `specs/changes/batch-critique-qe-scoring/` and runs
   `cdd-kit gate batch-critique-qe-scoring --strict` locally. Whether to also
   add the CI-level line is an implementation-PR-time decision, not a
   planning-pass gap.
4. No new job, no new fixture directory, no new `retention-days` policy, no
   new secret, and no OIDC/permissions change are anticipated — this change
   has no artifact, credential, or infra surface (`change-classification.md`
   §Required Contracts: Env/API/CSS/Data all "none").

## Promotion Policy

- No gate is promoted or demoted between tiers by this change. All gates
  remain at their current tier (Tier 2 required: `contract-and-fast-tests`
  blanket unit-tests step; Tier 2 informational: `full-regression`).
- The optional targeted fast-fail step described above, if added at
  implementation time, is additive only (Tier 2, PR-required alongside the
  blanket step) — it does not replace or narrow any existing required check.
- Per `contracts/ci/ci-gate-contract.md` §Informational Gate Promotion
  Policy: if any of the new/extended tests prove non-deterministic across
  runner images (e.g. COMET OOM-ladder timing), the affected sub-check must
  be quarantined to an informational sub-job with owner + exit date rather
  than deleted or weakened — not anticipated here since the plan mocks
  `quality_evaluator.score_blocks()` and the LLM client (`test-plan.md`
  §Notes), so no GPU/network dependency exists in the new tests.

## Rollback Policy

- The batching refactor is confined to `translation_service.py`'s critique
  loop and `quality_evaluator.py`'s `score_blocks()` call pattern — no schema,
  migration, or persisted-state change (`change-classification.md` §Required
  Contracts: Data shape: none). Rollback is a straight file-level `git
  revert` of the implementation commit(s); no data migration, cache flush, or
  feature-flag toggle is required, since `CRITIQUE_LOOP_ENABLED`,
  `CRITIQUE_MAX_ITERATIONS`, and `CRITIQUE_TIMEOUT_SECONDS` defaults are
  explicitly unchanged (`change-request.md` §Non-goals).
- If a post-merge regression surfaces in `full-regression` or in production
  translation output parity (e.g. a segment's adopted draft/revised choice
  differs from pre-refactor behavior), revert the implementation commit,
  confirm `contract-and-fast-tests` is green on `main`, then open a follow-up
  change — do not patch forward under time pressure given the medium-risk
  classification (silent-output-change risk per
  `change-classification.md` §Risk Level).
- Any targeted fast-fail step added per "Workflow Changes Required When
  Implementation Lands" item 2 must be removed at `/cdd-close` alongside any
  `cdd-kit gate batch-critique-qe-scoring` line, per this repo's promoted
  learning on stale per-change workflow lines drifting undetected.

## Merge Eligibility

**informational-risk** (no PR exists yet — this pass is planning-only; no
code, test, or workflow diff is being gated today).

Forward-looking policy for the eventual implementation PR: **mergeable**
once —
1. `contract-and-fast-tests` (Tier 2, required) is green, including the
   existing blanket `pytest tests/ -x -q --tb=short` step, which will cover
   `tests/test_critique_loop_batching.py` and the extended
   `tests/test_critique_gate.py` / `tests/test_quality_evaluation.py` with no
   workflow edit.
2. `cdd-kit gate batch-critique-qe-scoring --strict` passes locally at commit
   time (already enforced today via `.git/hooks/pre-commit`).
3. `full-regression` (Tier 2, informational) shows no new failures relative
   to `main`.
4. AC-1 through AC-8 in `test-plan.md` §Acceptance Criteria → Test Mapping
   all pass — in particular AC-1 (parity) and AC-2 (call-count bound), which
   are the correctness core of this change.

No workflow file edit is a hard blocker to this change reaching a mergeable
PR — the existing required gates already cover its full test surface.
