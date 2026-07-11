# CI/CD Gate Review

## Required Gates for This Change

| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-and-fast-tests | 1 | yes | push/PR | `.github/workflows/contract-driven-gates.yml` job `contract-and-fast-tests`: `cdd-kit validate --contracts` then `pytest tests/ -x -q` | test-results/junit.xml |
| full-regression | 2 | informational | PR | `.github/workflows/contract-driven-gates.yml` job `full-regression`: `pytest tests/ -q` | test-results/full-regression.xml |
| golden-sample-regression | 2 | yes (blocks PR) | PR | `.github/workflows/contract-driven-gates.yml` job `golden-sample-regression` | n/a |
| renderer-equivalence | 2 | yes (blocks PR) | PR | `.github/workflows/contract-driven-gates.yml` job `renderer-equivalence` | test-results/renderer-equivalence.xml |
| frontend-tests | 1 | yes | PR | `.github/workflows/contract-driven-gates.yml` job `frontend-tests` | n/a |
| live-PANJIT E2E probe | — | no (manual/informational) | manual dispatch only, human-authorized | not in any workflow; run by hand against real PANJIT endpoint | n/a |

No new workflow file or job is added. The new unit/contract/integration/resilience
tests (test-plan.md families: unit, contract, integration, resilience —
`test_openai_compatible_client.py::TestReasoningDirectiveComposition`,
`::TestOutlineReasoningExemption`, `::TestTotalTimeoutConfig`,
`::TestEmbedBounded`, `test_cloud_total_timeout.py`,
`test_orchestrator_context_detection.py`, `test_context_prefix_bleed.py`,
`test_critique_loop_batching.py`, `test_critique_gate.py`) live under `tests/`
and are swept automatically by `contract-and-fast-tests`'s `pytest tests/ -x -q`
and by `full-regression`'s full-suite run — no dedicated job or grep step is
needed since none introduces a new deployment-synced env var or API surface.
`golden-sample-regression`/`renderer-equivalence`/`frontend-tests` are pre-existing
repo-wide PR gates (no path filters in this workflow) unrelated to this change's
backend-only surface; they run and must stay green but require no edits here.

## Workflow Changes Applied

None. Verified against `.github/workflows/contract-driven-gates.yml` (line 3,
"Active change gates: none") that the most recent merged changes (including
`json-structured-translation-io`) did NOT add a per-change `cdd-kit gate <id>`
line or a dedicated job for their new tests — they rely on the same blanket
`pytest tests/ -x -q` / `pytest tests/ -q` sweeps this change also relies on.
`json-structured-translation-io` only added an "Env schema sync" grep step
because it introduced a new deployment-synced flag
(`JSON_STRUCTURED_TRANSLATION_ENABLED`). This change introduces no new
deployment-synced env var: `OPENAI_TOTAL_TIMEOUT_SECONDS` already has a sync
step's coverage via the general env-contract validation (only its default
value changes, not its presence), `CRITIQUE_SKIP_CACHED_SEGMENTS` is a plain
boolean flag with no cross-artifact grep precedent required by other flags of
its kind, and `OPENAI_TRANSLATION_REASONING` is explicitly NOT an env var
(hardcoded constant, per env-contract.md 0.20.0 changelog entry). No new
workflow job, step, or `cdd-kit gate <id>` line is therefore required or added.

Contract-version bumps already in place and verified this run:
- `contracts/business/business-rules.md` schema-version 0.34.0 → 0.35.0 (BR-118,
  BR-119; amends BR-100, BR-109) with a matching `contracts/CHANGELOG.md`
  `[business 0.35.0]` entry.
- `contracts/env/env-contract.md` schema-version 0.19.0 → 0.20.0
  (`OPENAI_TOTAL_TIMEOUT_SECONDS` default change, `CRITIQUE_SKIP_CACHED_SEGMENTS`
  added) with a matching `[env 0.20.0]` entry.
- `cdd-kit validate --contracts` passes (verified live this run: contract, API
  conformance, response-shape, and env-semantic validations all pass).
- No API surface change — `cdd-kit openapi export --check` (existing
  `contract-and-fast-tests` step) needs no regeneration.

## Promotion Policy

Tier 1 (`contract-and-fast-tests`, `frontend-tests`) and the Tier-2-but-PR-blocking
jobs (`golden-sample-regression`, `renderer-equivalence`) gate merge: any failure
blocks the PR. `full-regression` is informational — new failures introduced by
this change must be triaged and escalated to a blocker before merge, per existing
repo policy; pre-existing unrelated failures are not this change's responsibility.
The live PANJIT E2E probe is never promoted into an automated gate: it is
manual/authorized-operator-only evidence and MUST NOT read `docs/TEST_DOC/`
(context-manifest.md forbidden path).

## Rollback Policy

Behavior-only change (design.md §Migration/Rollback) — no schema/API/CI rollback
coordination needed. If a regression surfaces post-merge, revert is a plain code
revert; no workflow file changes to undo since none were made.

## Merge Eligibility

mergeable — contingent on `contract-and-fast-tests`, `frontend-tests`,
`golden-sample-regression`, and `renderer-equivalence` all green, and
`full-regression` showing no new failures attributable to this change.
