# CI/CD Gate Plan

## Change ID
p3-docx-replace-mode

## Required Gates for This Change
| gate | tier | required | trigger | command / workflow | owner | artifact |
|---|---:|---:|---|---|---|---|
| contract-validate | 1 | yes | PR / push-main | `cdd-kit validate --contracts` | platform-team | exit code 0 |
| openapi-sync | 1 | yes | PR / push-main | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | platform-team | exit code 0 |
| change-gate | 1 | yes | PR / push-main | `cdd-kit gate p3-docx-replace-mode` | platform-team | exit code 0 |
| unit-tests | 1 | yes | PR / push-main | `pytest tests/test_output_mode_processors.py -x -q --tb=short` | application-team | junit XML (14 days) |
| contract-tests | 1 | yes | PR / push-main | `pytest tests/test_output_mode_api.py -x -q --tb=short` | application-team | junit XML (14 days) |
| integration-tests | 1 | yes | PR / push-main | `pytest tests/test_output_mode_orchestrator.py -x -q --tb=short` | application-team | junit XML (14 days) |
| full-test-suite | 1 | yes | PR / push-main | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` | application-team | junit XML (14 days) |
| full-regression | 2 | informational | PR only | `pytest tests/ -q --tb=short` (existing `full-regression` job) | application-team | junit XML (14 days) |

### Gate Notes

- **contract-validate** and **openapi-sync** cover AC-8: `api-contract.md` + `openapi.yml` must reflect
  `output_mode` field and version bump (0.6.0 → 0.7.0). Both already run in the existing
  `contract-and-fast-tests` job; no new workflow step required.
- **change-gate** (`cdd-kit gate p3-docx-replace-mode`) covers change artifact completeness. Already
  added to `contract-and-fast-tests` via the step below.
- **unit-tests** covers AC-1 through AC-4 and AC-7 (unit layer).
  See test-plan.md rows: `test_translate_docx_accepts_output_mode_param`,
  `test_translate_pptx_accepts_output_mode_param`, `test_output_mode_default_is_append`,
  `test_append_mode_behavior_unchanged_docx`, `test_append_mode_behavior_unchanged_pptx`,
  `test_replace_mode_docx_no_source_paragraphs_remain`, `test_replace_mode_docx_translation_is_in_place`,
  `test_replace_mode_pptx_no_source_text_frames_remain`, `test_replace_mode_pptx_translation_is_in_place`,
  `test_multi_target_output_mode_clamped_to_append`.
- **contract-tests** covers AC-5: HTTP 422 on invalid `output_mode`, default "append" behavior.
  See test-plan.md rows: `test_post_jobs_accepts_output_mode_*`, `test_post_jobs_rejects_invalid_output_mode_422`.
- **integration-tests** covers AC-6 and AC-7 (orchestrator layer).
  See test-plan.md rows: `test_orchestrator_threads_output_mode_to_translate_docx`,
  `test_orchestrator_threads_output_mode_to_translate_pptx`,
  `test_orchestrator_clamps_replace_to_append_for_multi_target`.
  Anti-tautology: patches at `app.backend.processors.orchestrator.translate_docx` /
  `…translate_pptx` (consumer-module binding), per CLAUDE.md and test-plan.md §AC-6 note.
- **full-regression** is informational; new failures escalate to blocker per existing workflow policy.
- Stress / soak / E2E / visual gates: not applicable per change-classification.md §Tasks Not Applicable.
- No env, secret, or migration changes — tier-floor-override is not required.

## Workflow Changes Applied

Added one step to the existing `contract-and-fast-tests` job in
`.github/workflows/contract-driven-gates.yml`:

```yaml
- name: Change gate — p3-docx-replace-mode (Tier 1 — blocks merge)
  run: cdd-kit gate p3-docx-replace-mode
```

Inserted immediately after the existing `Change gate` step (currently `echo "No active change gates…"`),
replacing that echo with the real gate invocation. The comment on line 3 is updated to list
`p3-docx-replace-mode` as an active change.

No new workflow jobs are needed: all required gates run within the existing `contract-and-fast-tests`
job because `pytest tests/` already executes the new test files when they are committed.

## Promotion Policy

- Tier 0 (local): `pytest tests/test_output_mode_processors.py -x -q` — must pass before pushing.
- Tier 1 gates run on every push to `main` and every PR (`contract-and-fast-tests` job).
- Tier 2 `full-regression` runs on PR only (`if: github.event_name == 'pull_request'`).
- A gate may not be demoted below its tier-floor without a `tier-floor-override` entry in the
  context-manifest with recorded rationale.
- At `/cdd-close`: remove the `cdd-kit gate p3-docx-replace-mode` step and update the comment
  on line 3 to move the change ID to the archived list (per CLAUDE.md promoted learning on archived dirs).

## Rollback Policy

No schema migration or persisted data-shape change is involved. Rollback is code-only.

- Immediate: revert `output_mode` parameter from `translate_docx` / `translate_pptx` signatures;
  behavior returns to "append"-only. The API layer reverts to rejecting the field (or ignoring it
  if the Pydantic schema reverts to strict mode).
- Contract rollback: revert `api-contract.md` version to 0.6.0 and re-export `openapi.yml` in
  the same revert PR.
- CI rollback: remove the `cdd-kit gate p3-docx-replace-mode` step from the workflow in the same
  revert PR.

## Merge Eligibility

blocked until all of the following pass on the PR SHA:

- `contract-and-fast-tests` (includes contract-validate, openapi-sync, change-gate, unit-tests,
  contract-tests, integration-tests, full-test-suite)

informational-risk: `full-regression` is informational; new failures escalate to blocker per
existing workflow policy before merge is approved.
