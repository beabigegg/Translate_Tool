# Archive: qa-judge-hang-recovery

## Change Summary
Fixes a live incident: a job hung 30+ min inside one LLM-judge cloud scoring call,
recoverable only by killing the backend. Root cause — the judge loop never checked
`job.stop_flag`, and `OpenAICompatibleClient`'s `(connect, read)` timeout tuple
bounds only the inter-chunk gap, so a provider dribbling keep-alive bytes hangs
forever. Adds two cooperating mechanisms: a wall-clock total-duration ceiling on
every cloud completion (BR-100) and a cancel-aware judge loop that degrades to
`judge_status="stopped"` (BR-99). Third and final change of the judge-subsystem
chain (1→2→3). Tier 1, bug-fix lane.

## Final Behavior
- Every `OpenAICompatibleClient` completion is bounded by `OPENAI_TOTAL_TIMEOUT_SECONDS`
  (default 480s), additive on `(connect, read)`. On expiry the call degrades
  (`ok=False`), never hangs or crashes.
- Setting `job.stop_flag` during the judge pass aborts an in-flight cloud read and
  exits the loop cooperatively → `JudgeResult(judge_status="stopped")`. A
  ceiling-timeout with no cancel stays `"unavailable"`. BR-73 iteration cap and
  BR-74 result shape preserved; backend stays alive.

## Final Contracts Updated
- `business-rules.md` — BR-99 (judge-loop-cancellation) + BR-100 (cloud-LLM
  total-duration-ceiling); 2 Table U rows; Table U header extended.
- `env-contract.md` / `.env.example.template` / `env.schema.json` —
  `OPENAI_TOTAL_TIMEOUT_SECONDS` (fresh positive-float validator `^[0-9]+([.][0-9]+)?$`).
- `data-shape-contract.md` + `api-contract.md` — `judge_status` enum gains `stopped`;
  `openapi.yml` re-exported (in sync).

## Final Source Changed
- `openai_compatible_client.py` — `_run_bounded_post` (daemon worker + ceiling +
  cancel_event, degrade-not-fail); `_post_completion`/`translate_once` gain `cancel_event`.
- `base_llm_client.py` (Protocol) + `ollama_client.py` — additive `cancel_event` kwarg.
- `quality_judge.py` — `cancel_event` through `_complete`/`evaluate`/`run_judge_loop`/
  `_run_judge_loop_impl`; cooperative checks; `"stopped"` degradation.
- `job_manager.py` — wires `cancel_event=job.stop_flag`; `JudgeResult` docstring.
- `config.py` — `OPENAI_TOTAL_TIMEOUT_SECONDS`.

## Final Tests Added / Updated
- NEW `tests/test_cloud_total_timeout.py` — real dribbling-socket server; reproduces
  the incident (fails pre-fix ~8s, bounded post-fix ~1s), cancel-aborts-blocked-read.
- `test_quality_judge.py` — TestCancelDuringInFlightScoring, TestCancellationDegradation,
  TestIterationCapUnaffectedByCancellation.
- `test_openai_compatible_client.py` — TestTotalTimeoutCeilingAdditive, TestTotalTimeoutConfig.
- `test_orchestrator_judge.py` — test_cancel_during_judge_phase_reaches_terminal_state.
- `test_env_contract.py` — test_openai_total_timeout_seconds_declared.
- `test_llm_client_protocol.py` — updated signature + stdlib-allowlist pins for the
  additive `cancel_event` / `threading` import.
- Full suite 1123 pass (torch env).

## Final CI/CD Gates
No workflow edits (existing judge group + full pytest + openapi --check cover it).
PR #16 CI: all required gates green.

## Production Reality Findings
- `last_client` reset-to-None (found in #2) meant the old re-translation path never
  used the winning provider; #3 builds cancellation on #2's `translation_client` shape.
- `session.close()` may not abort a checked-out connection's read; correctness relies
  on the MAIN caller being unblocked promptly (ceiling/cancel → Timeout) with the
  daemon worker abandoned acceptably (ADR-0011) — not on the close actually aborting.
- The plan's file-level test list omitted `test_llm_client_protocol.py`, but it was in
  the context-manifest — the additive Protocol change (IP-3) required updating its two
  signature-pinning tests.

## Lessons Promoted to Standards
1. **[promote-to-guidance]** `CLAUDE.md` cdd-kit:learnings — bug-fix-lane gate evidence:
   a `test-reproduced` reproduction needs a genuinely FAILED pre-fix `cdd-kit test run`,
   and reproduction/regression `command` must equal the referenced run's recorded command
   (minus runner flags). Recipe: temporarily restore the pre-fix file
   (`git show main:<file> > <file>`), run only the repro test via `cdd-kit test run`,
   then restore the fix and re-run that phase green.
- Not promoted: the interruptible-post design (daemon worker + close + Timeout) and the
  cancel/ceiling semantics are product behavior — captured in ADR-0011 + BR-99/BR-100,
  not CLAUDE.md.

## Follow-up Work
`qa-mechanism-docs` (#6) documents the final QA-pipeline state (BR-92 removed;
BR-98/99/100 added). `translation-progress-detail-ui` (#7) appends `snapshot_cb` to
`run_judge_loop`/`_run_judge_loop_impl` — composes with the `cancel_event` param added here.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
