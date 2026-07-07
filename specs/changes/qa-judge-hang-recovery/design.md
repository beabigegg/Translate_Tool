# Design: qa-judge-hang-recovery

## Summary
A live incident hung a job for 30+ min inside a single judge scoring call: the
LLM-judge loop never checks `job.stop_flag`, and the shared cloud client's
`(connect, read)` timeout tuple bounds only the inter-chunk gap, not total call
duration — a provider that dribbles keep-alive bytes hangs forever. This change
adds two cooperating mechanisms: (1) a **wall-clock total-duration ceiling** on
the cloud HTTP call that converts an unbounded hang into a bounded exception,
and (2) a **cancel-aware interruptible post** that shares the same wait
primitive as the ceiling so setting `stop_flag` aborts an in-flight socket read.
`stop_flag` is additionally checked between per-block scoring calls and between
judge iterations for prompt fast-exit. On cancel or ceiling-timeout the loop
degrades to a well-defined `JudgeResult` (BR-74 shape preserved), the job stays
alive, and no backend kill is needed. Designed to layer on top of
`qa-judge-provider-consistency`'s new `translation_client` consumer shape and
`translation-progress-detail-ui`'s additive `snapshot_cb` param.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Judge loop | `app/backend/services/quality_judge.py` (`run_judge_loop` :278, `_run_judge_loop_impl` :319-462, `evaluate` :235, `_complete`) | add optional `cancel_event` param (after sibling's `snapshot_cb`); `stop_flag` checks at top of each iteration and before each per-block `evaluate()`/re-translate call; forward `cancel_event` down to client call; new `"stopped"` degradation path |
| Judge call-site | `app/backend/services/job_manager.py` (judge hook ~L472-518, `_translate_fn`) | pass `cancel_event=job.stop_flag` into `run_judge_loop` and into the sibling's `_judge.translation_client.translate_once(...)`; `cancel_job` (:561) unchanged |
| Cloud client | `app/backend/clients/openai_compatible_client.py` (`_post_completion` :112-135, `translate_once`) | add total wall-clock ceiling + optional `cancel_event`; run blocking `session.post` under an interruptible supervised wait that aborts on ceiling OR cancel |
| Local client | `app/backend/clients/ollama_client.py` | same `cancel_event` plumbing for cancellation parity (default-provider judge path) — lower risk, no dribble-ceiling needed |
| Client protocol | `app/backend/clients/base_llm_client.py` | add optional `cancel_event=None` kwarg to `translate_once` signature (back-compatible) |
| Config | `app/backend/config.py` | new `OPENAI_TOTAL_TIMEOUT_SECONDS` (float, `os.environ.get` pattern) |
| Contracts | business-rules.md, env-contract.md, .env.example.template, env.schema.json, data-shape-contract.md:567, api-contract.md:323/:51 | new BRs + Table U rows; new env var row; additive `"stopped"` judge_status enum value |

## Key Decisions

**D1 — Cancellation granularity: two-layer, ceiling-as-backstop + cooperative
fast-exit.** A between-iterations-only `stop_flag` check would NOT have caught
the incident (hang was inside one `evaluate()`→`_post_completion()` socket read),
and a bare cooperative check cannot unblock a thread already parked in a socket
read. So the **wall-clock ceiling (D2) is the true backstop for in-flight
calls** — it bounds a dribbling read regardless of `stop_flag`. For prompt
cancellation, the ceiling's wait primitive ALSO watches `cancel_event`: the
interruptible post polls a short interval and, on `cancel_event.set()` OR budget
exhaustion, closes the session (forcibly aborting the in-flight read) and raises
a `requests`-compatible timeout so the existing `except RequestException` path
degrades cleanly. `stop_flag` is checked at the top of each iteration and before
each per-block call so a cancel during the (common) multi-block loop exits
without starting new work. → Rejected: cooperative-check-only — cannot interrupt
a blocked socket read, fails AC-1/AC-2. → Rejected: signal/`SIGALRM` — not
thread-safe (judge runs on a worker thread), and non-portable.

**D2 — Ceiling lives in the cloud client, additive and opt-in.** The root cause
(requests read-timeout = inter-chunk gap) is a transport property of the shared
client, not the judge; the same dribble hang can strike a main-translation call
to panjit/DeepSeek. Placing the ceiling in `openai_compatible_client._post_completion`
fixes ALL cloud calls (widest correctness benefit) and is the natural home for a
transport concern. Blast-radius mitigation: the ceiling is a **generous default**
(placeholder ~480 s, above the 420 s worst-case for a healthy `120+300` call),
`degrade-not-fail` (matches BR-74 and the `CRITIQUE_TIMEOUT_SECONDS` precedent),
and does not weaken the existing per-chunk `(connect, read)` tuple — it is an
additional upper bound only. Only the judge path wires `cancel_event`; main
translation gains the ceiling automatically but no new cancellation wiring (stays
out of the main loop's existing `stop_flag` path per non-goals). Env var
`OPENAI_TOTAL_TIMEOUT_SECONDS` (application-team, positive float seconds) —
follows `CRITIQUE_TIMEOUT_SECONDS` shape and the existing `OPENAI_` client
prefix. → Rejected: judge-call-site-only guard — leaves the identical hang live
on every main-translation cloud call; narrow benefit for the same code cost.

**D3 — New `"stopped"` judge_status (not reused `"unavailable"`, not invented
`"cancelled"`).** User-initiated cancellation is not an error, so surfacing it as
`"unavailable"` conflates a broken judge with a deliberate stop and loses the
operator signal the incident is about. Add a 4th enum value `"stopped"`, matching
this repo's existing job-level cancellation vocabulary (`JobStatus.status =
"stopped"`, job_manager.py:524) rather than inventing `"cancelled"`. The edit is
additive/non-breaking: the frontend JudgePanel positive-matches `"available"`, so
an unknown value fails safe (renders as not-available). A ceiling-timeout (no
cancel) still degrades to `"unavailable"` (it IS a failure); only a set
`stop_flag` yields `"stopped"`. → Rejected: reuse `"unavailable"` — zero-cost but
erases the cancel-vs-failure distinction. → Rejected: `"cancelled"` — inconsistent
with the established `"stopped"` precedent.

## Contract edits implied (additive)
- **business-rules.md**: new `BR-99` (judge-loop-cancellation: `stop_flag` reaches
  the judge loop and in-flight scoring call; degrades to `judge_status="stopped"`;
  BR-73 cap and BR-74 shape preserved) and `BR-100` (cloud-LLM total-duration
  ceiling: additive on top of `(connect, read)`, degrade-not-fail). Two Table U
  rows (cancel-mid-judge → `stopped`; ceiling-timeout → `unavailable`). Numbering
  assumes sibling `qa-judge-provider-consistency` lands `BR-98` first.
- **env-contract.md / .env.example.template / env.schema.json**: `OPENAI_TOTAL_TIMEOUT_SECONDS`
  row (backend, application-team, positive float seconds, degrade-not-fail).
  env.schema.json has no float-pattern precedent to copy — a fresh positive-float
  validator is needed (flagged by contract-reviewer).
- **data-shape-contract.md:567**: `judge_status` enum → add `stopped`.
- **api-contract.md:51 & :323**: `GET /jobs/{id}/judge` enum → add `stopped`;
  re-run `cdd-kit openapi export` after edit.

## Edit-ordering with siblings
Both `run_judge_loop`/`_run_judge_loop_impl` signatures already gain
`snapshot_cb=None` (translation-progress-detail-ui) and the `_translate_fn`
closure is rewritten to `_judge.translation_client.translate_once(...)`
(qa-judge-provider-consistency). This change appends `cancel_event=None` AFTER
`snapshot_cb` and passes `cancel_event=job.stop_flag` into both `run_judge_loop`
and that `translate_once` call. Land/rebase AFTER `qa-judge-provider-consistency`
(shared region); do not touch BR-97's `_skip_judge_provider` gate.

## Migration / Rollback
Pure additive runtime behavior; no data migration. Rollback is config-only: set
`OPENAI_TOTAL_TIMEOUT_SECONDS` very high to disable the ceiling's practical
effect. The `stop_flag` reach and `"stopped"` status are code paths guarded by an
already-existing flag; disabling requires code revert, but reverting reintroduces
the incident (see ADR 0011). No schema, no persisted state, no wire-format break.

## Open Risks
- Ceiling default is an unvalidated placeholder — too tight aborts legitimate long
  cloud generations (indistinguishable from a dribble hang for `stream=False`
  calls). Must be calibrated against the longest legit panjit/DeepSeek call before
  raising priority; documented as tunable.
- `OllamaClient` in-flight interrupt parity is lower-assurance than the cloud path;
  local hangs are the default-provider judge path and must still honor `stop_flag`
  between blocks even if the mid-read abort is best-effort.
- Interruptible-post uses a worker thread + session close to abort a read; an
  abandoned worker thread lingering until socket close is acceptable (daemon), but
  must not leak sessions — verify session lifecycle in implementation.
- `.cdd/code-map.yml` was not consulted (not required here — affected ranges were
  read directly from the manifest-allowed files); no staleness claim made.
