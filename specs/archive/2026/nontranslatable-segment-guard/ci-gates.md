# CI/CD Gate Plan

## Change ID
nontranslatable-segment-guard

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| contract | 1 | yes | pull_request | `cdd-kit validate --contracts` (existing step in job `contract-and-fast-tests`; validates the BR-107/BR-108 `business-rules.md` 0.25.1→0.26.0 edit) | exit code 0 |
| unit | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (existing blanket step in job `contract-and-fast-tests`; auto-discovers new `tests/test_nontranslatable_segment_guard.py`) | junit XML |
| integration | 1 | yes | pull_request | same blanket pytest step in `contract-and-fast-tests` — fake-client passthrough + meta/refusal-guard integration cases (AC-1, AC-2, AC-6) collected automatically | pass/fail |
| data-boundary | 1 | yes | pull_request | same blanket pytest step — trivial/edge classification cases incl. genuinely-translatable non-passthrough (AC-3, AC-4) collected automatically | pass/fail |
| resilience | 1 | yes | pull_request | same blanket pytest step — meta/refusal fake-client degrade-to-source cases (AC-2, AC-3) collected automatically | pass/fail |
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow (unchanged) | pass/fail |
| build | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow (unchanged) | pass/fail |
| e2e-critical | 1 | no | — | not applicable — backend translation-body path only, no UI/API surface (change-classification.md Tasks Not Applicable 3.3) | — |
| visual | 2 | no | — | no UI surface | — |
| fuzz/monkey | 1/3 | no | — | not applicable (Tasks Not Applicable 3.4) | — |
| stress | 4/5 | no | — | not applicable (Tasks Not Applicable 3.5) | — |
| soak | 4/5 | no | — | not applicable (Tasks Not Applicable 3.5) | — |
| full-regression | 2 | informational | pull_request | existing job `full-regression` (`pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml`) | junit XML |

## New Workflow Changes
None. `.github/workflows/contract-driven-gates.yml` job `contract-and-fast-tests`
already runs `cdd-kit validate --contracts` (covers the BR-107/BR-108
`business-rules.md` edit, schema-version 0.25.1→0.26.0) and the blanket
`pytest tests/ -x -q --tb=short` step, which auto-collects the new
`tests/test_nontranslatable_segment_guard.py` with zero workflow edits.
`full-regression` (Tier 2, informational, PR-triggered) covers the same suite
non-blocking. No new job, secret, or `contracts/ci/ci-gate-contract.md`
gate-inventory row is needed — task 2.6 stays skipped per
change-classification.md.

## Required Check Policy
`contract-and-fast-tests` (job name, PR-required) is the binding check for this
change; `full-regression` (job name) remains informational per existing policy.
No policy change.

## Informational Gate Promotion Policy
Not applicable — no new informational gate introduced; `full-regression` keeps
its existing informational status.

## Rollback Policy
Behavior-only bug-fix; no persisted state, schema, or API-surface change. The
input passthrough and output meta/refusal guard are additive branches inside
the existing `translate_merged_paragraphs` / result-mapping path, reusing the
existing `passthrough`/`failed` dispositions (no new `translation_status` enum
value, no `data-shape-contract.md` edit). A single `git revert` of the diff
fully restores prior behavior with no data-migration or client-compat concern.
No new operational kill-switch is introduced or needed: the classifier is
conservative by design, so any borderline/ambiguous input already falls back
to the pre-existing send-to-LLM path.

## Artifact Retention
No new artifacts. Existing `test-results/junit.xml` / `full-regression.xml`
retention (14 days, set in workflow) is unchanged.

## Merge Eligibility Decision
mergeable — the existing PR-required `contract-and-fast-tests` job (includes
`cdd-kit validate --contracts` for the BR-107/BR-108 edit and the blanket
pytest run collecting `tests/test_nontranslatable_segment_guard.py`) is
sufficient. No new gate, workflow file, or `contracts/ci/ci-gate-contract.md`
edit is required for this change.

## Notes
Test node IDs and the AC → test mapping live in test-plan.md (AC-1..AC-7,
per change-classification.md) once authored by test-strategist; this file
tracks gate policy only. Per CLAUDE.md's fake-update learning, any
`translate_once`/`translate_merged_paragraphs` test double reached by the new
guards must be updated in the same change if call signatures change — an
implementation/test-strategist concern, not a gate.
