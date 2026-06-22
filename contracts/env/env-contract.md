---
contract: env
summary: Environment variable inventory, secret handling, and deployment sync policy.
owner: platform-team
surface: runtime-config
schema-version: 0.10.0
last-changed: 2026-06-22
breaking-change-policy: deprecate-2-minors
---

# Env Contract

| name | scope | environments | required | secret | default | example | owner | validation | restart required | failure behavior |
|---|---|---|---:|---:|---|---|---|---|---:|---|
| OLLAMA_BASE_URL | backend | all | no | no | http://localhost:11434 | http://localhost:11434 | platform-team | valid URL | yes | Ollama client falls back to default; local layout inference (layout_detector.py) unavailable if wrong. OLLAMA_BASE_URL is not used by the translation fallback chain. |
| TRANSLATE_TOOL_HOST | backend | all | no | no | 127.0.0.1 | 0.0.0.0 | platform-team | valid IP | yes | Server binds to wrong interface |
| TRANSLATE_TOOL_PORT | backend | all | no | no | 8765 | 8765 | platform-team | integer | yes | Server binds to wrong port |
| TRANSLATION_CACHE_ENABLED | backend | all | no | no | 1 | 1 | application-team | 0 or 1 | no | Cache disabled if falsy; performance degradation |
| MAX_JOBS_IN_MEMORY | backend | all | no | no | 100 | 100 | platform-team | positive int | no | Fewer jobs retained in memory |
| JOB_TTL_HOURS | backend | all | no | no | 24 | 24 | platform-team | positive int | no | Jobs expire sooner or later |
| PANJIT_LLM_BASE_URL | backend | all | no | no | | https://ollama_pjapi.theaken.com | platform-team | valid URL | yes | Panjit provider disabled if absent or blank; provider skipped in fallback chain. PANJIT calls (embedding and extraction) use verify_ssl=False (self-signed internal cert); set tls_verify: true in providers.yml if cert is replaced. |
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
| CRITIQUE_LOOP_ENABLED | backend | all | no | no | 1 | 1 | application-team | boolean (1/0 or true/false) | no | When false (or 0), translate-then-critique self-refinement loop is skipped; initial draft returned without critique pass. Glossary substitution (BR-41) still runs. Rollback switch for p2-prompt-fewshot-glossary. |
| CRITIQUE_MAX_ITERATIONS | backend | all | no | no | 3 | 3 | application-team | positive integer | no | Maximum translate-then-critique loop iterations per translatable segment. Loop terminates at this count even if critique suggests further revision. See BR-44. |
| CRITIQUE_TIMEOUT_SECONDS | backend | all | no | no | 60 | 60 | application-team | positive float (seconds) | no | Per-segment critique loop wall-clock timeout. On timeout, loop degrades to last valid draft; job does not fail. See BR-44. |
| CHUNK_OVERLAP_TOKENS | backend | all | no | no | 50 | 50 | application-team | positive integer | no | Number of tokens of overlap shared between adjacent chunks during long-document chunking. Has no effect when the full document fits within the LLM context window (single-chunk path). See BR-47 and BR-49. |
| QE_ENABLED | backend | all | no | no | false | false | application-team | boolean (true/false or 1/0) | yes | When false (or 0), QE scoring step is skipped entirely; GET /jobs/{id}/quality returns status: "disabled". Opt-in by default — set to true to enable. See BR-57. |
| QE_MODEL_NAME | backend | all | no | no | Unbabel/wmt22-cometkiwi-da | Unbabel/wmt22-cometkiwi-da | application-team | non-empty string | yes | COMET/xCOMET model identifier (HuggingFace hub name or local path). Used only when QE_ENABLED=true. See BR-54. LICENSE WARNING: default model wmt22-cometkiwi-da and all CometKiwi/xCOMET models are CC-BY-NC-SA 4.0 (non-commercial). Legal review required before enabling in commercial deployments. For commercial use, consider wmt22-comet-da (Apache-2.0, reference-based). |
| QE_DEVICE | backend | all | no | no | cpu | cpu | application-team | string (cpu, cuda, mps) | yes | Inference device for QE model. Accepted values: cpu, cuda, mps. Falls back to cpu on invalid value with WARNING logged. Ignored when QE_ENABLED=false. See BR-57. |
| TERM_EMBEDDING_MODEL | backend | all | no | no | Qwen3-Embedding-8B | Qwen3-Embedding-8B | application-team | non-empty string | yes | Embedding model name on the PANJIT endpoint used to vectorise source segments for term DB lookup. See BR-62. |
| TERM_EMBEDDING_THRESHOLD | backend | all | no | no | 0.75 | 0.75 | application-team | float in (0.0, 1.0] | yes | Cosine similarity cutoff for a DB hit; values ≥ threshold inject without extraction call. Default: 0.75. See BR-62. |
| TERM_EXTRACTION_MODEL | backend | all | no | no | gemma4:latest | gemma4:latest | application-team | non-empty string | yes | LLM model name on the PANJIT endpoint used for term extraction on DB miss. See BR-62. |
| JUDGE_ENABLED | backend | all | no | no | false | false | application-team | boolean (true/false or 1/0) | yes | When false (or 0), judge step is skipped entirely; GET /jobs/{id}/judge returns status: "disabled". Opt-in by default — set to true to enable Gemma judge pass. See BR-74. |
| JUDGE_MODEL | backend | all | no | no | gemma3 | gemma3 | application-team | non-empty string | no | Ollama model name for the LLM judge. Used only when JUDGE_ENABLED=true. Must be a model pulled locally via Ollama (never routed through cloud providers). See BR-72, D4 in design.md. |
| JUDGE_MAX_ITERATIONS | backend | all | no | no | 3 | 3 | application-team | positive integer | no | Maximum re-translation iterations in the judge loop per job. Loop terminates at this count even if score never reaches 高. See BR-73. |

## Public Frontend Env Policy

Variables such as `VITE_`, `NEXT_PUBLIC_`, and `PUBLIC_` are browser-exposed. Never store secrets in them.

## Secret Policy

API keys (`PANJIT_API`, `DEEPSEEK_API`) must be stored in `.env` only. `.env` is gitignored and must never be committed. `config/providers.yml` must reference these via `${PANJIT_API}` / `${DEEPSEEK_API}` interpolation only — never embed literal key values. An unresolved `${VAR}` reference must disable the affected provider, not propagate the literal template string to the endpoint. Never log secret env var values.

**DeepSeek user-supplied key (settings-page-cloud-redesign, BR-65):** The DeepSeek API key entered via the Settings UI is a user-supplied, per-session secret that is distinct from the backend `DEEPSEEK_API` env var. It is stored ONLY in browser `localStorage` under key `deepseek_api_key`. It is transmitted per-request in the request body field `deepseek_api_key` to `POST /api/providers/test-translation`. The backend MUST NOT fall back to reading `DEEPSEEK_API` from `.env` for this surface. The backend MUST NOT persist, log, or cache this key beyond the lifetime of the single request. The frontend MUST NOT auto-populate the field from a backend env var — it reads only from `localStorage`. This pattern intentionally trades the inconvenience of re-entry across sessions for avoiding server-side secret storage for a user-owned key.

## Deployment Sync Policy

Any new env var must be added here and to `contracts/env/.env.example.template` and `contracts/env/env.schema.json` in the same change. Secrets (column `secret: yes`) must be provisioned out-of-band; `.env.example.template` uses placeholder values only.

Gate grep commands in `ci-gates.md` that assert env-var presence (e.g. the `env-sync-*` gates) must use the exact canonical names recorded in the table above. When an env var is added or renamed, update the ci-gates.md grep pattern in the same change — a stale pattern passes silently even if the var is absent from the deployment artifacts.
