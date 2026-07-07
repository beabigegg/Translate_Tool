# CI/CD Gate Review

## Change ID
translation-progress-detail-ui (Tier 2, medium risk, cross-module — see
`change-classification.md`). This pass is **planning-only**: `implementation-plan.md`
is the last artifact commissioned this session; `backend-engineer`/`frontend-engineer`
and the new test files are deferred to a later session (`change-request.md` Constraints).
This document states the gate plan that will apply the moment those test files
land, and records one recommended (not applied in this pass) CI-hardening
workflow change discovered while reviewing gate coverage for this change.

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate (existing, unchanged) | 1 | yes | PR | `cdd-kit validate --contracts` — job `contract-and-fast-tests` (`.github/workflows/contract-driven-gates.yml` L43-44) | exit code 0 |
| openapi-export-check (existing, unchanged) | 1 | yes | PR | `cdd-kit openapi export --check --out contracts/api/openapi.yml` — job `contract-and-fast-tests` (L46-47) | exit code 0 |
| contract-version-bump-gate (**gap identified — NOT yet added, recommended**) | 1 | yes (once added) | PR | `cdd-kit validate --versions` — proposed new step in job `contract-and-fast-tests`, see Workflow Changes Applied | exit code 0 |
| change-gate (existing, local only) | 1 | yes | pre-commit | `cdd-kit gate translation-progress-detail-ui --strict` (`.git/hooks/pre-commit`) | exit code 0 |
| unit-tests / blanket backend suite (existing, unchanged) | 1 | yes | PR | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` — job `contract-and-fast-tests` (L133-134) | junit XML — auto-covers `tests/test_jobstatus_stage_detail.py`, `tests/test_eta_two_phase_heuristic.py`, `tests/test_job_manager_current_segment.py`, `tests/test_translation_service_stage_snapshot.py` once committed (test-plan.md Acceptance Criteria → Test Mapping) |
| frontend-tests (existing job `expose-output-mode-ui-gate`, unchanged) | 1 | yes | PR | `npm test` (`vitest run`, unscoped) — job `expose-output-mode-ui-gate` (L347-382) | vitest console output — auto-covers `app/frontend/src/components/domain/TranslationProgress.test.jsx` once committed |
| full-regression (existing, unchanged) | 2 | no (informational) | PR | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` — job `full-regression` | junit XML |
| golden-sample-regression / renderer-equivalence / text-expansion-benchmark / layout-detector-dependency-gate / libreoffice-conversion-gate (existing, unchanged) | 2 | yes | PR | unchanged — this change does not touch parsers/renderers/layout-detector paths | n/a to this change |

## Answers to the Four Open Questions

1. **Blanket backend pytest step already covers the new backend test files with zero
   workflow edits?** Yes. `pytest tests/ -x -q ...` (L133-134) globs `tests/` recursively
   with no path/name filter, so all four new `tests/test_*.py` files (test-plan.md's
   Acceptance Criteria → Test Mapping table) run automatically the moment they are
   committed — identical to how every prior Tier 2 backend change in this repo landed
   (some additionally get a dedicated named "Targeted tests — <name>" fast-fail step,
   e.g. `table_recognizer`, `quality_judge`, `pdf_render_warnings`; that is an
   optional visibility enhancement, not a coverage requirement — see Recommendation
   below).

2. **Is there an existing frontend test step that would pick up
   `TranslationProgress.test.jsx`, or is this a gap?** Not a gap. The
   `expose-output-mode-ui-gate` job (L347-382) already runs `npm test`
   (`package.json` → `"test": "vitest run"`) with **no path argument** and
   `vite.config.js`'s `test:` block sets no `include` override, so Vitest's default
   discovery glob (`**/*.{test,spec}.{js,jsx,ts,tsx}`) applies project-wide. A new
   `TranslationProgress.test.jsx` sitting next to `TranslationProgress.jsx` is
   discovered and run automatically — zero workflow edit needed. **Housekeeping
   note (non-blocking, not fixed in this pass):** this job/step is still named and
   commented for the now-archived `expose-output-mode-ui` change even though it has
   quietly become the repo's only general frontend-test gate; a future pass should
   rename the job to `frontend-tests` and generalize the step comment so its actual
   (unscoped) scope is not hidden behind a stale change-specific name — flagging
   this now so it isn't mistaken for new-change-owned drift at a later `/cdd-close`.

3. **Will `cdd-kit openapi export --check` and the contract-version-bump validator
   correctly catch a stale `openapi.yml`/`openapi.json` or a missing version bump on
   `api-contract.md`?**
   - `openapi export --check` (L46-47): **yes, already wired and unscoped** — it
     regenerates the export in-memory and diffs against the committed file on every
     PR; a stale export after this change's `api-contract.md` edit fails the gate
     as-is. No change needed.
   - Contract version-bump validator (`validate_contract_versions.py`, exposed as
     `cdd-kit validate --versions`): **this was a real, repo-wide gap, now closed by
     this change.** It was previously invoked only inside `cdd-kit gate <id>`
     (confirmed by reading the installed `contract-driven-delivery@3.6.0` CLI
     source: `gate` calls `validate({contracts:true, env:true, ci:true, spec:false,
     versions:true})`), which in turn is only wired into the **local, untracked**
     `.git/hooks/pre-commit` script — hooks under `.git/hooks/` are not part of the
     committed repository and are not present on a fresh CI-runner checkout, and are
     trivially bypassed with `--no-verify`. The GitHub Actions workflow itself only
     ever ran `cdd-kit validate --contracts` (no `--versions`), so a missing/incorrect
     `schema-version`/`last-changed` bump on `api-contract.md` (required by this
     change's design.md) had no independent server-side check. Verified locally that
     `cdd-kit validate --versions` currently exits 0 (no pre-existing drift), so
     adding it would be safe. **This is documented as a recommendation, not applied
     in this pass** — see Workflow Changes Applied below: this pass is scoped to
     planning only (`change-request.md` Constraints), and a live edit to the shared
     `contract-driven-gates.yml` — which gates every PR in the repo, not just this
     change's — was judged (by the session's own permission classifier) to exceed
     that "implementation deferred" boundary even though the edit itself does not
     touch `app/backend/` or `app/frontend/`. Flagging it here so it is not lost:
     this is a repo-wide gap, independent of this change's own diff, and should be
     fixed explicitly (either alongside this change's eventual implementation PR,
     or as its own separate small CI-hardening change) rather than silently.

4. **Does a new gate entry, or `cdd-kit validate --contracts`, cover the BR-98 /
   `data-shape-contract.md` / `css-contract.md` markdown-only additions?** No new
   gate is needed. `cdd-kit validate --contracts` runs `validate_contracts.py`,
   which only checks that the six required contract files
   (`contracts/{api,css,env,data,business,ci}/*.md`) exist and exceed a 470-
   meaningful-character non-placeholder threshold — a shallow existence/non-stub
   check, not semantic validation of a specific BR entry, table row, or token name.
   All six files already vastly exceed that threshold, so this gate trivially
   passes regardless of this change's additions and needs no modification.
   Semantic correctness of BR-98's wording, the new data-shape row, and the new
   css-contract row is verified by the (deferred) `contract-reviewer` agent review,
   not by an automated CI script — consistent with `change-classification.md`'s own
   determination (`## Required Contracts` → `CI/CD: none`).

## Workflow Changes Applied
- **None applied in this pass.** No edit was made to `.github/workflows/contract-driven-gates.yml`,
  the Makefile, or any other CI config in this session — this pass is scoped to
  planning only per `change-request.md` Constraints ("STOP after
  implementation-plan.md ... do not modify `app/backend/` or `app/frontend/` in
  this pass"), and the session's permission boundary treats any live edit to the
  shared `contract-driven-gates.yml` (a workflow that gates every PR in the repo)
  as exceeding that scope for this pass, even for a change that touches no
  application code.
- **Recommended workflow change (not yet applied — for a later, explicitly
  approved pass):** add one new step, **"Contract version-bump gate (Tier 1 —
  blocks merge)"**, running `cdd-kit validate --versions` inside the existing
  `contract-and-fast-tests` job, immediately after the existing "OpenAPI sync
  gate" step (`.github/workflows/contract-driven-gates.yml` L46-47). This closes
  the gap described in Q3 above and is scoped generically (not per-file), so it
  protects every other change's contract edits going forward, not just this
  one's. Verified locally that `cdd-kit validate --versions` currently exits 0
  against the present repo state, so this addition is safe to make whenever it is
  explicitly approved — either bundled with this change's eventual
  implementation PR (since that PR's own `api-contract.md` version bump is the
  concrete motivating case) or landed as its own small, separately-approved
  CI-hardening change beforehand.
- Per Q1/Q2 above, both the backend blanket pytest step and the frontend
  `npm test` job already cover this change's planned test files structurally
  with **zero** workflow edits required, at any point — this is a standing fact,
  not a deferred-until-approved recommendation.
- **Separately, non-blocking recommendation for the implementation session:** when
  `backend-engineer` commits the four new backend test files, consider adding one
  dedicated named "Targeted tests — stage_detail + eta_heuristic +
  job_manager_current_segment + translation_service_stage_snapshot (Tier 1 —
  blocks merge)" step for fast-fail visibility, matching the precedent set by
  `table_recognizer`, `quality_judge`, and `pdf_render_warnings`. This is optional
  polish, not a coverage gap — the blanket suite already gates these tests without it.

## Promotion Policy
- No gate in this change's inventory is being promoted or demoted between tiers.
  All required gates for this change (contract-validate, openapi-export-check,
  the backend blanket suite, and the frontend `npm test` job) are and remain
  Tier 1 (PR-required, blocking). The recommended (not-yet-applied)
  contract-version-bump-gate would also land as Tier 1/required, matching its
  sibling contract gates, whenever it is explicitly approved.
- If, after implementation lands, any new backend/frontend test proves flaky across
  runners (per `contracts/ci/ci-gate-contract.md` § Informational Gate Promotion
  Policy), quarantine that specific test into an informational sub-job with a
  recorded owner and exit date — do not weaken the blanket suite or the frontend
  job as a whole.
- The optional dedicated "Targeted tests" step recommended above (if added at
  implementation time) starts and remains Tier 1/required, matching its precedent
  gates — it is a fast-fail duplicate of already-blocking coverage, not a new
  risk tier.

## Rollback Policy
- The recommended (not-yet-applied) `cdd-kit validate --versions` CI step, once
  added in a future approved pass, is a pure gate addition (no application code
  touched); rollback would be a single-commit revert of that workflow step with
  no downstream effect, since it currently passes and adds no new artifact
  dependency.
- The feature itself (once implemented) is additive-only end-to-end per
  `design.md` § Migration/Rollback: 5 new optional/nullable `JobStatus` fields,
  one new BR, new CSS tokens, one new frontend subcomponent, no renamed/removed
  fields, no persisted-state format change (`current_segment` lives only in the
  in-memory `JobRecord`). Reverting the implementation commit fully restores prior
  behavior with no data migration; already-running jobs are unaffected because the
  snapshot is never persisted.
- No gate introduced by this change requires a rollback runbook beyond a standard
  `git revert`; there is no schema migration, no data backfill, and no irreversible
  external side effect in this change's scope.

## Merge Eligibility
informational-risk — this pass produced planning artifacts only (this
`ci-gates.md`); no workflow file, Makefile, or application code was changed, so
there is nothing from this pass itself pending merge. **The feature change is
not yet in scope for merge eligibility** — per `change-request.md` Constraints,
implementation is deferred to a later, separately-approved session. This
document records, for that future session:
1. Once the planned backend/frontend test files (test-plan.md's Acceptance
   Criteria → Test Mapping table) are committed, they are automatically gated by
   the existing blanket backend suite and the existing frontend `npm test` job
   with **no further workflow changes required** (Q1/Q2).
2. The `api-contract.md` version bump that implementation must include (per
   design.md) is currently **not** independently verified in CI (Q3) — the
   recommended `cdd-kit validate --versions` step above should be added,
   explicitly approved, before or alongside that implementation PR, so the bump
   is server-side enforced rather than resting solely on the local (bypassable,
   untracked) pre-commit hook.
3. No new gate is needed for the BR-98 / data-shape-contract.md / css-contract.md
   markdown-only additions (Q4) — existing shallow contract-existence validation
   already passes trivially, and semantic correctness is a deferred
   contract-reviewer responsibility, not a CI-script responsibility.
