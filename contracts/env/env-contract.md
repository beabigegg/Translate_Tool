---
contract: env
summary: Environment variable inventory, secret handling, and deployment sync policy.
owner: platform-team
surface: runtime-config
schema-version: 0.1.0
last-changed: 2026-04-27
breaking-change-policy: deprecate-2-minors
---

# Env Contract

| name | scope | environments | required | secret | default | example | owner | validation | restart required | failure behavior |
|---|---|---|---:|---:|---|---|---|---|---:|---|
| OLLAMA_BASE_URL | backend | all | no | no | http://localhost:11434 | http://localhost:11434 | platform-team | valid URL | yes | Ollama client falls back to default; local layout inference unavailable if wrong |
| TRANSLATE_TOOL_HOST | backend | all | no | no | 127.0.0.1 | 0.0.0.0 | platform-team | valid IP | yes | Server binds to wrong interface |
| TRANSLATE_TOOL_PORT | backend | all | no | no | 8765 | 8765 | platform-team | integer | yes | Server binds to wrong port |
| TRANSLATION_CACHE_ENABLED | backend | all | no | no | 1 | 1 | application-team | 0 or 1 | no | Cache disabled if falsy; performance degradation |
| MAX_JOBS_IN_MEMORY | backend | all | no | no | 100 | 100 | platform-team | positive int | no | Fewer jobs retained in memory |
| JOB_TTL_HOURS | backend | all | no | no | 24 | 24 | platform-team | positive int | no | Jobs expire sooner or later |

## Public Frontend Env Policy

Variables such as `VITE_`, `NEXT_PUBLIC_`, and `PUBLIC_` are browser-exposed. Never store secrets in them.

## Secret Policy

## Deployment Sync Policy
