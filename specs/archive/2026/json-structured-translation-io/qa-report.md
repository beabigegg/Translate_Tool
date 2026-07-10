# QA Report — json-structured-translation-io

Change tier: 1 (high risk, system-wide: every translation call routes through
one of the two paths this change rewrites). Reviewer: qa-reviewer.
Two-reviewer sign-off required (qa-reviewer + spec-architect); this is the
qa-reviewer approval.

## Gate Results

| Gate | Result | Evidence |
|---|---|---|
| Contracts updated (data 0.18.0 / business 0.30.0 / env 0.19.0) | pass | headers match 3 CHANGELOG entries |
| cdd-kit validate --contracts | pass | test-runs/20260710-122118 |
| Protocol immutability (5-method surface) | pass | base_llm_client.py + test_llm_client_protocol.py untouched; test_protocol_defines_five_methods green |
| Selection tautology (echo vs single-cell) | pass | exact-dict assertion, re-run by node-id |
| Delivery tautology (system-channel ordering) | pass | both clients assert captured payload, index-ordered |
| caplog root-logger bleed (INFO observability) | pass | name-filtered `record.name == "TranslateTool"` |
| Meta-refusal both directions | pass | BR-108 example caught; "Need more context." survives |
| Deferred-scope containment | pass | docx_processor diff wire-format-only; no nested-table collection |
| test-evidence.yml covers shipped bytes | pass | regenerated 12:24; mtime later than every covered source file |
| Required phases green, no waivers | pass | collect/targeted/changed-area/contract passed; full also passed |

## Evidence

- Regenerated `test-evidence.yml` (`cdd-kit test run`). Required phases collect,
  targeted (122102), changed-area (122105), contract (122118) all passed;
  non-required full (122120) also passed: 1365 tests, 0 failures, 0 errors,
  4 skipped → 1361 passed. Zero waiver fields.
- The new full junit CONTAINS `TestHostileTableJsonReplies` (12 BR-82
  hostile-reply resilience tests, absent from the prior stale run),
  `TestTranslateJsonSystemChannelDelivery` (3), and 24
  `test_json_translation_body` testcases. The evidence now tests the
  reconstructed `table_serializer.py` (12:07) and `translation_helpers.py` (12:08).
- `serialize_json`/`parse_json` read and confirmed against all nine contract
  rules (data-shape §Table Serialization Wire Format). The whole-grid echo check
  is `all(reply == sent over sent_cells)`;
  `test_single_unchanged_cell_is_legitimate_not_rejected` asserts the exact
  result dict (selection, not count). Both re-run green by node-id.
- Delivery: OpenAI `TestTranslateJsonSystemChannelDelivery` captures the
  `requests.Session.post` `json=` payload and asserts ONE system message with
  `system_prompt` index < `system_context` index. Ollama asserts the same
  ordering on `_call_ollama`'s `payload["system"]`. Both re-run green by node-id.
- Observability: INFO fallback tests filter `record.name == "TranslateTool"`,
  making them immune to caplog root-logger bleed.
- BR-78 flag-OFF path pinned in `test_context_prefix_bleed.py`
  (`_FakeEchoClient`); flag-ON BR-78 delivery covered by the new seam tests.
  No coverage lost.
- Contracts: data 0.18.0, business 0.30.0, env 0.19.0 headers each backed by a
  matching `contracts/CHANGELOG.md` entry.
- qa independent runs on the current tree: 174-test change surface green; 10
  load-bearing tests re-run green by node-id.

## Reconstruction risk (git checkout incident) — closed

`table_serializer.py` was destroyed by `git checkout -- <file>` during a
falsifiability toggle — uncommitted work is invisible to git's safety net — and
then reconstructed from the agent's own earlier `Read` output. The agent caught
and disclosed this itself. Closed three ways: (1) a recorded green full run over
the current bytes, including all 12 hostile-reply tests; (2) an independent
nine-rule exercise of `parse_json` by main Claude, returning a distinct named
reason per reject and the correct accept/reject on the two that matter —
whole-grid echo rejected, single-cell echo accepted; (3) the agent-log
falsifiability record showing assertion-level RED on the disabled echo check and
on the disabled meta-refusal guard, GREEN on restore. No residual divergence
identified.

## Failures

None. The prior blocking finding — recorded evidence predating the 12:07/12:08
reconstruction and the 16+ tests added after 11:43 — is resolved by full
regeneration against the current tree.

## Fixback Routing

None blocking. Follow-ups only.

## Follow-ups for /cdd-close

- `test_fallback_logs_warning_on_parse_failure`
  (`test_table_context_translation.py:432`) asserts `levelno >= WARNING` with no
  `record.name` filter. That WARNING is emitted via
  `logging.getLogger(__name__)` in `translation_service.py` and never reaches
  `translator.log`. A redundant weak assertion, not a coverage hole — the real
  BR-82/BR-109 guarantee is carried by the name-filtered `TestFallbackLogging`.
  Pre-existing; NOT introduced by this change. Tighten it or re-scope its
  docstring. Owner: test-strategist.
- Durable rule candidate: falsifiability toggles must mutate in place with a
  scratch-file backup and restore from it — never `git checkout` / `git stash` /
  `git restore`, which silently destroy uncommitted working-tree work (the normal
  state of an in-flight CDD change). If a git-level revert already destroyed
  uncommitted work, regenerate `cdd-kit test run` evidence afterwards: a
  reconstruction is not trusted until a full recorded run covers the current
  bytes. Promote to `CLAUDE.md`.

## Decision

**approved** (qa-reviewer). Pending the required second sign-off (spec-architect)
for this Tier 1 high-risk change. No code change requested; no residual risk.
