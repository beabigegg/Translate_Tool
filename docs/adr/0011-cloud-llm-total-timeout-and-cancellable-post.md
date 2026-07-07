# ADR 0011: Cloud LLM calls carry a wall-clock total-duration ceiling and a cancel-aware interruptible post

## Status
proposed

## Context
A production job hung 30+ minutes inside a single LLM-judge scoring call. Two
transport facts caused it: (1) `requests`' `(connect, read)` timeout tuple bounds
only the gap *between* received bytes, not total call duration — a provider that
trickles keep-alive/partial bytes within each 300 s window (common for long
cloud LLM generations behind an SSE-to-sync gateway) hangs indefinitely despite
the client's documented "≤7 min" bound; and (2) the judge loop never observes
`job.stop_flag`, and even if it did, a cooperative flag check cannot unblock a
thread already parked in a socket read. Recovery required killing the whole
backend process. The client (`openai_compatible_client.py`) is shared by the main
translation path too, so the same hang can strike any cloud call.

## Decision
Add, at the shared cloud-client transport layer (`openai_compatible_client._post_completion`):
1. A **wall-clock total-duration ceiling** (`OPENAI_TOTAL_TIMEOUT_SECONDS`,
   generous default) that is additive on top of the existing per-chunk
   `(connect, read)` tuple and never weakens it. On expiry the call aborts and
   raises a `requests`-compatible timeout, degrading via the existing exception
   path (BR-74 / `judge_status="unavailable"`) — degrade-not-fail, no retry.
2. A **cancel-aware interruptible post**: the blocking `session.post` runs under a
   supervised wait that shares one primitive with the ceiling and also watches an
   optional `cancel_event`. Setting the event (the judge path passes
   `job.stop_flag`) closes the session to abort the in-flight read and raises,
   so cancellation reaches a call already blocked in a socket read.
The judge loop additionally checks `stop_flag` between per-block calls and between
iterations for prompt fast-exit; a cancelled judge pass surfaces the new
`judge_status="stopped"` (consistent with `JobStatus="stopped"`).

## Consequences
- Any cloud call now has a hard liveness bound; this class of hang no longer
  requires a backend kill. The fix is a bounded ceiling, not a retry framework.
- Trade-off: for `stream=False` calls a legitimate long generation is
  indistinguishable from a dribble hang, so the ceiling default must be generous
  and calibrated; too tight aborts valid long translations. It is tunable via env.
- The interruptible-post uses a worker thread + session close; implementations
  must not leak sessions and must treat an abandoned worker as best-effort.
- **Do not silently revert**: removing the worker-thread wrapper or the ceiling
  "to simplify" reintroduces the exact unbounded-hang incident. Any future change
  narrowing this back to a per-chunk-only timeout must document why the dribble
  case is no longer possible.
- Blast radius is the whole cloud pipeline (main translation gains the ceiling);
  only the judge path wires `cancel_event`, leaving the main loop's existing
  `stop_flag` handling untouched.
