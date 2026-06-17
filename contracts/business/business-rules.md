---
contract: business
summary: Business decision tables, rule inventory, and change policy for behavior updates.
owner: application-team
surface: domain-behavior
schema-version: 0.2.0
last-changed: 2026-06-17
breaking-change-policy: deprecate-2-minors
---

# Business Rules

## Rule Inventory
| rule id | name | owner | current behavior | tests |
|---|---|---|---|---|
| BR-1 | auth-policy | application-team | No authentication on any endpoint; intentional local-tool design decision. | — |
| BR-2 | num_ctx-validation | application-team | If `num_ctx` is provided, must be > 0 and within [min_num_ctx, max_num_ctx] of the resolved model_type (from VRAM_METADATA); else HTTP 422. | — |
| BR-3 | target-language-required | application-team | POST /api/jobs requires ≥ 1 non-empty target after comma-split; else HTTP 400. | — |
| BR-4 | model-auto-routing | application-team | Provider and model selection is config-driven via `config/providers.yml` read at startup by `config.py`; `model_router.py` resolves model + provider from `routing.default` and `routing.rules`. Manual `profile` param overrides to a single group. Previously hardcoded `_ROUTING_TABLE` is removed. | — |
| BR-5 | term-import-strategy | application-team | `strategy` must be one of `{skip, overwrite, merge, force}`. `force` overwrites approved rows; the others protect already-approved rows. | — |
| BR-6 | term-export-format | application-team | `format` must be one of `{json, csv, xlsx}`. `status` filter accepts `approved`, `unverified`, or omitted (all). | — |
| BR-7 | job-lifecycle | application-team | Job status transitions: `queued` → `running` → `{completed \| stopped \| failed}`. Cancel sets a stop flag; job transitions to `stopped`. | — |
| BR-8 | job-retention | application-team | In-memory store capped at `MAX_JOBS_IN_MEMORY=100`. Jobs expire after `JOB_TTL_HOURS=24` hours. Cleanup runs every 30 minutes. | — |
| BR-9 | supported-formats | application-team | Accepted file extensions: `.docx`, `.doc`, `.pptx`, `.xlsx`, `.xls`, `.pdf`. Legacy `.doc`/`.xls` via LibreOffice/COM conversion. | — |
| BR-10 | document-size-limits | application-team | `MAX_SEGMENTS=10_000_000`, `MAX_TEXT_LENGTH=1_000_000_000` — effectively disabled. Size limit breach surfaces as job `status: "failed"` (not an HTTP error). | — |
| BR-11 | wikidata-import-confidence | application-team | Wikidata lookup imports insert with `confidence=0.9`, `status="unverified"`, strategy `merge`. | — |
| BR-12 | provider-registry | application-team | `config/providers.yml` is the authoritative provider registry. `model_router.py` reads it at startup via `config.py`. A provider entry has: `id`, `type`, `enabled`, `base_url`, `api_key`, `models`, optional `role`. | — |
| BR-13 | provider-default-routing | application-team | `routing.default` in `providers.yml` defines the primary model + provider for most jobs. When `providers.yml` is absent or unreadable, `model_router` falls back to Ollama-only behavior (backward-compatible). | — |
| BR-14 | provider-fallback-chain | application-team | `fallback_chain` is an ordered list of provider IDs. If the primary provider fails, the next provider in the chain is attempted. Maximum one attempt per provider per job. First success wins. | — |
| BR-15 | provider-offline-detection | application-team | A provider is considered "offline" when an HTTP request raises a connection or timeout exception at the client boundary. Auth failures (HTTP 401/403) are also treated as offline for fallback purposes. | — |
| BR-16 | provider-attribution | application-team | The provider ID that successfully processed a job is always recorded in `JobStatus.provider`. If the job fails after all fallback providers are exhausted, `JobStatus.provider` remains null and `status` transitions to `failed`. | — |
| BR-17 | provider-secret-safety | application-team | API keys (`PANJIT_API`, `DEEPSEEK_API`) must not appear in `config/providers.yml` as literals; they must be referenced via `${VAR}` interpolation resolved at load time. An unresolved reference must disable the provider, not pass the literal string to the endpoint. | — |

## Decision Tables

### Table A — num_ctx validation (BR-2)
| condition | behavior | test id |
|---|---|---|
| `num_ctx` omitted (None) | Accepted; model default used | — |
| `num_ctx` ≤ 0 | HTTP 422: "num_ctx must be a positive integer" | — |
| `num_ctx` outside [min_num_ctx, max_num_ctx] | HTTP 422: "num_ctx must be between {min} and {max}…" | — |
| min_num_ctx ≤ `num_ctx` ≤ max_num_ctx | Accepted | — |

### Table B — term import strategy (BR-5)
| condition | behavior | test id |
|---|---|---|
| `strategy` not in {skip, overwrite, merge, force} | HTTP 400: "strategy must be skip, overwrite, merge, or force" | — |
| `strategy = skip` | Existing rows kept; only new terms inserted | — |
| `strategy = overwrite` or `merge` | Updates allowed; already-approved rows protected | — |
| `strategy = force` | Overwrites everything including approved rows | — |

### Table C — provider fallback chain (BR-14, BR-15, BR-16)
| condition | behavior | test id |
|---|---|---|
| primary provider returns success | `JobStatus.provider` set to primary provider ID; chain not consulted | — |
| primary provider raises connection/timeout exception | next provider in `fallback_chain` attempted; primary skipped | — |
| primary provider returns HTTP 401/403 | treated as offline; next provider attempted | — |
| all providers in chain exhausted without success | job transitions to `status: "failed"`; `JobStatus.provider` remains null | — |
| `providers.yml` absent or all providers have `enabled: false` | falls back to `OllamaClient`-only behavior; `JobStatus.provider` set to `"ollama-local"` | — |
| `DEEPSEEK_ENABLED=false` | DeepSeek excluded from chain regardless of `DEEPSEEK_API` presence | — |

## Change Policy

Any business logic change must update this file, the relevant decision table, and regression tests.
