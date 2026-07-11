# CI/CD Gate Review

## Change ID
truncation-length-guard

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | PR | `cdd-kit validate --contracts` (`contract-and-fast-tests`) | exit code 0 |
| unit-tests (blanket sweep) | 1 | yes | PR | `pytest tests/ -x -q` (`contract-and-fast-tests`) | junit XML |
| full-regression | 2 | yes | PR | `pytest tests/ -q` (`full-regression`) | junit XML — AC-7 evidence |
| golden-sample-regression | 2 | yes | PR | existing `golden-sample-regression` job | per-sample diff |
| local pre-PR (Tier 0) | 0 | advisory | local | command sequence below | terminal output |

No new gate is added. `tests/test_length_guard.py` is a plain pytest file
under `tests/`, collected automatically by the existing `pytest tests/ -x -q`
step and by `full-regression`'s `pytest tests/ -q`. See test-plan.md's Test
Execution Ladder and AC→test mapping for phase-by-phase local commands.

## Workflow Changes Applied
None — no `.github/workflows/*.yml` edit, no Makefile target, no new job.
- Env: none — `k`/`a`/`b`/`MIN_SOURCE_CHARS` are `config.py` constants, not
  env vars (change-classification.md §Required Contracts); no env-schema /
  `.env.example` sync step applies.
- CI/CD contract: `none` per change-classification.md; tasks 2.6/4.4
  (contract/workflow edit) explicitly skipped.
- A dedicated targeted-test step for `test_length_guard.py` is deliberately
  NOT added — it would deepen a documented, thrice-recurring drift (stale
  per-change steps surviving archival). The blanket sweep already covers new
  test files with zero added surface to forget at close-out.

## Drift Check (fresh, this review)
- `tests/test_length_guard.py` confirmed absent pre-implementation.
- No `cdd-kit gate <archived-id>` line exists in `contract-driven-gates.yml`
  (that command is local/pre-commit per ci-gate-contract.md, not a CI step).
- All named jobs (`golden-sample-regression`, `text-expansion-benchmark`,
  `renderer-equivalence`, `layout-detector-dependency-gate`,
  `libreoffice-conversion-gate`, `frontend-tests`) are permanent/generic
  gates — none scope a targeted step to an already-archived change-id.
- The 3 env-schema-sync steps (`DEEPSEEK_ENABLED`/`TERM_EMBEDDING_*`,
  `JUDGE_*`, `JSON_STRUCTURED_TRANSLATION_ENABLED`) remain because those
  env vars are still live config — correctly kept, not stale.
- Minor finding (documentation-only, out of this change's scope): the header
  `archived:` comment list (line 3) omits two change-ids already moved to
  `specs/archive/2026/` (`json-structured-translation-io`,
  `cloud-base-system-prompt-drop`). No functional gate/step is affected; flag
  for the next close-out rather than editing the workflow now.
- No other stale targeted-test step found.

## Local Pre-PR Command Sequence (conda-scoped, `translate-tool` env)
```
conda run -n translate-tool pytest tests/test_length_guard.py -q
conda run -n translate-tool pytest tests/test_docx_nested_tables.py -k truncat -q
conda run -n translate-tool pytest tests/test_json_translation_body.py -k length_guard -q
conda run -n translate-tool pytest tests/ -q   # full-suite regression, AC-7 evidence
```
Mirrors test-plan.md's ladder (collect → targeted → changed-area → full); CI
reruns the same commands (minus conda) in `contract-and-fast-tests` /
`full-regression`.

## AC-7 Regression Note
`test_table_context_translation.py` and `test_docx_nested_tables.py` fixture
cells are all sourced under `MIN_SOURCE_CHARS = 15` (test-plan.md
"Existing-fake sweep"), so the guard's fail-safe means these fixtures never
trip it — both stay green under the blanket sweep with no edits. The
`full-regression` `pytest tests/ -q` run is the durable evidence that
non-truncated existing output is unaffected.

## Required Artifact Note
`monkey-test-report.md` (Tier 1, per change-classification.md) is a required
artifact but NOT a CI gate — adversarial false-positive-boundary evidence
authored by monkey-test-engineer and reviewed by qa-reviewer outside the
pipeline; it does not gate a CI job.

## Promotion Policy
No promotions. No new gate at any tier; existing Tier 1/2 gates
(`contract-and-fast-tests`, `full-regression`, `golden-sample-regression`)
absorb this change's tests unmodified. Nothing quarantined — the guard's
tests are deterministic pure-function/mocked-seam tests.

## Rollback Policy
Additive module + one call-site, no flag, safe-by-default (BR-68 exemption +
fail-safe design). Rollback is a plain revert; no migration, no env var. If
design.md added/repurposed an IR marker, confirm no residual data-shape
consumer before revert. No special rollback gate beyond revert +
`full-regression` rerun.

## Merge Eligibility
mergeable — contingent on all Tier 1 gates above passing (including
`test_length_guard.py` inside the blanket sweep), qa-reviewer sign-off, and
the monkey-test-report.md artifact per change-classification.md.
