# CI/CD Gate Plan

## Change ID
support-legacy-office-formats

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| contract-and-fast-tests (existing, unchanged) | 1 | yes | pull_request | `.github/workflows/contract-driven-gates.yml` job `contract-and-fast-tests` | junit XML; covers full `pytest tests/` run including `.doc`/`.xls`/`.ppt` orchestrator branches — those branches MUST use `@pytest.mark.skipif(not is_libreoffice_available(), ...)` per AC-4 so this required job never fails due to LibreOffice absence |
| libreoffice-conversion-gate (new) | 2+ | yes | pull_request | `.github/workflows/contract-driven-gates.yml` job `libreoffice-conversion-gate` — `pytest tests/test_libreoffice_helpers.py --tb=short -q` | junit XML; pass or graceful skip per `contracts/ci/ci-gate-contract.md` §LibreOffice Conversion Gate |
| contract-validate (existing, unchanged) | 2+ | yes | pull_request | `cdd-kit validate --contracts` | exit code 0 — validates `contracts/api/api-contract.md`, `contracts/env/env-contract.md`, `contracts/business/business-rules.md`, `contracts/ci/ci-gate-contract.md` deltas for this change |
| openapi-sync (existing, unchanged) | 2+ | yes | pull_request | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | exit code 0 — required because AC-8 changes the accepted-upload-types contract |
| visual (drop-zone copy) | 2 | informational | pull_request | agent-log evidence (`agent-log/visual-reviewer.yml`) per test-plan.md visual row | pass/fail note; no dedicated CI job — text/whitelist-only UI change per change-classification.md |

## New Workflow Changes

Applied directly in `.github/workflows/contract-driven-gates.yml`:
- New job `libreoffice-conversion-gate` (PR-triggered, `ubuntu-latest`): installs Python, attempts `sudo apt-get install -y libreoffice-core` with `continue-on-error: true` (a failed/unavailable install must never redden the gate — it only affects whether real-binary tests run or skip), then runs `pytest tests/test_libreoffice_helpers.py --tb=short -q --junitxml=...` and uploads the junit artifact (`retention-days: 14`, consistent with sibling gates).
- Active-change-gates comment header updated to list `support-legacy-office-formats`.
- No change to the existing `contract-and-fast-tests` job's `pytest tests/ -x -q` step — it already picks up `tests/test_orchestrator_phase0.py`'s new `.doc`/`.xls`/`.ppt` branches. This is why AC-4's skip-vs-fail semantics for real-binary branches are load-bearing for the whole required job, not just the new gate.

## Decision: apt-get install-now vs. defer

**Decided now, not deferred.** The `libreoffice-core` install step is added to the workflow in this change (see above), not left as a backend-engineer/ci-cd-gatekeeper follow-up. Rationale: the install is a single well-known Debian package (`libreoffice-core`, no PPA/network-fetch-at-test-time risk beyond the standard apt mirror already used by `ubuntu-latest` runners), it is wrapped in `continue-on-error: true` so it carries zero risk of spuriously failing the gate, and deferring it would mean the real `.doc`/`.xls`/`.ppt` conversion path is *never* exercised in CI until an unspecified future PR — silently shipping AC-1/AC-2 with zero real-binary CI coverage. The only thing genuinely deferred to backend-engineer is authoring the `@pytest.mark.skipif` markers and the mocked degrade-path test inside `tests/test_libreoffice_helpers.py` itself (implementation, not CI plumbing).

## Required Check Policy
All gates in the Required Gates table above marked `required: yes` must pass before this PR is eligible to merge, per `contracts/ci/ci-gate-contract.md` § Required Check Policy. The `libreoffice-conversion-gate` job's required status is satisfied by either a pass or a clean skip of the real-binary tests — a skip is not a failure. Only a genuine test failure (assertion error, or the mocked degrade-path sub-test failing/being skipped) blocks merge.

## Informational Gate Promotion Policy
No new non-deterministic sub-check is introduced by this change. If glyph/font or subprocess-timing non-determinism is later observed in `libreoffice-conversion-gate` across runner images, quarantine per `contracts/ci/ci-gate-contract.md` § Informational Gate Promotion Policy (owner + exit date) rather than disabling the gate.

## Rollback Policy
Per design.md § Migration/Rollback: this change is purely additive. CI rollback mirrors code rollback — reverting `.ppt`/`.doc`/`.xls` from `SUPPORTED_EXTENSIONS` and `ACCEPTED_EXTENSIONS` stops new legacy uploads without requiring a workflow change. If `libreoffice-conversion-gate` proves persistently unreliable in CI (not the application), the gate itself can be demoted from required to informational via a follow-up CI-gate-contract change — this is not authorized preemptively here.

## Artifact Retention
`libreoffice-conversion-gate` junit XML: `retention-days: 14`, matching all sibling PR-gate artifacts in this workflow (e.g. `renderer-equivalence-results`, `text-expansion-benchmark-results`).

## Merge Eligibility Decision
mergeable — contingent on: (1) `tests/test_libreoffice_helpers.py` existing with the required skipif/unconditional-mocked-test split (test-strategist/backend-engineer, see test-plan.md), (2) `tests/test_orchestrator_phase0.py`'s new legacy branches following the same skip semantics so the existing required `contract-and-fast-tests` job is not put at risk, (3) `cdd-kit openapi export --check` passing after AC-8's contract edits. No new Tier 0/1 gate is required — this change does not touch auth, payments, or DB migration surfaces (per change-classification.md Tier rationale).

## Notes
Full test → AC mapping lives in test-plan.md (authored in parallel by test-strategist — see its Acceptance Criteria → Test Mapping table; not duplicated here). Business rule for lossy-conversion disclosure: BR-9 (amended) / BR-96, see `contracts/business/business-rules.md`. External-dependency semantics: `contracts/env/env-contract.md` § External Binary Dependencies.
