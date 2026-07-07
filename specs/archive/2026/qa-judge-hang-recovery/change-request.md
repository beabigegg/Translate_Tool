# Change Request

## Original Request

A live production incident this session: a translation job hung for 30+
minutes during the LLM-judge phase, with (a) no way to cancel it from the UI,
and (b) no wall-clock upper bound on the underlying cloud LLM call despite the
client code's own documented "≤7 minute" guarantee. Recovery required the
user manually killing the entire backend process — there is no in-app
recovery path today.

Verified this session via direct code read and live-process inspection (not
just agent-reported):

**Finding A — judge loop has no cancellation check.**
- `cancel_job()` (`job_manager.py:561-565`) only sets `job.stop_flag`
  (`threading.Event`, defined at `job_manager.py:98`).
- The main translation loop DOES check it —
  `job.stop_flag.is_set()` at `job_manager.py:352`, and it's threaded into
  `process_files` (`job_manager.py:376`, `stop_flag=job.stop_flag`).
- `quality_judge.py` has **zero** references to `stop_flag`/`stopped`/`cancel`
  anywhere in the file. `run_judge_loop`/`_run_judge_loop_impl`
  (`quality_judge.py:278-444`) never checks it — not at the per-block
  scoring step, not at the re-translation step, not between judge
  iterations. Pressing Cancel in the UI has zero effect once a job has
  entered the judge phase.

**Finding B — no wall-clock upper bound on cloud LLM calls; documented "≤7
min" bound does not hold in practice.**
- `openai_compatible_client.py:28-31`'s own comment: "A hanging provider
  consumes at most (120 + 300) s = 7 min before the chain advances," based on
  `requests`' `(connect_timeout, read_timeout)` tuple passed to
  `_post_completion` (`openai_compatible_client.py:112-135`,
  `timeout=self._timeout`).
- Live incident: `ss -tnp` on the actual running backend process (PID 3369)
  showed two ESTABLISHED connections to the panjit host
  (`ollamapjapi.theaken.com`, Cloudflare-fronted) on the **same local TCP
  ports** unchanged for 30+ minutes. Backend CPU time advanced only ~3s over
  25 minutes — consistent with a single still-blocked socket read, not
  retries (confirmed no retry/backoff logic exists anywhere:
  `base_llm_client.py` is a bare `Protocol` definition with five method
  signatures and zero implementation, despite CLAUDE.md describing it as a
  "shared retry/timeout base"; `openai_compatible_client.py` mounts no custom
  `HTTPAdapter`/`Retry`).
  `job.status_detail` was frozen the entire time.
- Most likely root cause: `requests`' read-timeout measures the gap
  *between* received chunks, not total call duration. If the panjit
  gateway/infrastructure trickles any keep-alive bytes within each 300s
  window (common for long LLM generations, e.g. an internal SSE-to-sync
  translation layer), the call can hang indefinitely regardless of the
  configured `(120, 300)` tuple — the "≤7 min" comment is only true for a
  connection that goes fully silent, not one that dribbles data slowly
  forever.
- Resolved operationally by the user manually killing the backend process —
  no in-app recovery existed.

## Business / User Goal

Make a hung QA-phase network call both (a) cancellable from the existing UI
Cancel button, and (b) bounded by an actual wall-clock ceiling independent of
per-chunk read-timeout semantics — so this class of incident never again
requires killing the whole backend process to recover.

## Non-goals

- Not building a general-purpose retry/backoff framework — the timeout fix is
  a bounded ceiling, not a retry mechanism. Behavior on timeout should match
  what already happens on any other judge-call exception (BR-74: graceful
  degradation, `judge_status="unavailable"`, job still completes normally).
- Not touching the main translation loop's existing `stop_flag` handling
  (`job_manager.py:352`, `process_files`'s own cancellation path) — already
  correct; this change only extends the SAME flag's reach into the judge
  loop.
- Not touching judge scoring logic, tier semantics (高/中/低), or
  `JUDGE_MAX_ITERATIONS` — BR-72/73 are correct as documented; this change
  only adds an escape hatch around them.
- Not touching `qa-judge-provider-consistency`'s scope beyond depending on it
  landing first (this change depends on that one — both touch
  `job_manager.py`'s judge call-site region and `quality_judge.py`'s
  `run_judge_loop`, to avoid a guaranteed merge conflict).
- Not resolving BR-92 or writing the three-mechanism documentation — separate
  sibling changes (`br92-rescore-resolution`, `qa-mechanism-docs`).

## Constraints

- The cancellation fix must not break BR-73 (iteration cap enforced
  unconditionally) or BR-74 (graceful degradation on unreachable/exception) —
  a cancelled job mid-judge-loop must still produce a well-defined
  `JudgeResult`/`job.judge` state (e.g. `judge_status="unavailable"` or a
  new explicit cancelled state — spec-architect's call), not leave it
  half-written or raise an unhandled exception.
- The timeout fix must not change behavior for calls that legitimately
  complete within a reasonable bound — only add an upper ceiling for calls
  that would otherwise hang indefinitely. Must not weaken the existing
  `(connect_timeout, read_timeout)` per-chunk protection, only add a
  total-duration cap on top of it.
- Cancellation must be checkable at a granularity that actually helps — e.g.
  checking `stop_flag` only between judge iterations (up to
  `JUDGE_MAX_ITERATIONS`=3 rounds) would NOT have helped the live incident,
  since the hang was WITHIN a single scoring call. The fix needs either a
  cooperative check inside the blocking call's timeout path, or the
  total-timeout fix (Finding B) itself becomes the effective cancellation
  mechanism for in-flight calls, with `stop_flag` checked between
  calls/blocks. Design must state which.
- STOP after `implementation-plan.md` — no `backend-engineer`/`bug-fix-engineer`
  in this pass.

## Known Context

- `depends-on: qa-judge-provider-consistency` (see this change's `tasks.yml`
  frontmatter) — that sibling change also edits `job_manager.py`'s judge
  call-site region (`_translate_fn`, ~L493-510) and
  `quality_judge.py:run_judge_loop`; land/rebase this change after that one.
- Sibling changes `batch-critique-qe-scoring` and `translation-progress-detail-ui`
  also touch adjacent regions (`translation_service.py` critique loop,
  `job_manager.py` ~L472-518, `quality_judge.py:run_judge_loop` — the latter
  already gained an additive optional `snapshot_cb` param in
  `translation-progress-detail-ui`'s implementation-plan.md amendment this
  session, for observability only, not cancellation). Coordinate the actual
  edit order; do not silently conflict on the same lines.
- `contracts/business/business-rules.md` BR-73/BR-74 (iteration cap, graceful
  degradation) are the existing rules this change must not violate.

## Open Questions

- What wall-clock ceiling should the total-timeout guard use — a flat
  constant (e.g. `JUDGE_TOTAL_TIMEOUT_S`), a multiple of the existing
  `(connect+read)` bound, or configurable via env (following this repo's
  established `os.environ.get(...)` config pattern)? Deferred to
  spec-architect/implementation-planner.
- Should the total-timeout guard live in `openai_compatible_client.py` (fixes
  it for ALL cloud calls, including main translation, not just judge) or be
  scoped narrowly to the judge call path only? The live incident was in the
  judge phase, but the same per-chunk-timeout gap could equally affect a main
  translation call to panjit/DeepSeek. Deferred to spec-architect — likely
  worth fixing at the client level (broader benefit) rather than
  judge-call-site-only, but confirm this doesn't expand scope into
  `qa-judge-provider-consistency`'s or `batch-critique-qe-scoring`'s territory
  unexpectedly.
- Cancellation granularity mechanism (see Constraints above) — needs a
  concrete design decision, not left implicit.

## Requested Delivery Date / Priority

No fixed deadline, but HIGHER priority than the other 3 sibling changes — this
is the only one tied to an actual live incident that already required manual
backend intervention to recover from. Plan now, implement as soon as the user
approves.
