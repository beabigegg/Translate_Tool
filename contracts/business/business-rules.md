---
contract: business
summary: Business decision tables, rule inventory, and change policy for behavior updates.
owner: application-team
surface: domain-behavior
schema-version: 0.1.0
last-changed: 2026-04-27
breaking-change-policy: deprecate-2-minors
---

# Business Rules

## Rule Inventory
| rule id | name | owner | current behavior | tests |
|---|---|---|---|---|
| BR-1 | auth-policy | application-team | No authentication on any endpoint; intentional local-tool design decision. | — |
| BR-2 | num_ctx-validation | application-team | If `num_ctx` is provided, must be > 0 and within [min_num_ctx, max_num_ctx] of the resolved model_type (from VRAM_METADATA); else HTTP 422. | — |
| BR-3 | target-language-required | application-team | POST /api/jobs requires ≥ 1 non-empty target after comma-split; else HTTP 400. | — |
| BR-4 | model-auto-routing | application-team | Target languages are grouped to benchmark-optimal models via `resolve_route_groups()`; manual `profile` param overrides to a single group. | — |
| BR-5 | term-import-strategy | application-team | `strategy` must be one of `{skip, overwrite, merge, force}`. `force` overwrites approved rows; the others protect already-approved rows. | — |
| BR-6 | term-export-format | application-team | `format` must be one of `{json, csv, xlsx}`. `status` filter accepts `approved`, `unverified`, or omitted (all). | — |
| BR-7 | job-lifecycle | application-team | Job status transitions: `queued` → `running` → `{completed \| stopped \| failed}`. Cancel sets a stop flag; job transitions to `stopped`. | — |
| BR-8 | job-retention | application-team | In-memory store capped at `MAX_JOBS_IN_MEMORY=100`. Jobs expire after `JOB_TTL_HOURS=24` hours. Cleanup runs every 30 minutes. | — |
| BR-9 | supported-formats | application-team | Accepted file extensions: `.docx`, `.doc`, `.pptx`, `.xlsx`, `.xls`, `.pdf`. Legacy `.doc`/`.xls` via LibreOffice/COM conversion. | — |
| BR-10 | document-size-limits | application-team | `MAX_SEGMENTS=10_000_000`, `MAX_TEXT_LENGTH=1_000_000_000` — effectively disabled. Size limit breach surfaces as job `status: "failed"` (not an HTTP error). | — |
| BR-11 | wikidata-import-confidence | application-team | Wikidata lookup imports insert with `confidence=0.9`, `status="unverified"`, strategy `merge`. | — |

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

## Change Policy

Any business logic change must update this file, the relevant decision table, and regression tests.
