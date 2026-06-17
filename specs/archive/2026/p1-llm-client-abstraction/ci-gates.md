# CI/CD Gate Plan — p1-llm-client-abstraction

## Required Gates
| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 2 | yes | pre-commit / PR | `cdd-kit validate --contracts` | exit 0 |
| change-gate | 2 | yes | pre-commit / PR | `cdd-kit gate p1-llm-client-abstraction` | exit 0 |
| protocol-conformance | 1 | yes | PR | `pytest tests/test_llm_client_protocol.py -v` | JUnit XML, exit 0 |
| full-regression | 1 | yes | PR | `pytest tests/ -v` | JUnit XML, exit 0 |
| private-method-grep | 2 | informational | PR | `grep -n '_build_no_system_payload\|_call_ollama' app/backend/services/translation_service.py; test $? -eq 1` | exit 1 = pass |

## Gate Notes
- `protocol-conformance` covers test-plan.md rows AC-1, AC-2, AC-6 (Protocol existence, OllamaClient structural conformance, stdlib-only).
- `full-regression` covers test-plan.md rows AC-4, AC-5 (public API unchanged, all existing tests pass unmodified).
- `private-method-grep` enforces AC-3; exits 1 (grep found nothing) = clean; exits 0 (match found) = fail. Informational only — blocks merge when the change-gate `--strict` flag is active.
- No new workflow file is required. Existing gates (`contract-validate`, `change-gate`, `unit-tests`) already run on PR. The two pytest invocations above run inside the existing `unit-tests` job by splitting into two steps.

## Workflow Changes Applied
No new workflow files added. The existing CI pipeline's `unit-tests` job is extended with two named steps:

```
- name: Protocol conformance
  run: pytest tests/test_llm_client_protocol.py -v --junit-xml=reports/protocol.xml

- name: Full regression
  run: pytest tests/ -v --junit-xml=reports/regression.xml
```

The `private-method-grep` check runs as a third step (`continue-on-error: true`) and posts the result as a workflow annotation; it does not block the job but is surfaced in PR checks.

## Promotion Policy
No gate is being promoted between tiers. Existing Tier 2 gates (`contract-validate`, `change-gate`) are sufficient for a Tier 3 refactor with no contract, migration, or dependency change.

## Rollback Policy
Code revert only — `git revert <merge-sha>`. No data migration, schema change, or env-var change exists; rollback requires no coordination outside the backend module. Post-revert, re-run `full-regression` to confirm baseline is restored.

## Merge Eligibility
**Mergeable** when:
1. `contract-validate` exits 0.
2. `change-gate` exits 0 (all required tasks ticked in `tasks.yml`).
3. `protocol-conformance` exits 0 (AC-1, AC-2, AC-6 pass).
4. `full-regression` exits 0 (AC-4, AC-5 pass — all existing tests unmodified).
5. `private-method-grep` confirms zero private-method calls in `translation_service.py` (AC-3).

**Blocked** if any required gate (items 1–5) fails. Item 5 is required for merge despite its informational CI status; AC-3 is a hard acceptance criterion per `change-classification.md`.
