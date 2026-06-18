---
contract: env
summary: Environment variable inventory, secret handling, and deployment sync policy.
owner: platform-team
surface: runtime-config
schema-version: 0.4.0
last-changed: 2026-06-18
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
| PANJIT_LLM_BASE_URL | backend | all | no | no | | https://ollama_pjapi.theaken.com | platform-team | valid URL | yes | Panjit provider disabled if absent or blank; provider skipped in fallback chain |
| PANJIT_API | backend | all | no | yes | | <your-panjit-api-key> | platform-team | non-empty string | yes | Panjit provider disabled if absent or blank; never log this value |
| DEEPSEEK_BASE_URL | backend | all | no | no | https://api.deepseek.com | https://api.deepseek.com | platform-team | valid URL | yes | DeepSeek provider uses this base URL; required when DEEPSEEK_ENABLED=true |
| DEEPSEEK_API | backend | all | no | yes | | <your-deepseek-api-key> | platform-team | non-empty string | yes | DeepSeek provider disabled if absent or blank; never log this value |
| DEEPSEEK_ENABLED | backend | all | no | no | false | false | platform-team | boolean (true/false or 1/0) | yes | Enables DeepSeek provider in fallback chain; when false, DeepSeek is excluded regardless of DEEPSEEK_API presence |
| OLLAMA_NUM_CTX | backend | all | no | no | (none) | 4096 | platform-team | positive int | yes | Backward-compat fallback for context window. If set and the specific var (GENERAL_NUM_CTX / TRANSLATION_NUM_CTX) is not set, both types use this value. New deployments should prefer the specific vars. |
| GENERAL_NUM_CTX | backend | all | no | no | 4096 | 4096 | platform-team | positive int | yes | Context window for general-purpose model calls. Fallback chain: GENERAL_NUM_CTX → OLLAMA_NUM_CTX → 4096 |
| TRANSLATION_NUM_CTX | backend | all | no | no | 3072 | 3072 | platform-team | positive int | yes | Context window for translation-dedicated model calls. Fallback chain: TRANSLATION_NUM_CTX → OLLAMA_NUM_CTX → 3072 |
| TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED | backend | all | no | no | false | false | application-team | boolean (true/false or 1/0) | no | When true, also inject unverified terms with confidence >= TERM_INJECT_CONF_THRESHOLD into translation prompts. Migration escape hatch for deployments relying on the old confidence=1.0 bypass. |
| TERM_INJECT_CONF_THRESHOLD | backend | all | no | no | 0.9 | 0.9 | application-team | float in (0.0, 1.0] | no | Minimum confidence score for unverified terms to be included in injection when TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true. Has no effect when the flag is false. |
| LAYOUT_DETECTOR_MODEL_PATH | backend | all | no | no | (none) | /opt/models/heron-101 | platform-team | non-empty string (valid local directory path) | yes | Local path to the Docling heron-101 ONNX weights directory. When unset, falls back to HuggingFace auto-download of `docling-project/docling-layout-heron-onnx`. Set for air-gapped / Docker-preloaded deployments. Not a secret. |
| LAYOUT_DETECTOR_ENABLED | backend | all | no | no | true | false | platform-team | boolean (true/false or 1/0) | yes | Enable or disable the layout detector. When false (or 0), `round(y0,10pt)` reading-order heuristic is used for all pages. Rollback switch — set to 0 to revert to pre-p2-layout-detection parse path without a code change. |

## Public Frontend Env Policy

Variables such as `VITE_`, `NEXT_PUBLIC_`, and `PUBLIC_` are browser-exposed. Never store secrets in them.

## Secret Policy

API keys (`PANJIT_API`, `DEEPSEEK_API`) must be stored in `.env` only. `.env` is gitignored and must never be committed. `config/providers.yml` must reference these via `${PANJIT_API}` / `${DEEPSEEK_API}` interpolation only — never embed literal key values. An unresolved `${VAR}` reference must disable the affected provider, not propagate the literal template string to the endpoint. Never log secret env var values.

## Deployment Sync Policy

Any new env var must be added here and to `contracts/env/.env.example.template` and `contracts/env/env.schema.json` in the same change. Secrets (column `secret: yes`) must be provisioned out-of-band; `.env.example.template` uses placeholder values only.
