# Archive — cloud-doc-context-summary

## Change Summary

Step 2 of the translation-prompt realignment: make the one-sentence document-context
summary (the 前情提要 preamble) actually work on the cloud translation path
(PANJIT/DeepSeek), which is the only path this project uses in practice. The change
began as a single guard removal and grew, under evidence, into two coupled fixes.
First, `orchestrator._detect_document_context` was gated out on cloud by
`and _cloud_client is None`, and it called Ollama-only private methods
(`_build_no_system_payload`/`_call_ollama`) that `OpenAICompatibleClient` does not
implement — so deleting the guard alone would have crashed or silently degraded, and
`translate_once` was the wrong shared seam because it wraps its input in
"Translate the following text…" framing (the model would translate the summary
instruction rather than summarize). Second, and more consequentially, even a
generated summary was being discarded: `OpenAICompatibleClient.system_prompt` was an
orchestrator-compatibility stub whose writes were "intentionally ignored", so neither
the scenario style prompt nor the document-context preamble ever reached a cloud
model. Fixing only the first defect would have shipped a no-op.

## Final Behavior

- The one-sentence document-context summary is generated on cloud providers through a
  new shared `complete(prompt) -> (ok, text)` raw-completion seam implemented on both
  concrete clients. `OllamaClient.complete` wraps the exact prior inline call, so the
  local path is byte-identical.
- `OpenAICompatibleClient.translate_once` now merges `self.system_prompt` (scenario
  style + `Document context: <summary>`) ahead of the per-segment BR-78
  `system_context` into ONE leading system-role message. Neither ever enters the
  translatable user payload (ADR-0016).
- `complete()` carries no system prompt by construction (`_build_messages` stays pure),
  so the summary call summarizes rather than translates its own instruction.
- Gating is unchanged: `CONTEXT_DETECTION_ENABLED` (code constant) AND
  `QWEN_CONTEXT_FLOW_ENABLED` (env var) must both be true, and a translation-dedicated
  client is still skipped. A failed or empty summary degrades gracefully to no
  preamble; the job never aborts for this reason.
- Net effect on the user's real path: the scenario style prompt and the document
  summary now reach the model for the first time. Previously only the scenario's
  sampling params (temperature/top_p) took effect.

## Final Contracts Updated

- `contracts/business/business-rules.md` — NEW **BR-109** (`cloud-context-detection-parity`),
  covering both generation (via `complete()`, no system prompt) and delivery (merge
  ahead of BR-78 `system_context`, never in the user payload, graceful fallback).
  **BR-78** row gained a cross-reference sentence noting the cloud-side merge preserves
  its never-in-user-payload guarantee. `schema-version 0.26.0 → 0.27.0`.
- `contracts/env/env-contract.md` — backfilled the previously **undocumented**
  `QWEN_CONTEXT_FLOW_ENABLED` env var (it existed in `config.py` with default `"1"` but
  was never in the contract); corrected the `OPENAI_TOTAL_TIMEOUT_SECONDS`
  bounded-call-site list to include the new `complete()` seam.
  `schema-version 0.16.0 → 0.17.0`. Mirrored into `.env.example.template` and
  `env.schema.json`.
- `contracts/CHANGELOG.md` — `[business 0.27.0]` + `[env 0.17.0]`.
- Deliberately NOT changed: `CONTEXT_DETECTION_ENABLED` is a hardcoded `config.py`
  constant, not an env var, so it gets no env-contract row. No API, data-shape, or
  CI/CD contract change (JSON I/O is Step 3).

## Final Tests Added / Updated

Added `tests/test_orchestrator_context_detection.py` (AC-1..AC-7, 10 tests):
- AC-1 cloud active client used for the summary (unit + integration)
- AC-2 summary reaches the **outgoing request payload** — system message contains
  `Document context: <summary>`, user message does not
- AC-3 both flags AND-gate the cloud path (two negative, call-count assertions)
- AC-4 translation-dedicated client still skipped (call-count assertion)
- AC-5 summary call raising AND returning `(False, "")` → job continues, no preamble
- AC-6 local-Ollama path unchanged (asserts it still generates AND injects)
- AC-7 scope preservation (Protocol still 5 methods, injection wiring untouched, no JSON I/O)

Added `tests/test_openai_compatible_client.py::TestSystemPromptDelivery` (3 tests):
merge ordering (preamble before BR-78 context, single system message, clean user
payload); `system_prompt` alone still delivered; `complete()` sends no system message
even when `system_prompt` is set.

Updated the test doubles reproducing the changed seam:
`tests/test_context_prompt_i18n.py` (mock `complete`), `tests/test_provider_fallback.py`
(removed a now-stale `CONTEXT_DETECTION_ENABLED=False` patch whose rationale cited the
very limitation this change removes).

Full suite: **1256 passed, 4 skipped**.

## Final CI/CD Gates

Per `ci-gates.md`: no workflow file added or edited. Required —
`cdd-kit validate --contracts` and the blanket `pytest tests/` in
`contract-and-fast-tests` (auto-covers the new test file). Informational —
`full-regression`. Manual (not automated) — real-PANJIT 8D-PDF re-run.
Rollback: `git revert`; safe because the behavior is flag-gated and degrades
gracefully, with no migration or irreversible state.

PR #25, CI run 28996399475 attempt 2: all 8 jobs `success`.

## Production Reality Findings

1. **The plan's central assumption was wrong, and only source-reading caught it.**
   The classifier and the original BR-109 draft both assumed the downstream injection
   wiring already delivered the preamble on both client paths. It did not. The
   cloud client's `system_prompt` was a stub documented in its own comment as
   "intentionally ignored". This was invisible from `.cdd/code-map.yml` and from the
   contracts; it required reading the cloud client's `_build_messages`/`translate_once`
   and grepping for any reader of `client.system_prompt` (there were none).

2. **A green test suite hid a complete no-op.** The first implementation passed all
   its tests, including AC-2, because AC-2 asserted that
   `client.system_prompt` *contained* the preamble — an attribute the cloud client
   ignored. Assignment was proven; delivery was not. The test was structurally
   tautological on the path that mattered.

3. **The constraint was self-imposed, not external.** A live capability probe of the
   PANJIT endpoint (`/v1/chat/completions`, gpt-oss:120b) showed a system-only
   instruction overrode the user message verbatim — the endpoint fully honors
   system-role messages. The "cloud clients build their own prompt" rationale in the
   stub comment was not backed by any endpoint limitation.

4. **Contract review caught two consistency defects the implementation missed**:
   `OPENAI_TOTAL_TIMEOUT_SECONDS` still enumerated its bounded call sites as
   "(translate + judge)" after `complete()` joined them, and BR-78 gave no signal that
   it now composes with BR-109 on the cloud path.

5. **`CONTEXT_DETECTION_ENABLED` is not an env var** (contrary to the change request's
   framing) — it is a hardcoded constant — while `QWEN_CONTEXT_FLOW_ENABLED` was a real
   env var that had never been documented. Both facts surfaced only from live source.

6. Pre-existing, out of scope: `process_files` unconditionally resets
   `client.system_prompt = base_system_prompt` in a per-file `finally:` block, which is
   why local-path assertions must capture the value at call time.

## Lessons Promoted to Standards

Classified by contract-reviewer at `/cdd-close` Step 3. Net `CLAUDE.md` growth: **zero
bullets added** (two edited in place).

| Lesson | Classification | Target | Evidence |
|---|---|---|---|
| **L1 — assignment is not delivery** (a 4th tautology form): asserting a value was SET on an attribute proves nothing if the consuming path never reads it; assert on the outgoing payload captured at the real boundary. | promote-to-guidance (folded into the existing tautological-tests bullet) | `CLAUDE.md` `cdd-kit:learnings` | archive.md Finding 2; `agent-log/backend-engineer.yml` Part 2; `agent-log/qa-reviewer.yml`; `tests/test_orchestrator_context_detection.py::test_cloud_summary_injected_as_document_context_in_system_prompt` |
| **L2 — a compatibility stub can silently discard writes**: verify an assigned attribute actually has a downstream READER before assuming a value flows. | promote-to-guidance (folded into the existing no-shell-planning-agents / seam-verification bullet) | `CLAUDE.md` `cdd-kit:learnings` | archive.md Finding 1; `agent-log/backend-engineer.yml` Part 2; the corrected stub comment in `openai_compatible_client.py` |
| **L3 — probe the external endpoint before believing a code comment's claimed limitation** | **do-not-promote** — single occurrence, and it is an investigation heuristic with no natural contract surface. Recorded in Finding 3 for future investigation; re-raise only if the pattern recurs, at which point it folds alongside L2. | — | archive.md Finding 3 |
| **L4 — undocumented env vars / miscategorized config constants** | **promote-to-contract** (the right home: mechanically checkable by grepping `config.py` for `os.environ` reads against the table) | `contracts/env/env-contract.md` `## Deployment Sync Policy`; `schema-version 0.17.0 → 0.18.0`; `CHANGELOG [env 0.18.0]` | `agent-log/contract-reviewer.yml` PASS 1; the `QWEN_CONTEXT_FLOW_ENABLED` backfill |
| **L5 — BR-109 / BR-78 product behavior** | already landed in this change's own contract edits — no further action | `contracts/business/business-rules.md` | this change |

The new env-contract policy states: every `os.environ` read in `app/backend/config.py`
MUST have a contract row (backfilled retroactively when a change touches that flag's
behavior), and a hardcoded non-`os.environ` `config.py` constant MUST NOT be given an
env-contract row — it belongs in business-rules prose with an explicit "not an env var"
note. This directly prevents both miscategorizations found in this change from
recurring silently.

Confirmed: no existing `cdd-kit:learnings` entry is contradicted by the contracts as
they now stand; no removals were required.

## Follow-up Work

- **Step 3 of the realignment** (separate tracked change): JSON structured translation
  I/O (`{"text":…}` → `{"translation":…}`) with validation and weak-model fallback.
- `DYNAMIC_SCENARIO_STRATEGY_ENABLED` (`config.py`) is another real env var that is
  still undocumented in `env-contract.md` — same class of gap as
  `QWEN_CONTEXT_FLOW_ENABLED`, found by contract-reviewer, deliberately left out of
  scope.
- `_detect_document_context(client: LLMClient, …)` calls `client.complete()`, which is
  intentionally off the five-method `LLMClient` Protocol. Runtime-safe (both concrete
  clients implement it; an `AttributeError` degrades via the existing `try/except`),
  but a future static-type-check gate would flag it. Narrow the annotation or add a
  `Protocol` alias exposing `complete()` if such a gate is added.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
