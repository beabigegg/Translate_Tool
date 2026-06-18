# Contracts Changelog

All notable contract surface changes belong here.
Format: Keep-a-Changelog (https://keepachangelog.com/).
Versions are semantic per contract type.

While a contract is at 0.x (draft), entries here are optional.
Once a contract reaches 1.0.0, every schema-version bump must have
a corresponding entry below.

## [business 0.6.0] — 2026-06-18
Added: BR-28 (term-state-machine — four-state lifecycle and allowed transitions). Added: BR-29 (term-injection-gate — approved-only default, optional loose gate via TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED). Added: BR-30 (llm-confidence-cap — _LLM_CONFIDENCE_CAP=0.85). Added: BR-31 (term-conflict-strategy-rejected-protection — rejected terms protected by overwrite/merge strategies). Added: Table G (term export status filter), Table H (injection gate decision table), Table I (conflict strategy decision table).

## [env 0.3.0] — 2026-06-18
Added: TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED (bool, default false) and TERM_INJECT_CONF_THRESHOLD (float, default 0.9) — term injection loose gate vars. Updated: .env.example.template and env.schema.json.

## [api 0.4.1] — 2026-06-18
Added: schema authoring rule in `## Schemas` comment block — map/dict fields must use type `string` (not `object`) with "serialized as JSON map of <key> -> <value>" note; `cdd-kit openapi export` rejects `object` type. Non-breaking additive note.

## [api 0.4.0] — 2026-06-18
Added: POST /terms/reject and POST /terms/flag-needs-review endpoints (TermRejectRequest body; 200 on success, 404 on not found). Added: TermRejectRequest schema. Extended: TermStatsResponse with needs_review, approved, rejected, by_status fields (additive, non-breaking). Note: GET /terms/export status param now accepts needs_review and rejected in addition to approved and unverified. Updated: api-inventory.md with two new routes.

## [data 0.3.0] — 2026-06-18
Added: Term.status valid-value table (unverified, needs_review, approved, rejected). Added: TermStatsResponse data shape table (additive: needs_review, approved, rejected, by_status fields). Updated: term export format note to include needs_review and rejected status values.

## [api 0.2.0] — 2026-06-17
Added: `RouteInfoEntry.provider` (nullable string — provider ID selected for this route group). Added: `JobStatus.provider` (nullable string — provider ID that processed the job). Added: `JobStatus.term_summary` (nullable — extraction count map). All additive optional fields; non-breaking.

## [api 0.1.0] — 2026-04-27
Initial draft.

## [css 0.1.0] — 2026-04-27
Initial draft.

## [env 0.2.0] — 2026-06-17
Added: `PANJIT_LLM_BASE_URL`, `PANJIT_API`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_API`, `DEEPSEEK_ENABLED` — cloud LLM provider credentials. Filled: `## Secret Policy` and `## Deployment Sync Policy`. Updated: `.env.example.template` with all documented vars. Updated: `env.schema.json` with all vars (6 existing + 5 new).

## [env 0.1.0] — 2026-04-27
Initial draft.

## [data 0.2.0] — 2026-06-17
Added: `JobStatus.provider` optional column (nullable string — provider ID used for the job). Added cross-reference to api-contract.md for full JobStatus field table.

## [data 0.1.0] — 2026-04-27
Initial draft.

## [business 0.2.0] — 2026-06-17
Updated: BR-4 (model-auto-routing) — now config-driven via providers.yml; removed hardcoded _ROUTING_TABLE reference. Added: BR-12..BR-17 (provider registry, default routing, fallback chain, offline detection, attribution, secret safety). Added: Table C (provider fallback decision table).

## [business 0.1.0] — 2026-04-27
Initial draft.

## [ci 0.1.0] — 2026-04-27
Initial draft.
