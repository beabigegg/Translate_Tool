# Contracts Changelog

All notable contract surface changes belong here.
Format: Keep-a-Changelog (https://keepachangelog.com/).
Versions are semantic per contract type.

While a contract is at 0.x (draft), entries here are optional.
Once a contract reaches 1.0.0, every schema-version bump must have
a corresponding entry below.

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
