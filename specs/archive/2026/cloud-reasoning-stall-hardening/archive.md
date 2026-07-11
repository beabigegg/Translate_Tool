# Archive — cloud-reasoning-stall-hardening

## Change Summary
Four coordinated hardening fixes on the PANJIT `gpt-oss:120b` cloud translation
path, all empirically validated against the live endpoint (probes + a
faulthandler stack on a real 27-minute hang). The cloud path had been emitting
dozens of empty-content/`unparseable JSON` fallbacks per real DOCX and could
stall 8–27 minutes on a single Cloudflare-cut request, effectively hanging a
whole document.

## Final Behavior
1. Every cloud TRANSLATION call (`translate_once` main/critique/judge + the JSON
   seam) prepends a harmony `Reasoning: low` directive (from the hardcoded
   `OPENAI_TRANSLATION_REASONING` constant) to the single leading system message
   — the ONLY reasoning lever PANJIT honors; `reasoning_effort`/`reasoning:{}`/
   `chat_template_kwargs` API params are inert. The outline `complete()` seam is
   exempt (`reasoning=None`). Empty-content fallbacks dropped from dozens to 0 on
   a real Chinese→Vietnamese DOCX.
2. `OPENAI_TOTAL_TIMEOUT_SECONDS` default lowered 480→120 so a Cloudflare-cut
   CLOSE-WAIT stall aborts in ~2 min instead of 8–27.
3. `embed()` now runs inside the same `_run_bounded_post` wall-clock bound
   (was an unbounded `session.post`) and degrades to `[]` on ceiling expiry.
4. New default-OFF `CRITIQUE_SKIP_CACHED_SEGMENTS` flag excludes Phase-1
   cache-HIT segments from the critique loop when enabled; default false is
   byte-identical current behavior.

## Final Contracts Updated
- `contracts/business/business-rules.md` 0.34.0→0.35.0: new BR-118
  (cloud-reasoning-suppression), BR-119 (critique-skip-cached-segments); BR-100
  amended (ceiling 480→120, embed under the bound); BR-109 composition sentence.
- `contracts/env/env-contract.md` 0.19.0→0.20.0: `OPENAI_TOTAL_TIMEOUT_SECONDS`
  480→120, new `CRITIQUE_SKIP_CACHED_SEGMENTS` row. `.env.example.template` synced.
- `docs/adr/0021-reasoning-suppression-harmony-system-directive.md` (new, amends ADR-0016).
- `contracts/CHANGELOG.md`: `[business 0.35.0]`, `[env 0.20.0]`.

## Final Tests Added / Updated
- `tests/test_openai_compatible_client.py`: `TestReasoningDirectiveComposition` (4),
  `TestOutlineReasoningExemption` (1), `TestEmbedBounded` (2); updated stale 480.0→120.0
  literals; fixed 7 pre-existing composition tests for the now-unconditional directive.
- `tests/test_context_prefix_bleed.py`: no-leak assertion extended for the `Reasoning:` prefix.
- `tests/test_orchestrator_context_detection.py`: AC-2 outline-exemption integration test.
- `tests/test_cloud_total_timeout.py`: 2 resilience tests (ceiling abort; embed bound → []).
- `tests/test_critique_loop_batching.py` (3) + `tests/test_critique_gate.py` (1): BR-119.
- Evidence: full suite 1481 passed / 0 failed (`test-evidence.yml` final-status passed).

## Final CI/CD Gates
Rode existing gates (contract-and-fast-tests, full-regression, golden-sample-regression,
renderer-equivalence, frontend-tests) — all green on PR #42. No new workflow step, no
per-change gate line. Live PANJIT E2E marked manual/informational-only (never gated,
never reads docs/TEST_DOC/).

## Production Reality Findings
- Sabotage-verified two load-bearing invariants (not left to the agents' green self-reports):
  AC-1 directive delivery (remove prepend → 3 composition tests RED with assertion/IndexError)
  and AC-4 embed bound (unbound embed → resilience test RED at 10s vs 0.5s ceiling); both
  restored byte-identical from scratch backups.
- The tier-floor check false-positived on vocab (authorized/cache/endpoint/route/session/worker);
  recorded a `tier-floor-override` rationale (Tier 1 is correct — no auth/payments/migration/
  concurrency).

## Lessons Promoted to Standards
- **Already promoted-to-contract during the change** (contract-reviewer confirmed, do-not-re-promote):
  (a) PANJIT/gpt-oss ignores `reasoning_effort`/`reasoning:{}`/`chat_template_kwargs` API params;
  only a harmony `Reasoning:` system directive works → BR-118 + ADR-0021.
  (b) reasoning-token exhaustion (empty `finish_reason='stop'`) and wall-clock-ceiling stalls share
  one root cause; reasoning-off + lowered ceiling fix both → BR-100 + ADR-0021.
- **promote-to-guidance (CLAUDE.md, net-zero fold):** added `"authorized"` and `"worker"` to the
  existing tier-floor-false-positive trigger list in the Promoted Learnings section (this change hit
  both). Evidence: pre-commit gate output + `tier-floor-override` in tasks.yml / agent-log/audit.yml.
- **Rejected (do-not-promote):** faulthandler-as-py-spy-fallback debugging technique — niche,
  project-agnostic, and not evidenced in the change artifacts; capture contemporaneously if it recurs.

## Follow-up Work
- Item 4 (`CRITIQUE_SKIP_CACHED_SEGMENTS`) is default-OFF, so critique-cost reduction is
  opt-in; the default-on stall/quality fix is items 1–3. Revisit if operators need default cost cuts.
- Ceiling calibration: 120s equals the 120s connect-timeout leg; raise via env override if a
  legitimate slow call is later observed near the bound.
- Reasoning suppression + length guard remain DOCX/cloud-focused; body/PPTX/XLSX truncation
  (BR-117 scope note) is still follow-up.

## Cold Data Warning
This archive is historical evidence. Current requirements live in contracts/ and active
project guidance.
