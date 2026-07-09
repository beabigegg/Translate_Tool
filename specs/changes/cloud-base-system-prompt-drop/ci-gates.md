# CI/CD Gate Plan

## Change ID
cloud-base-system-prompt-drop

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | pull_request | `.github/workflows/contract-driven-gates.yml` L44 `cdd-kit validate --contracts` | exit code 0 |
| targeted provider_fallback | 1 | yes | pull_request | `.github/workflows/contract-driven-gates.yml` L93 `pytest tests/test_provider_fallback.py -x -q` | pass/fail log |
| unit/contract/integration blanket | 1 | yes | pull_request | `.github/workflows/contract-driven-gates.yml` L134 `pytest tests/ -x -q --tb=short --junitxml=…` (job `contract-and-fast-tests`) | junit XML |
| full-regression | 2 | informational (new failures escalate) | pull_request | `.github/workflows/contract-driven-gates.yml` L161 `pytest tests/ -q` (job `full-regression`) | junit XML |

## Workflow Changes Applied
None. No `.github/workflows/*.yml` or Makefile edit is made for this change.

Rationale:
- All new/modified tests (`tests/test_openai_compatible_client.py`,
  `tests/test_orchestrator_context_detection.py`,
  `tests/test_ollama_client_dynamic_strategy.py`) land as new test functions in
  existing files already swept by the blanket `pytest tests/ -x -q` step at
  L134 inside `contract-and-fast-tests` — a merge-blocking, Tier 1 job. No
  file-scoped targeted step is required because none of these three files has
  (or needs) a dedicated fast-fail step; the blanket sweep already runs them
  every PR.
- AC-1 (semiconductor role declaration reaches the outgoing payload) and AC-3
  (base → scenario → few-shot → `Document context:` ordering) are proved by
  `test_orchestrator_context_detection.py::test_cloud_client_delivers_profile_base_system_prompt_semiconductor`
  and `::test_base_prompt_precedes_document_context_preamble_in_composition`.
  Both assert on the mocked `requests.Session.post` `json=` kwarg — a fully
  mocked transport boundary with no live network dependency — so, unlike a
  network-reachable external gate, there is no "might silently skip" hazard:
  the assertion runs deterministically inside the merge-blocking L134 step on
  every PR.
- The fallback-chain construction site (`orchestrator.py` L560) is exercised
  by AC-5 (`test_fallback_chain_client_delivers_profile_base_system_prompt`,
  also new in `test_orchestrator_context_detection.py`, also covered by L134)
  and by the pre-existing L93 targeted `test_provider_fallback.py` step, which
  test-plan.md confirms stays green untouched (additive optional kwarg with an
  `""`-equivalent default requires no test-double edits across its 39
  constructor call sites). No change to L93 is needed.
- No API endpoint, schema, or `contracts/api/api-contract.md` change occurs in
  this change, so `cdd-kit openapi export --check` (L47) is untouched and
  stays green without any regeneration step.
- `cdd-kit validate --contracts` (L44) already performs cross-file contract
  consistency checks (schema-version vs. CHANGELOG entries) as a standing,
  change-agnostic validator — it will fail if BR-110's `business-rules.md`
  schema-version bump (0.27.2 → 0.28.0) is not mirrored by a matching
  `contracts/CHANGELOG.md` entry. This satisfies AC-8 without a new gate.

## Promotion Policy
No gate promotions. No new gate is introduced at any tier; existing Tier 1/2
gates already cover every acceptance criterion (AC-1 through AC-8).

## Rollback Policy
Revert the commit(s) touching `openai_compatible_client.py`,
`orchestrator.py`, and `contracts/business/business-rules.md` (BR-110). No
schema/data migration is introduced, so rollback is a plain code revert with
no forward-compatibility concern.

## Merge Eligibility
mergeable — contingent on the existing Tier 1 gates (`contract-validate`,
targeted `provider_fallback`, and the blanket `pytest tests/ -x -q` step) all
passing green; no new or modified gate is required for this change.
