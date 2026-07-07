# Change Request

## Correction (found by test-strategist during planning)

The Original Request below describes `_translate_fn` as reusing `last_client`
("whatever provider won the main translation"), implying it's SOMETIMES
already-correct (already panjit) and sometimes divergent. Actual behavior is
worse: `job_manager.py:405-406` unconditionally resets `last_client = None` at
the end of every route-group loop iteration, BEFORE the judge hook runs
(~L472). So today, `_translate_fn`'s `last_client` fallback is **always**
`None` at judge-invocation time, regardless of which provider won
translation — meaning it **always** falls through to
`OllamaClient(DEFAULT_MODEL)`, unconditionally, not just in some divergent
case. This makes the fix strictly more important than originally described
(there is no "already-correct" case in current behavior to preserve
byte-for-byte — design.md's AC-2 no-op guarantee is instead verified via
constructed-request-parameter comparison against what a correct panjit call
would look like, since a live already-panjit path cannot be exercised
end-to-end today).

## Original Request

The judge phase's re-translation callback silently reuses whichever provider
won the main translation, instead of the judge's own scoring provider —
making QA-phase behavior a side effect of an unrelated routing decision
rather than an intentional choice.

Verified this session via direct code read (not just agent-reported):
- `_translate_fn` (`job_manager.py:493-510`, the re-translation callback
  passed into `_judge.run_judge_loop`) does `_cli = last_client` — the client
  object that happened to win the main translation phase via
  `model_router.py`'s fallback chain — with a fallback to
  `OllamaClient(model=DEFAULT_MODEL)` if `last_client` is `None`. It has zero
  reference to `JUDGE_MODEL`/`JUDGE_PROVIDER`/`JUDGE_CLOUD_PROVIDER_ID`.
- The judge's own scoring call, by contrast, deliberately builds a dedicated
  client: `quality_judge.py:89-108` (`_build_cloud_client()`) constructs an
  `OpenAICompatibleClient` from `providers.yml`, keyed by
  `JUDGE_CLOUD_PROVIDER_ID` (`config.py:207`, default `"panjit"`), whenever
  `JUDGE_PROVIDER="cloud"` (`config.py:197`).
- User's confirmed deployment constraint: main translation only ever routes
  to panjit or DeepSeek — never local Ollama. So in practice `last_client` is
  always one of those two providers, but `_translate_fn` depends on this only
  by accident (nothing enforces or documents it) — if `model_router.py`'s
  fallback chain ever changes, or Ollama becomes reachable again, the
  re-translation step would silently follow it with no one deciding that was
  correct.
- User's stated ideal: whenever the judge/QA pass actually runs (main
  translation provider is not `deepseek` — see BR-97, which already skips the
  entire judge pass for DeepSeek-translated jobs), **both** scoring and
  re-translation should go through panjit. Scoring and re-translation MAY use
  different models/endpoints within panjit (e.g. `gpt-oss:120b` for judging
  vs. a different model for translating), but must not silently diverge to a
  different *provider*.

## Business / User Goal

Make the QA-phase re-translation provider an explicit, documented choice tied
to the judge's own provider configuration (`JUDGE_CLOUD_PROVIDER_ID`), not an
implicit side effect of `last_client`. Eliminate the possibility of a
document's re-translation step silently running on a different provider than
the one that judged it as needing re-translation.

## Non-goals

- Not changing which provider wins the **main bulk translation** —
  `model_router.py`'s Ollama→DeepSeek→PANJIT fallback chain and
  `providers.yml` selection for the initial translation pass are untouched.
  This change only affects the re-translation callback invoked from inside
  the judge loop (`_translate_fn`).
- Not touching BR-97 (judge-skip-deepseek-provider) — that gate already
  correctly skips the entire judge pass (scoring AND re-translation) when the
  winning provider is `deepseek`; this change does not alter when the judge
  pass runs, only what it uses internally when it does run.
- Not touching the in-line critique loop (`translation_service.py:59-96`) or
  its `_critique_gate_adopt` COMET comparison — unrelated mechanism, and the
  sibling `batch-critique-qe-scoring` change already owns that code region.
- Not touching cancellation or timeout behavior — that is the sibling
  `qa-judge-hang-recovery` change (which depends on this one landing first,
  since both touch `job_manager.py`'s judge call-site region and
  `_translate_fn`/`quality_judge.py`).
- Not resolving BR-92 — unrelated mechanism (sibling `br92-rescore-resolution`
  change).

## Constraints

- Must not change behavior for the already-correct case: if `last_client`
  already happens to be a panjit client, the fix should be a no-op in
  practice (same requests, same responses) — only the divergent case
  changes.
- Must not alter BR-97's skip condition or any other existing judge-loop
  business rule (BR-72 through BR-77) beyond which client executes the
  re-translation call.
- Must reuse existing `providers.yml`/`JUDGE_CLOUD_PROVIDER_ID` configuration
  plumbing (`quality_judge.py:89-108`'s `_build_cloud_client()` pattern) —
  do not invent a new config surface for this.
- STOP after `implementation-plan.md` — no `backend-engineer`/`bug-fix-engineer`
  in this pass.

## Known Context

- `config.py:190-209`: `JUDGE_ENABLED`, `JUDGE_PROVIDER` (default `"ollama"`,
  can be `"cloud"`), `JUDGE_MODEL` (default `"gemma3"`, or e.g.
  `"gpt-oss:120b"` when cloud), `JUDGE_CLOUD_PROVIDER_ID` (default
  `"panjit"`).
- `quality_judge.py:56-120`: `QualityJudge.__init__` builds `self._client`
  (scoring) via `_build_cloud_client()` when `self._provider == "cloud"`, else
  a local `OllamaClient(model=JUDGE_MODEL)`. This is the pattern the
  re-translation fix should mirror or directly reuse.
- `job_manager.py:472-518`: the judge invocation call site —
  `job.status_detail = "品質評審中…"`, `_judge = QualityJudge()`, the
  `_translate_fn` closure (`L493-510`), and `job.judge =
  _judge.run_judge_loop(job_id, qe_blocks, _translate_fn)`.
- Related sibling changes touching the same file region: `qa-judge-hang-recovery`
  (depends on this one — see its own change-request.md), and both
  `batch-critique-qe-scoring` / `translation-progress-detail-ui` touch
  adjacent regions in `translation_service.py`/`job_manager.py` — sequence or
  rebase, do not silently conflict.

## Open Questions

- Should QA-phase re-translation reuse the EXACT SAME client instance/model
  as scoring (`self._client`/`JUDGE_MODEL`), or build a second, distinct
  "translation-role" panjit client with a different model name (user's own
  phrasing allows "換端點" — different endpoint/model, same provider)?
  Deferred to spec-architect given `providers.yml`'s actual shape (does it
  have separate "judge" vs "translate" model entries for panjit, or just one
  panjit endpoint with a configurable model per call?).
- Does this fix need a new business rule (extending the BR-97/BR-72 area) to
  document "QA re-translation must use JUDGE_CLOUD_PROVIDER_ID's provider,
  decoupled from last_client"? Likely yes — defer exact BR numbering to
  contract-reviewer/spec-architect.

## Requested Delivery Date / Priority

No fixed deadline. Priority: correctness (silent provider divergence risk) —
discovered incidentally, not a scheduled roadmap item. Plan now, implement in
a later session.
