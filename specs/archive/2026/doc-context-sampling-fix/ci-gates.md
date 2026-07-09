# CI/CD Gate Plan

## Change ID
doc-context-sampling-fix

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contracts-validate | 1 | yes | pull_request | `cdd-kit validate --contracts` (contract-and-fast-tests job, `.github/workflows/contract-driven-gates.yml`) — validates BR-109 sub-rule and business-rules.md 0.27.0→0.27.1 bump, CHANGELOG.md entry | job pass/fail |
| unit+integration+data-boundary (blanket) | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (contract-and-fast-tests job) — auto-collects all new tests in `tests/test_orchestrator_context_detection.py`, test-plan.md AC-1..AC-8 | test-results/junit.xml (14d) |
| full-regression | 2 | informational | pull_request | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` (full-regression job) | full-regression.xml (14d) |
| libreoffice-conversion-gate | 2 | yes | pull_request | `pytest tests/test_libreoffice_helpers.py --tb=short -q` (unchanged pytest target — see rationale below) | libreoffice-conversion-gate.xml (14d) |

No Tier 0/4/5 gates apply: no local-only fast gate separate from the PR gate,
no weekly soak (a sampling-path bug fix is not a load profile), no manual
production-like dispatch beyond the existing `workflow_dispatch`/`schedule`
triggers already on the workflow. `tasks.yml` 6.4 is skipped accordingly.

## Risk Analysis: proving AC-1 and AC-7 without a silent skip

Per test-plan.md (integration row; Notes), the AC-1/AC-7/AC-8 integration
tests (`test_process_files_context_detected_for_legacy_xls`,
`test_xls_sampling_does_not_double_convert_via_libreoffice`,
`test_legacy_xls_and_table_only_docx_both_emit_context_detected`) mock the
LibreOffice boundary at `subprocess.Popen` — the same boundary
`test_libreoffice_helpers.py::_FakePopen` uses — never at `xls_to_xlsx`'s
internals, and carry **no** real-binary `skipif`. So they exercise the real
`.xls`-sampling code path with a faked process boundary and need no `soffice`
binary at all. Consequence: `contract-and-fast-tests`'s blanket
`pytest tests/ -x -q` step (Tier 1, PR-required) runs AC-1/AC-7/AC-8
unconditionally, even on a runner with LibreOffice absent. **That job — not
`libreoffice-conversion-gate` (which tolerates a failed apt-get install via
`continue-on-error: true`) — is what actually proves these ACs.** The AC-2/AC-3
unit tests (token-specific, not mere non-emptiness) run in the same step.

**Decision: do not add `tests/test_orchestrator_context_detection.py` to
`libreoffice-conversion-gate`'s pytest target.** That job's `skipif` convention
exists for tests needing the *real* `soffice` binary; this change's tests
avoid that dependency by design, so adding the file there would only
re-execute the same mocked assertions without adding real-binary coverage. No
`.github/workflows/contract-driven-gates.yml` edit is required.

## Workflow Changes Applied
None. The mocked-`Popen`-boundary design already yields a non-skippable,
merge-blocking assertion for every AC (AC-1..AC-8) inside the existing Tier 1
`contract-and-fast-tests` job (see Risk Analysis). No new dependency,
lockfile, migration, endpoint, or secret is introduced (change-classification.md
Required Contracts: all "none"). `cdd-kit validate --contracts` (already
required) picks up the business-rules.md 0.27.0→0.27.1 bump and CHANGELOG.md
entry with no config change. The `.xls` fixture is a small committed binary
read at test time, not network-fetched.

## Required Check Policy
`contract-and-fast-tests` (job name, PR-required) is the binding check for
this change; `libreoffice-conversion-gate` stays required but unchanged and
does not carry the burden of proving AC-1/AC-7/AC-8 (see Risk Analysis);
`full-regression` stays informational per existing policy. No policy change.

## Informational Gate Promotion Policy
Not applicable — no new informational gate introduced; `full-regression`
keeps its existing informational status.

## Rollback Policy
`git revert` of the merge commit. Behavior is fully flag-independent (no new
flag; `CONTEXT_DETECTION_ENABLED`/`QWEN_CONTEXT_FLOW_ENABLED` unchanged) and
the fix degrades gracefully on sampling failure (AC-6) — no migration, no
schema, no irreversible state to unwind.

## Artifact Retention
No new artifacts. Existing `test-results/junit.xml` / `full-regression.xml` /
`libreoffice-conversion-gate.xml` retention (14 days, set in workflow) is
unchanged.

## Merge Eligibility Decision
mergeable — contingent on `contract-and-fast-tests` passing (blanket pytest
run covers AC-1..AC-8 unconditionally via the mocked-`Popen` boundary) and
`cdd-kit validate --contracts` passing against the bumped business-rules
contract. `libreoffice-conversion-gate` stays required but unchanged;
`full-regression` remains informational per existing Tier 2 policy.

## Notes
Test node IDs and the full AC → test mapping live in test-plan.md; this file
tracks gate policy only. If a future change adds a real-`soffice`-dependent
assertion for this sampling path, that change's ci-gates.md — not this one —
decides whether to extend `libreoffice-conversion-gate`'s pytest target.
