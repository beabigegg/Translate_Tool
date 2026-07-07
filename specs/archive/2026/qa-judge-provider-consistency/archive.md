# Archive: qa-judge-provider-consistency

## Change Summary
The judge/QA re-translation callback (`_translate_fn` in `job_manager.py`) reused
`last_client` — the main-translation winner from `model_router`'s fallback chain —
with a silent `OllamaClient(DEFAULT_MODEL)` fallback. Because `last_client` is reset
to `None` at the end of every route-group loop (before the judge hook runs), the
re-translation path **always** fell through to a hardcoded local Ollama default
model, never the provider that actually scored the block. This change routes QA
re-translation through the judge's own provider via a new cached
`QualityJudge.translation_client` (BR-98). First of the judge-subsystem chain (2→3).

## Final Behavior
When the judge pass runs (not skipped by BR-97), QA re-translation executes on the
judge's own provider: cloud → `JUDGE_CLOUD_PROVIDER_ID` provider using its
`providers.yml` `models.translate` role (falling back to `JUDGE_MODEL`); ollama →
local `OllamaClient(JUDGE_MODEL)`. The already-panjit deployment case is a
request-for-request no-op (same provider + `gpt-oss:120b` translate model as before).
The `last_client is None → OllamaClient(DEFAULT_MODEL)` fallback is gone.

## Final Contracts Updated
- `contracts/business/business-rules.md` — BR-98 (judge-retranslation-provider-consistency)
  added after BR-97; Table U row added; Table U header extended to "(…, BR-98)".
- `contracts/env/env-contract.md` — `(BR-98)` cross-refs appended to `JUDGE_PROVIDER`
  and `JUDGE_CLOUD_PROVIDER_ID` description cells (review-only prose; no new var).

## Final Source Changed
- `app/backend/services/quality_judge.py` — `_build_cloud_client(self, model=None)`;
  new cached `translation_client` property (never None).
- `app/backend/services/job_manager.py` — `_translate_fn` rewritten to
  `_judge.translation_client.translate_once(...)`; `OllamaClient(DEFAULT_MODEL)`
  fallback removed; `OllamaClient`/`DEFAULT_MODEL` imports retained (used elsewhere).

## Final Tests Added / Updated
- `tests/test_quality_judge.py` — 6 unit tests: cloud provider+`models.translate`
  resolution, model-may-differ-same-provider, `JUDGE_MODEL` fallback, no-new-config-symbol,
  cached-built-once, never-None (cloud + ollama).
- `tests/test_orchestrator_judge.py` — 3 integration tests with a `run_judge_loop`
  `side_effect` that actually invokes `translate_fn` (anti-tautology): uses
  translation_client not last_client, request-params preserved, no OllamaClient(DEFAULT_MODEL)
  fallback; + strengthened `test_judge_skipped_when_provider_is_deepseek`.
- 60 judge-group tests green; 86 provider/client/router regression tests green (torch env).

## Final CI/CD Gates
No workflow edits (existing judge test group + full pytest cover the new tests). PR #15
CI: all required gates green.

## Production Reality Findings
- `last_client` is unconditionally reset to `None` before the judge hook, so the old
  re-translation path never used the winning provider at all — the "reuse last_client"
  comment was misleading; the real prior behavior was always the local Ollama default.
- `cdd-kit gate` tier-floor false-positive again: matched "endpoint / route / session"
  vocab despite zero critical surface (backend refactor, no new endpoint/var/schema).

## Lessons Promoted to Standards
1. **[fold-into-existing, net 0 lines]** `CLAUDE.md` cdd-kit:learnings — extended the
   tier-floor false-positive trigger list with `"route"` (evidence: this change's gate
   output "matched: endpoint, route, session"). Continues the #1 addition of
   "breaking change" / "session".
- No new mock-boundary lesson: the definition-module patch target and the
  run_judge_loop-side_effect anti-tautology pattern are already covered by existing
  CLAUDE.md entries (mock.patch binding rule; tautological-tests wrong-entry-point form).

## Follow-up Work
`qa-judge-hang-recovery` (#3) rebases onto this change — it edits the same
`_translate_fn` / `run_judge_loop` region and adds cancellation/timeout on top of the
finalized `translation_client` shape.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
