# CI/CD Gate Review

## Change ID: p1-cloud-providers

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | pull_request | `cdd-kit validate --contracts` | exit code 0 |
| change-gate | 1 | yes | pull_request | `cdd-kit gate p1-cloud-providers` | exit code 0 |
| unit-tests | 1 | yes | pull_request | `pytest tests/ -x -q` | junit XML |
| contract-conformance | 1 | yes | pull_request | `pytest tests/ -x -q -k "contract"` | junit XML |
| integration | 1 | yes | pull_request | `pytest tests/ -x -q -k "integration"` | junit XML |
| resilience | 1 | yes | pull_request | `pytest tests/ -x -q -k "resilience"` | junit XML |
| data-boundary | 1 | yes | pull_request | `pytest tests/ -x -q -k "data_boundary"` | junit XML |
| secret-scan | 1 | yes | pull_request | `grep -rn --include="*.py" --include="*.yml" --include="*.yaml" -E "(PANJIT_API\|DEEPSEEK_API)\s*[:=]\s*[A-Za-z0-9+/]{20,}" . --exclude-dir=.git` | zero matches |

## Informational Gates (run, do not block merge)
| gate | tier | trigger | command/workflow | artifact |
|---|---:|---|---|---|
| full-regression | 2 | pull_request | `pytest tests/ -q` | junit XML; any new failure escalates to blocker |
| env-template-check | 2 | pull_request | `grep -l "PANJIT_API\|DEEPSEEK_API" contracts/env/.env.example.template` | file must be listed |

## Manual Gates (Tier 5)
| gate | tier | trigger | command/workflow |
|---|---:|---|---|
| cloud-smoke-test | 5 | manual — once before first production deploy | Run full translation via Panjit endpoint using real `.env` vars; confirm `JobStatus.provider` equals `panjit` |

## Workflow Changes Applied
The existing `.github/workflows/contract-driven-gates.yml` `contract-and-fast-tests` job placeholder step has been replaced with concrete pytest commands covering all Tier 1 gates listed above. See that file for the updated step definitions.

## Required Check Policy
Branch protection must bind to the named job `contract-and-fast-tests` (the job `name:` field). All Tier 1 gates run in that job; the job must be green for merge eligibility.

## Promotion Policy
- No gate may be promoted from Tier 2 to Tier 1 without updating this file and the workflow in the same PR.
- Downstream changes (`p1-provider-routing`, `p1-observability-metrics`) must not start until all Tier 1 gates for this change pass on the merge commit.

## Rollback Policy
- If the merge commit breaks the full-regression gate, revert the merge commit immediately.
- With `providers.yml` absent or all providers disabled, `config.py` and `model_router` must fall back to Ollama-only; this self-healing path removes the need for a schema rollback in most cases.
- Hard rollback: delete `openai_compatible_client.py`, revert `model_router.py`, remove `provider` field handling; no data migration required (the `provider` field on `JobStatus` defaults to `None`).

## Merge Eligibility
blocked until all Tier 1 gates pass AND secret-scan returns zero matches
