---
change-id: cloud-reasoning-stall-hardening
schema-version: 0.1.0
last-changed: 2026-07-11
---

# Implementation Plan: cloud-reasoning-stall-hardening

## Objective
Ship four behavior-only hardening fixes on the cloud (`OpenAICompatibleClient`)
translation path: (1) source the `_post_completion` reasoning-directive default
from a new hardcoded config constant; (2) lower the wall-clock ceiling default
480→120s; (3) bring `embed()` under the same wall-clock bound; (4) add a
default-off critique-loop skip of Phase-1 cache-HIT segments. Update stale tests
and add the new unit/contract/integration/resilience coverage. No API, schema,
UI, or CI-workflow surface changes.

## Execution Scope

### In Scope
- `app/backend/config.py`: add `OPENAI_TRANSLATION_REASONING`, add
  `CRITIQUE_SKIP_CACHED_SEGMENTS`, lower `OPENAI_TOTAL_TIMEOUT_SECONDS` default.
- `app/backend/clients/openai_compatible_client.py`: re-source the `_post_completion`
  reasoning default from config (BR-118); route `embed()` through `_run_bounded_post`
  (BR-100).
- `app/backend/services/translation_service.py`: default-off BR-119 skip in the
  critique pre-filter.
- Update stale `480.0` test literals and extend the no-leak bleed test.
- Add the new tests in test-plan.md §Acceptance Criteria → Test Mapping.

### Out of Scope (non-goals — do NOT do)
- Any change to `complete()` beyond its existing `reasoning=None` (outline seam
  is EXEMPT, BR-118).
- Making `OPENAI_TRANSLATION_REASONING` an env var (it is a hardcoded constant).
- Lowering `max_tokens`, adding OpenAI `reasoning_effort`/`response_format` params,
  or any new provider/model/API/UI surface (design.md §Key Decisions rejections).
- Capping critique rounds/segment count or disabling `CRITIQUE_LOOP_ENABLED`
  wholesale (design.md Item 4 rejected alternatives).
- Editing `contracts/**` (contract-reviewer already bumped business-rules 0.35.0
  and env-contract 0.20.0 per ci-gates.md) or any `.github/workflows/**`.
- Reading or testing against `docs/TEST_DOC/` (forbidden path).
- The local Ollama translate path.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `OPENAI_TRANSLATION_REASONING="low"` (hardcoded, not env); add `CRITIQUE_SKIP_CACHED_SEGMENTS` (env-overridable bool, default false); change `OPENAI_TOTAL_TIMEOUT_SECONDS` default 480→120 | backend-engineer |
| IP-2 | client | Re-source `_post_completion`'s reasoning default from `OPENAI_TRANSLATION_REASONING` (BR-118) | backend-engineer |
| IP-3 | client | Route `embed()`'s `_session.post` through `self._run_bounded_post` (BR-100); keep existing `except → return []` degrade | backend-engineer |
| IP-4 | services | Default-off BR-119 skip: when `CRITIQUE_SKIP_CACHED_SEGMENTS=true`, exclude Phase-1 `cached_keys` segments from `_pending_keys` | backend-engineer |
| IP-5 | tests (existing) | Update stale `480.0` literals; extend `test_context_prefix_bleed.py` for the `Reasoning:` directive no-leak | backend-engineer |
| IP-6 | tests (new) | Add unit/contract/integration tests per test-plan.md mapping | backend-engineer |
| IP-7 | tests (resilience) | Add `test_cloud_total_timeout.py` ceiling + embed-bound resilience tests | e2e-resilience-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | §Key Decisions Items 1–4, §Open Risks | implementation constraints + ceiling calibration note |
| test-plan.md | AC→Test Mapping table, §Test Update Contract, §Anti-Tautology Notes | tests to write/update + real-boundary assertion rules |
| ci-gates.md | Required Gates table | verification gates (no new workflow) |
| contracts/business/business-rules.md | BR-118 (L129), BR-119 (L130), BR-100 (L111), BR-109 (L120) | behavior + no-leak invariant |
| change-classification.md | §Inferred Acceptance Criteria AC-1..AC-5 | criterion mapping |

## File-Level Plan
| path | action | notes (verified seam line) |
|---|---|---|
| `app/backend/config.py` | edit | change `OPENAI_TOTAL_TIMEOUT_SECONDS` default `"480"`→`"120"` — L99 (`float(os.environ.get("OPENAI_TOTAL_TIMEOUT_SECONDS", "480"))`) CONFIRMED 480 |
| `app/backend/config.py` | add | `OPENAI_TRANSLATION_REASONING: str = "low"` (hardcoded; NOT `os.environ.get`; comment "not an env var" like `CONTEXT_DETECTION_ENABLED`) — grep confirmed absent |
| `app/backend/config.py` | add | `CRITIQUE_SKIP_CACHED_SEGMENTS: bool = os.environ.get("CRITIQUE_SKIP_CACHED_SEGMENTS","0").lower() in ("1","true","yes")` near L168 critique block, default OFF — mirrors `CRITIQUE_LOOP_ENABLED` L168 CONFIRMED |
| `app/backend/clients/openai_compatible_client.py` | edit | `_post_completion` reasoning default → config-sourced. Prefer param default `None` sentinel + call-time `if reasoning is None: reasoning = config.OPENAI_TRANSLATION_REASONING` (avoids import-freeze), preserving `complete(reasoning=None)`'s explicit-None exemption — but None must still mean "no directive" for `complete()`, so use a distinct sentinel OR read the constant only when the caller omits the arg entirely; backend picks the form that makes `test_directive_value_sourced_from_openai_translation_reasoning_config_constant` read the CONSTANT (not the literal) AND keeps `complete()` directive-free. Prefix composition L204-208 UNCHANGED. `_post_completion` sig L179-185 CONFIRMED `reasoning="low"`; `complete()` `reasoning=None` L404 CONFIRMED exempt |
| `app/backend/clients/openai_compatible_client.py` | edit | `embed()`: wrap `self._session.post(...)` in a local `_do_post` closure, call `self._run_bounded_post(_do_post)` (no cancel_event); keep `raise_for_status`/parse + broad `except → return []`. `_session.post` L273 CONFIRMED unbounded; `_run_bounded_post(self, fn, cancel_event=None)` L125 CONFIRMED same class |
| `app/backend/clients/openai_compatible_client.py` | none | `translate_json` calls `_post_completion` WITHOUT `reasoning=` (L387) → inherits default directive; system merge L385-386 unchanged. No edit required |
| `app/backend/services/translation_service.py` | edit | `_pending_keys` comprehension (L466-469): add clause excluding `_key in cached_keys` when `CRITIQUE_SKIP_CACHED_SEGMENTS` true (call-time read). `cached_keys` entries are `(tgt, src_text)` — same tuple shape as `_key`. Pre-filter L466-469 CONFIRMED; `cached_keys` defined L280, populated L316 CONFIRMED |
| `tests/test_openai_compatible_client.py` | edit | `480.0`→`120.0`: `TestTotalTimeoutCeilingAdditive` patch L760, assert-comment L766, patch L772; `TestTotalTimeoutConfig::test_env_var_parses_positive_float_default` assert L791 (see Seam Verification correction) |
| `tests/test_context_prefix_bleed.py` | edit | extend no-leak: `"Reasoning:"` substring absent from every echoed user `text` (test-plan §Test Update Contract) |
| `tests/test_openai_compatible_client.py` | add | `TestReasoningDirectiveComposition`, `TestOutlineReasoningExemption`, `TestEmbedBounded` (test-plan AC-1/AC-2/AC-4) |
| `tests/test_critique_loop_batching.py`, `tests/test_critique_gate.py` | add | BR-119 unit tests (default-off parity, opt-in selection, no-drop, gate-unaffected) |
| `tests/test_orchestrator_context_detection.py` | add | AC-2 integration: outline summary non-empty with translation reasoning suppressed |
| `tests/test_cloud_total_timeout.py` | add | resilience: ceiling abort ≤120s; embed stall → `[]` (e2e-resilience-engineer) |

### Seam Verification Result (grep-confirmed this run)
All seams named in the launch task match live source. One line-number correction to
test-plan.md §Test Update Contract: it lists the stale `480.0` patches at
"~L760/766/772/780/795" attributed to `TestTotalTimeoutCeilingAdditive`. ACTUAL —
L780 is a docstring and L791 (not 795) is the assert, and BOTH belong to
`TestTotalTimeoutConfig::test_env_var_parses_positive_float_default`, NOT
`TestTotalTimeoutCeilingAdditive`. The additive-class `480.0` occurrences are L760
(patch), L766 (assert-comment `!= 480.0`), L772 (patch). No functional impact — all
`480.0` occurrences (760, 766, 772, 791) change to `120.0`.

## Ordered Task Sequence

### backend-engineer (in order)
1. IP-1 config constants: add `OPENAI_TRANSLATION_REASONING`, add
   `CRITIQUE_SKIP_CACHED_SEGMENTS`, lower `OPENAI_TOTAL_TIMEOUT_SECONDS` default to 120.
2. IP-2 reasoning-default sourcing from `OPENAI_TRANSLATION_REASONING` (call-time read).
3. IP-3 embed bound: route `embed()` through `_run_bounded_post`.
4. IP-4 critique skip: default-off `cached_keys` exclusion in `_pending_keys`.
5. IP-5 update existing tests: `480.0`→`120.0` (L760/766/772/791); extend
   `test_context_prefix_bleed.py` for the `Reasoning:` no-leak.
6. IP-6 new tests (RED-first where net-new per test-plan §Notes).
7. Generate targeted + changed-area evidence (see Test Execution Plan). Report
   `blocked` rather than infer unstated scope.

### e2e-resilience-engineer (after backend wiring lands)
1. IP-7 `test_cloud_total_timeout.py`: real local dribble socket (no client-internals
   mocking) proving `_post_completion` aborts within 120s (not 480s), and a stalled
   `embed()` POST aborts within the ceiling and degrades to `[]`. Assert at the real
   boundary (wall-clock abort + returned value), per test-plan §Anti-Tautology.

## Contract Updates
- API: none
- CSS/UI: none
- Env: `OPENAI_TOTAL_TIMEOUT_SECONDS` default change + new `CRITIQUE_SKIP_CACHED_SEGMENTS`
  already synced by contract-reviewer (env-contract 0.20.0, per ci-gates.md). Backend
  does NOT edit `contracts/**`.
- Data shape: none
- Business logic: BR-118, BR-119, BR-100, BR-109 already authored (business-rules
  0.35.0). Implement to those rules; do not edit the contract.
- CI/CD: none (no new workflow/job/gate line — ci-gates.md).

## Test Execution Plan
Run all phases via `conda run -n translate-tool cdd-kit test run --phase <phase>`
(QE/torch-dependent tests hard-error outside the conda env). Required floor: collect,
targeted, changed-area; add contract (ADR-0016/ADR-0021 no-leak) and full (final/CI).
Full ladder: test-plan.md §Test Execution Ladder.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (BR-118 composition) | tests/test_openai_compatible_client.py::TestReasoningDirectiveComposition | system msg == directive+base+neighbor; directive absent from every user message; value from config constant |
| AC-2 (BR-118 exemption) | tests/test_openai_compatible_client.py::TestOutlineReasoningExemption | `complete()` sends no directive |
| AC-2 (integration) | tests/test_orchestrator_context_detection.py | non-empty summary with translation reasoning suppressed |
| AC-1 (no-leak) | tests/test_context_prefix_bleed.py | `Reasoning:` substring absent from echoed user `text` |
| AC-3 (default) | tests/test_openai_compatible_client.py::TestTotalTimeoutConfig::test_env_var_parses_positive_float_default | default parses to 120.0 |
| AC-3 (ceiling) | tests/test_cloud_total_timeout.py::test_stalled_dribble_aborts_within_120s_ceiling_not_480s | abort ≤120s |
| AC-4 (embed routing) | tests/test_openai_compatible_client.py::TestEmbedBounded | `_run_bounded_post` actually exercised by `embed()` |
| AC-4 (embed resilience) | tests/test_cloud_total_timeout.py::test_embed_stalled_post_aborts_within_ceiling_degrades_to_empty_list | abort ≤ceiling → `[]` |
| AC-5 (default-off parity) | tests/test_critique_loop_batching.py::test_critique_skip_cached_segments_default_false_every_segment_still_enters_pending_keys | flag off = byte-identical `_pending_keys` |
| AC-5 (opt-in selection) | tests/test_critique_loop_batching.py::test_critique_skip_cached_segments_true_excludes_phase1_cache_hit_keys_from_pending_keys | cache-HIT keys excluded (SET, not count) |
| AC-5 (no-drop) | tests/test_critique_loop_batching.py::test_critique_skip_cached_segments_true_keeps_excluded_segments_draft_present_in_tmap | excluded segment's `tmap` draft non-empty |
| AC-5 (gate unaffected) | tests/test_critique_gate.py::test_critique_skip_cached_flag_does_not_alter_max_iterations_timeout_or_gate_for_segments_still_in_loop | in-loop mechanics unchanged |

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this
  plan; follow the source pointers above.
- Preserve the BR-109/ADR-0016 no-leak invariant: the `Reasoning:` directive and the
  base/neighbor system content stay in the ONE leading `role:"system"` message and
  NEVER enter `user_content`. Assert on the captured OUTGOING payload, never on
  `client.system_prompt` (assignment-without-delivery) and never only on relative
  ordering (order-without-location) — test-plan §Anti-Tautology Notes.
- `OPENAI_TRANSLATION_REASONING` is a hardcoded constant, NOT an env var.
- `CRITIQUE_SKIP_CACHED_SEGMENTS` default false ⇒ current critique behavior is
  BYTE-IDENTICAL; the flag only removes cache-HIT segments from `_pending_keys`.
- Read config flags at call time (module attribute), never `from ... import` the value
  into a module global (import-freeze defeats `monkeypatch.setattr(config, ...)`).
- Before landing, grep `tests/` for `_post_completion`/`translate_once`/`embed` fakes
  with fixed signatures and update them in THIS change (a fake that merely ACCEPTS a
  new kwarg without recording it stays green even if delivery is deleted).
- Never read, write, or test against `docs/TEST_DOC/`.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- Ceiling calibration (design.md §Open Risks): 120s equals the 120s connect timeout and
  sits below the 300s read timeout, so a cold-start connect could theoretically brush
  the ceiling. Probed legit calls complete 3–16s, practically safe; additive-ceiling
  tests must patch the ceiling to a value ≠ the read timeout to stay a valid probe.
- The config-sourced reasoning default must be read at call time AND must not collapse
  `complete()`'s explicit `reasoning=None` (directive-free) into the new default — pick
  a sentinel/omission scheme that keeps the outline seam exempt.
- BR-119 key-shape trap: `_pending_keys` `_key` and `cached_keys` entries are both
  `(tgt, src_text)`; verify the exclusion keys off the same tuple shape or the skip
  silently no-ops (or over-excludes).
- Tautological-test forms are enumerated per family in test-plan §Anti-Tautology; any
  log assertion must filter `record.name == "TranslateTool"`.
