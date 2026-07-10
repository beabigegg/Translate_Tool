# CI/CD Gate Plan

## Change ID
json-structured-translation-io — Tier 1, high risk, system-wide (change-classification.md).

## Required Gates
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | PR/push | `cdd-kit validate --contracts` (job `contract-and-fast-tests`) | exit code 0 — see caveat below |
| env-sync (new flag) | 1 | yes | PR/push | new grep step "Env schema sync — JSON_STRUCTURED_TRANSLATION_ENABLED" (`contract-driven-gates.yml`, job `contract-and-fast-tests`) | exit code 0 |
| targeted (new files, collect-only smoke) | 1 | yes | PR/push | already swept by existing `pytest tests/ -x -q --tb=short --junitxml=…` line 134, job `contract-and-fast-tests` | junit.xml |
| unit/contract/integration/data-boundary/resilience (AC-1..AC-8) | 1 | yes | PR/push | same line-134 step — no new targeted step added, see rationale | junit.xml |
| full-regression | 2 | yes (informational→escalates) | PR | `pytest tests/ -q --tb=short` job `full-regression` | full-regression.xml |
| openapi export --check | 1 | yes | PR/push | unchanged, untouched by this change (no API surface) | exit code 0 |

## New Workflow Changes Applied
- `.github/workflows/contract-driven-gates.yml`, job `contract-and-fast-tests`: added one grep step, "Env schema sync — JSON_STRUCTURED_TRANSLATION_ENABLED in .env.example.template and env.schema.json", following the existing `DEEPSEEK_ENABLED`/`JUDGE_ENABLED` precedent (lines 49-78). Both artefacts already carry the row (verified on disk); this step is the enforcement, not a new obligation. Blocks merge.
- No other workflow edit. All new/extended test files (`test_json_translation_prompt.py`, `test_json_translation_body.py`, and the extended `test_table_serialization.py`, `test_table_context_translation.py`, `test_nontranslatable_segment_guard.py`, `test_pdf_layout_table_fixes.py`) live under `tests/` and are already swept by the blanket `pytest tests/ -x -q` at line 134 (merge-blocking) and `pytest tests/ -q` in `full-regression` at line 161. No dedicated per-file targeted step is added.

## Rationale: no dedicated targeted step for AC-1/AC-2/AC-4/AC-5
AC-1 (phantom-column table completes without fallback) and AC-5 (fallback INFO reaches `TranslateTool`) are both proven inside the mocked-transport integration tests in `test_table_context_translation.py`/`test_json_translation_body.py`. The transport boundary (client HTTP call) is mocked per test-plan.md, so there is no network dependency and no silent-skip hazard that would justify carving these out into their own fast-fail step (unlike `test_table_recognizer.py` or the judge-loop cluster, which guard genuinely slow/flaky surfaces). The existing blanket sweep already fails fast (`-x`) on the first failure anywhere in `tests/`, which covers these files adequately at Tier 1.

`tests/test_env_contract.py` already has its own dedicated fast-fail step (line 89, job `contract-and-fast-tests`). If test-strategist's optional `JSON_STRUCTURED_TRANSLATION_ENABLED` default-true/flag-off row lands in that file (test-plan.md line 55, conditional on implementation-plan confirming the flag — it did land), it is covered automatically because the step already targets the whole file by name, not by test class. No workflow edit needed for that file.

## Required Check Policy
`contract-validate`, the new env-sync step, and the line-134 blanket sweep in `contract-and-fast-tests` are merge-blocking (Tier 1). `full-regression` is Tier 2 informational-that-escalates per existing repo policy (new failures introduced by this change block; pre-existing failures do not, per CLAUDE.md pending-task rules). No new Tier 2+ named gate is introduced — this change adds no new IR field, renderer path, or benchmark surface that the existing golden/renderer/expansion gates weren't already built for; those gates are unaffected because they exercise `TranslatableDocument` IR before serialization, not the wire format.

## Contract-drift caveat (schema-version bumps)
Three contracts were bumped in this change (data-shape 0.18.0, business-rules 0.30.0, env 0.19.0). `cdd-kit validate --contracts` checks contract-internal shape/reference conformance; it does **not** verify that a bumped `schema-version` has a paired `contracts/CHANGELOG.md` entry — there is no such validator in this repo today (confirmed against the gate steps actually present in `contract-driven-gates.yml`; the only sync-checked pairs are the flag-presence greps for named env vars). If a CHANGELOG entry were missing, CI would stay green. This is an accepted, pre-existing gap, not something this change introduces or is scoped to fix — flagging it here for visibility only.

## Tier-floor override
This change's env var (`JSON_STRUCTURED_TRANSLATION_ENABLED`) and its documentation trip the known `cdd-kit gate` tier-floor false-positive vocabulary (`flag`, `rollback`, `kill-switch`). Use `tier-floor-override` with the rationale already on record in `change-classification.md` §Tier: the mandatory per-request never-fail fallback (BR-111/BR-112) is the de-risking factor that keeps this Tier 1 rather than Tier 0, and the flag is an additional instant-revert control, not evidence of unmitigated risk.

## Accepted risk — not caught by any CI gate
Per design.md §Open Risks: a systemic quality regression on **well-formed-but-schema-valid** JSON (e.g. the model reliably returns grammatically valid `{"translation": …}` that is a bad translation) is invisible to every gate in this plan — the fallback only fires on malformed/unparseable/echoed-source JSON, and no gate in this repo scores translation quality against a ground truth for this path. The `JSON_STRUCTURED_TRANSLATION_ENABLED` kill-switch is the only mitigation, and it is manual/operator-triggered, not CI-triggered. This is accepted risk, recorded here per design.md, not deferred to a future gate — no Tier 3/4 nightly or weekly gate is added because there is no real-infra or soak surface in scope (test-plan.md: call volume explicitly out of scope) that would make such a gate meaningful yet.

## Promotion Policy
No gate promotions in this change. No informational gate is introduced that could later promote to required; the one new step (env-sync) is required from the start, matching its two precedents (`DEEPSEEK_ENABLED`, `JUDGE_ENABLED`).

## Rollback Policy
Two independent rollback layers, per design.md §Migration/Rollback: (1) per-request automatic fallback to the legacy pipe-grid/plain-text pipeline on any malformed/schema-invalid/echoed-source reply — no operator action; (2) `JSON_STRUCTURED_TRANSLATION_ENABLED=0` (or `false`) reverts both paths to byte-for-byte pre-change behavior instantly, no redeploy, no data migration to reverse (none exists — wire-format-only change). No CI gate change is needed to support either rollback path; both are runtime behaviors already covered by test-plan.md's data-boundary/resilience rows.

## Merge Eligibility
mergeable — once the new env-sync step is green, the blanket `contract-and-fast-tests` sweep (line 134) passes with the new/extended test files included, `cdd-kit validate --contracts` passes, and `full-regression` shows no new failures. `openapi export --check` is unaffected (no API surface, per Established facts).
