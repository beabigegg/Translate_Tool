---
contract: business
summary: Business decision tables, rule inventory, and change policy for behavior updates.
owner: application-team
surface: domain-behavior
schema-version: 0.7.1
last-changed: 2026-06-18
breaking-change-policy: deprecate-2-minors
---

# Business Rules

## Rule Inventory
| rule id | name | owner | current behavior | tests |
|---|---|---|---|---|
| BR-1 | auth-policy | application-team | No authentication on any endpoint; intentional local-tool design decision. | — |
| BR-2 | num_ctx-validation | application-team | If `num_ctx` is provided, must be > 0 and within [min_num_ctx, max_num_ctx] of the resolved model_type (from VRAM_METADATA); else HTTP 422. | — |
| BR-3 | target-language-required | application-team | POST /api/jobs requires ≥ 1 non-empty target after comma-split; else HTTP 400. | — |
| BR-4 | model-auto-routing | application-team | Provider and model selection is config-driven via `config/providers.yml` read at startup by `config.py`. `model_router.py` resolves model + provider from `routing.default`. Per-language overrides are sourced from `routing.rules` (language-keyed map of `{model, provider, profile}` entries, e.g. `routing.rules.Vietnamese`) when that key is present; rules are matched by `target_lang`. A manual `profile` param overrides to a single group. The legacy `_OLLAMA_ROUTING_TABLE` remains only as a no-`provider_config` fallback for backward compatibility. | — |
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
| BR-18 | per-target-language-dispatch | application-team | `resolve_route_groups()` resolves each `target_lang` in a batch independently. A mixed-language batch (e.g. `[vi, de, ko, ja]`) produces one `RouteGroup` per distinct (model, profile_id, model_type, provider) tuple; each language is matched against `routing.rules` before falling back to `routing.default`. The whole batch is never routed by `targets[0]` alone. | — |
| BR-19 | unmapped-language-fallback | application-team | A `target_lang` not matched by any entry in `routing.rules` (or when `routing.rules` is absent) falls back to `routing.default`. This must not raise an exception and must produce a deterministic result identical to a single-language job using the default route. | — |
| BR-20 | metrics-counter-lifetime | application-team | All counters (`translation_count`, `translation_latency_mean_ms`, `provider_failure_count`, `font_cache_hits`, `font_cache_misses`) are held in process memory only. They initialize to zero at process start. No external store is read or written. Counters are lost on process restart. | — |
| BR-21 | translation-count-increment | application-team | `translation_count` increments by 1 each time a translation call completes — whether the result is a success or a failure. Increment happens after the call returns, regardless of outcome. | — |
| BR-22 | translation-latency-mean | application-team | `translation_latency_mean_ms` is the arithmetic mean of all per-call elapsed wall-clock latencies in milliseconds, measured from call dispatch to provider response at the service boundary. Computed incrementally: `new_mean = ((old_mean * (n-1)) + new_latency_ms) / n` where `n` is the updated `translation_count`. When `translation_count` is 0, `translation_latency_mean_ms` is 0.0 (float, not null). | — |
| BR-23 | provider-failure-count-increment | application-team | `provider_failure_count` increments by 1 each time a provider call raises a connection exception, a timeout exception, or returns HTTP 401/403 (matching BR-15 offline-detection criteria). It does not increment on success. It increments once per failed provider attempt — a 3-provider fallback chain with all three failing increments `provider_failure_count` by 3. | — |
| BR-24 | font-cache-hit-miss-increment | application-team | `font_cache_hits` increments by 1 each time a font buffer load returns a value already in the `lru_cache` (cache hit). `font_cache_misses` increments by 1 each time the font buffer is read from disk (cache miss). Exactly one of the two counters increments on each font buffer access. | — |
| BR-25 | translation-failure-placeholder | application-team | When a segment translation fails (any translation mode, including `SENTENCE_MODE`), the value stored in `tmap` for that block is `[Translation failed|{tgt}] {original_text}` — a block-level string containing the target language tag and the unmodified original source text. This format applies regardless of whether `SENTENCE_MODE` is active. The format is the detection anchor for `verify_and_fill_tmap`; any deviation makes the block non-retryable. | tests/test_sentence_mode_consistency.py |
| BR-26 | per-segment-done-fail-counting | application-team | `done` and `fail_cnt` are incremented once per segment inside the per-segment translation loop, regardless of translation mode. A mid-loop or mid-batch stop must not cause `done` to exceed the number of segments actually processed. `SENTENCE_MODE` and non-`SENTENCE_MODE` paths must produce identical `done`/`fail_cnt` values on identical input with identical stop timing. | tests/test_sentence_mode_consistency.py |
| BR-27 | stop-flag-propagation | application-team | When a job cancellation stop flag is set, it must be passed into `translate_blocks_batch` (and threaded through `BatchTranslator`) so mid-batch work halts as soon as the flag is detected between individual translation calls. After a batch completes (or halts), the outer per-target loop must check the stop flag and break immediately — no further target languages are processed once the stop flag is set. This applies to both `SENTENCE_MODE` and non-`SENTENCE_MODE` paths. | tests/test_sentence_mode_consistency.py |
| BR-28 | term-state-machine | application-team | Valid `Term.status` values: `unverified`, `needs_review`, `approved`, `rejected`. Allowed transitions: any status → `approved` (via `approve()`); any status → `rejected` (via `reject()`); any status → `needs_review` (via `flag_needs_review()`); `rejected` or `needs_review` → `approved` (via `approve()`). `edit_term()` sets status to `approved` directly (implicit approval). | tests/test_term_state_machine.py |
| BR-29 | term-injection-gate | application-team | Default (strict): only `status='approved'` terms are injected into translation prompts. Optional loose gate (`TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true`): also inject `status='unverified'` terms with `confidence >= TERM_INJECT_CONF_THRESHOLD`. `rejected` and `needs_review` terms are NEVER injected regardless of the loose gate flag. The `confidence=1.0` bypass is removed; LLM self-assessed confidence no longer grants injection. | tests/test_term_state_machine.py |
| BR-30 | llm-confidence-cap | application-team | LLM-extracted confidence is capped at `_LLM_CONFIDENCE_CAP = 0.85` in `term_extractor.py`. This prevents LLM self-assessment from matching human-verified confidence. Human approval (`approve()`) is the canonical verification method. | tests/test_term_state_machine.py |
| BR-31 | term-conflict-strategy-rejected-protection | application-team | `insert()` with strategy `overwrite` or `merge`: skip (return `'skipped'`) if existing term has `status='approved'` OR `status='rejected'`. `insert()` with strategy `force`: overwrites regardless of status, including `rejected`. Human-rejected terms are not silently re-imported by bulk imports unless `force` is used. | tests/test_term_state_machine.py |
| BR-32 | local-inference-privacy | platform-team | Page images produced by rasterising PDF pages (via PyMuPDF `page.get_pixmap()`) during layout detection MUST remain local. They must never be serialised, persisted to disk, sent over any socket, or logged. The rasterised array is created, consumed, and discarded entirely within `layout_detector.py`. The module must contain no network-client, HTTP, socket, or cloud-SDK imports. | tests/test_pdf_parser.py |
| BR-33 | layout-detection-fail-soft | platform-team | When layout detection fails for any page (causes: model file absent, ONNX session load error, out-of-memory, corrupt or unrasterisable page image), the system MUST fall back to the `round(y0,10pt)` reading-order heuristic for that affected page and continue the job. The failure MUST be logged at WARNING level, including the page number and failure reason. No page image or page content may appear in the log message. A detector unavailable at startup is surfaced once as a WARNING; it does not fail the process. | tests/test_pdf_parser.py |
| BR-34 | renderer-primary-fallback | application-team | fitz is the default primary renderer for PDF output. When the fitz render path raises an unhandled exception, the system MUST fall back to the ReportLab renderer and produce a rendered PDF output without aborting the job. The fallback MUST be logged at WARNING level, including the exception type and the document identifier. The ReportLab path is never invoked unless fitz fails; both paths consume the same `TranslatableDocument` IR via the shared IR-bbox reflow component. | tests/test_pdf_generator.py |
| BR-35 | renderer-ir-consumption-consistency | application-team | For any given `TranslatableDocument` IR, the fitz primary path and the ReportLab fallback path MUST make identical element-level decisions for element inclusion/exclusion, reading-order resolution, and text-source selection (translated_content vs. content fallback). Layout pixel-position and font rendering may differ between paths within the documented numeric tolerance (defined in design.md). An unknown `element_type` value MUST be treated as `text` on both paths (passthrough, do not skip, do not raise). | tests/test_ir_pipeline_decoupling.py |

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

### Table D — config-driven per-language routing (BR-18, BR-19)
| condition | behavior | test id |
|---|---|---|
| `target_lang` matches an entry in `routing.rules` | model/provider/profile resolved from that rule; grouped accordingly | — |
| `target_lang` not in `routing.rules` (or `routing.rules` absent) | falls back to `routing.default`; no exception | — |
| mixed batch `[vi, de, ko, ja]` with distinct per-language rules | each language resolves independently; 1–4 RouteGroups possible | — |
| `provider_config` is None | legacy `_OLLAMA_ROUTING_TABLE` path used; behavior unchanged | — |

### Table E — metrics counter semantics (BR-20 through BR-24)
| condition | counter affected | delta | test id |
|---|---|---|---|
| Translation call completes (success) | `translation_count`, `translation_latency_mean_ms` | count +1; mean updated per BR-22 | — |
| Translation call completes (failure / exception) | `translation_count`, `translation_latency_mean_ms`, `provider_failure_count` | count +1; mean updated per BR-22; failure +1 | — |
| Provider raises connection or timeout exception | `provider_failure_count` | +1 per failed attempt | — |
| Provider returns HTTP 401 or 403 | `provider_failure_count` | +1 per failed attempt | — |
| Provider returns non-error response | `provider_failure_count` | no change | — |
| Font buffer returned from lru_cache (cache hit) | `font_cache_hits` | +1 | — |
| Font buffer loaded from disk (cache miss) | `font_cache_misses` | +1 | — |
| Process starts (or restarts) | all counters | reset to 0 | — |
| `translation_count` is 0 | `translation_latency_mean_ms` | must read 0.0 (float, not null/undefined) | — |

### Table F — translation failure placeholder and stop propagation (BR-25, BR-26, BR-27)
| condition | behavior | test id |
|---|---|---|
| Segment translation fails in non-`SENTENCE_MODE` | `tmap[(tgt, text)]` set to `[Translation failed\|{tgt}] {text}` | tests/test_translation_strategy.py |
| Segment translation fails in `SENTENCE_MODE` | `tmap[(tgt, text)]` set to `[Translation failed\|{tgt}] {text}` (same format; original text included) | tests/test_sentence_mode_consistency.py |
| Segment translation succeeds | `done` incremented by 1 inside the per-segment loop | tests/test_metrics_counters.py |
| Segment translation fails | `fail_cnt` incremented by 1 inside the per-segment loop | tests/test_sentence_mode_consistency.py |
| Stop flag set before batch starts | `translate_blocks_batch` receives the flag; exits after the next per-sentence boundary | tests/test_sentence_mode_consistency.py |
| Stop flag set mid-batch | `translate_blocks_batch` detects flag between per-sentence calls and halts remaining sentences | tests/test_sentence_mode_consistency.py |
| Stop flag set; batch completes or halts | outer per-target loop breaks; no further target languages are translated | tests/test_sentence_mode_consistency.py |
| `translate_blocks_batch` called with no stop_flag (legacy callers) | behaves as before; `stop_flag=None` default means no cancellation check | tests/test_translation_strategy.py |

## Term State Machine

### Table G — term export status filter (BR-6 extended, BR-28)
| condition | behavior | test id |
|---|---|---|
| `status` omitted | all terms exported | — |
| `status = approved` | only `approved` terms exported | — |
| `status = unverified` | only `unverified` terms exported | — |
| `status = needs_review` | only `needs_review` terms exported | — |
| `status = rejected` | only `rejected` terms exported | — |
| `status` not in {approved, unverified, needs_review, rejected} | treated as no filter (all exported) | — |

### Table H — term injection gate (BR-29)
| condition | behavior | test id |
|---|---|---|
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false` (default), term `status='approved'` | term included in injection | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false` (default), term `status='unverified'`, any confidence | term NOT included | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false` (default), term `status='rejected'` | term NOT included | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false` (default), term `status='needs_review'` | term NOT included | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true`, term `status='unverified'`, `confidence >= TERM_INJECT_CONF_THRESHOLD` | term included | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true`, term `status='unverified'`, `confidence < TERM_INJECT_CONF_THRESHOLD` | term NOT included | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true`, term `status='rejected'` | term NOT included (rejected never injected) | tests/test_term_state_machine.py |
| `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true`, term `status='needs_review'` | term NOT included (needs_review never injected) | tests/test_term_state_machine.py |

### Table I — term conflict strategy (BR-5 extended, BR-31)
| condition | behavior | test id |
|---|---|---|
| `strategy = skip`, term exists | existing row kept; new term not inserted | — |
| `strategy = overwrite` or `merge`, existing term `status='approved'` | skip; return `'skipped'` | tests/test_term_state_machine.py |
| `strategy = overwrite` or `merge`, existing term `status='rejected'` | skip; return `'skipped'` | tests/test_term_state_machine.py |
| `strategy = overwrite` or `merge`, existing term `status='unverified'` or `'needs_review'` | update allowed | — |
| `strategy = force`, any existing status including `rejected` | overwrite regardless | tests/test_term_state_machine.py |

### Table J — layout detection failure handling (BR-32, BR-33)

| condition | behavior | test id |
|---|---|---|
| `LAYOUT_DETECTOR_ENABLED=false` or `0` | layout detection skipped for all pages; `round(y0,10pt)` heuristic used for all `reading_order` assignment | — |
| `LAYOUT_DETECTOR_ENABLED=true` (default), model weights found | detection runs; `element_type` and `reading_order` written from detector output | — |
| Model weights absent at startup | WARNING logged once; detection skipped for all pages; heuristic fallback used; job continues | — |
| ONNX session load error (any page) | WARNING logged (page number + reason); heuristic fallback used for that page; job continues | — |
| Out-of-memory on inference (any page) | WARNING logged (page number + reason); heuristic fallback used for that page; job continues | — |
| Corrupt or unrasterisable page image | WARNING logged (page number + reason); heuristic fallback used for that page; job continues | — |
| Inference failure on page N | pages before N retain detector-assigned values; page N and subsequent use heuristic | — |
| No-text-layer (scanned) PDF | layout detection not invoked; existing out-of-scope (P3-1) behavior unchanged | — |

### Table K — renderer primary/fallback selection (BR-34, BR-35)
| condition | behavior | test id |
|---|---|---|
| fitz render path completes without exception | output PDF produced via fitz; ReportLab not invoked | tests/test_pdf_generator.py |
| fitz render path raises an unhandled exception | WARNING logged (exception type + document id); ReportLab path invoked; PDF produced via ReportLab | tests/test_pdf_generator.py |
| ReportLab fallback also raises | job transitions to `status: "failed"`; exception propagated to job manager | tests/test_pdf_generator.py |
| IR `bbox` is null for an element | both paths apply documented fallback placement; neither raises | tests/test_ir_pipeline_decoupling.py |
| IR `reading_order` is null for an element | both paths apply positional sort fallback; neither raises | tests/test_ir_pipeline_decoupling.py |
| IR `element_type` is an unknown value | both paths treat element as `text`; neither raises; element rendered | tests/test_ir_pipeline_decoupling.py |
| IR `translated_content` is null | both paths render `content` (source text) instead; neither raises | tests/test_ir_pipeline_decoupling.py |

## Change Policy

Any business logic change must update this file, the relevant decision table, and regression tests.
