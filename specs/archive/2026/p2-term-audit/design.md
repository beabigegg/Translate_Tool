# Design: p2-term-audit

## Summary
Add a read-only terminology audit that measures, per completed job, whether
`approved` glossary terms actually landed in the translated output and whether
any `rejected` terms leaked in. The audit attaches at the exact same
`post_translate_hook` seam already used by `quality_evaluator.py`: the job worker
already accumulates `(block_id, src, mt)` tuples into a single `qe_blocks` list
via `post_translate_hook=qe_blocks.extend`. The new `term_audit.py` consumes that
same accumulated `mt` text plus the job's targets/domain, queries `term_db` for
the relevant approved/rejected sets, performs case-insensitive exact matching by
default, and produces a `TerminologyAuditResult` attached to the in-memory
`JobRecord` (a new `audit` field) — the same place and lifecycle as
`JobQualityRecord`. No translations are mutated, no endpoint, env var, or DB
migration is added.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Term audit module (new) | `app/backend/services/term_audit.py` | New `audit_terms(blocks, targets, domain, term_db, ...) -> TerminologyAuditResult`; pure read-only inspection + matching |
| Job worker | `app/backend/services/job_manager.py` | Add `audit` field to `JobRecord`; after the route-group loop (same site as QE scoring), call `audit_terms` over the existing `qe_blocks` and attach result. No new accumulator/hook. |
| Term DB query | `app/backend/services/term_db.py` | Reuse existing `get_approved(target_lang, domain)`; add a `get_rejected(...)` read query mirroring `get_approved` (rejected set is not currently exposed) |
| Business rules | `contracts/business/business-rules.md` | Add BR-59..BR-61 (audit definition, match algorithm default, safe-degradation) |
| Data shape | `contracts/data/data-shape-contract.md` | Add `TerminologyAuditResult` shape + `JobRecord.audit` optional field under a new "Terminology Audit" section |
| Tests (new) | `tests/test_term_audit.py` | Matching + seam wiring + result-shape tests |

## Key Decisions

**D-1 (matching algorithm):** Default is per-classifier case-insensitive **exact**
substring match of each approved term's `target_text` against the block `mt`
text. This requires zero NLP dependency, is deterministic, and aligns with the
existing deterministic glossary-match guarantee (BR-41). Lemmatized matching is
an **optional, configurable** mode (parameter / config flag, default off), never
the default. → Rejected: lemmatized-by-default — pulls a heavy mandatory NLP
dependency into a path that runs on every job and contradicts the
no-heavy-dep constraint; also non-deterministic across library versions.

**D-2 (data-flow seam):** `term_audit` runs over the **same** `qe_blocks`
accumulator populated by `post_translate_hook=qe_blocks.extend` inside
`process_files`, invoked from the post-loop section of `_run_job` (immediately
adjacent to the QE scoring block). It MUST NOT be wired through
`translate_document()` or any higher-level wrapper. → Rejected: attaching via
`translate_document()` — that wrapper does not reach the processor
`post_translate_hook` seam, so a test calling it would pass tautologically while
the audit never sees real blocks (CLAUDE.md wrong-entry-point lesson;
see `tests/test_translation_strategy.py::test_qe_hook_called_after_translation`).
→ Rejected: a second parallel hook — duplicates the seam the QE path already
proves; reuse the one accumulator.

**D-3 (report integration):** The result is attached as a new optional
`audit: Optional[TerminologyAuditResult]` field on the in-memory `JobRecord`,
parallel to `quality: Optional[JobQualityRecord]`. It reuses the existing
job-level audit/qa data structure documented in data-shape-contract.md — no new
parallel report file, format, or serialization surface. → Rejected: emitting a
separate qa-report artifact — creates a second source of truth for job-level
quality data and diverges from the QE record's lifecycle.

**D-4 (lemmatized library, only if D-1 optional mode enabled):** When the
optional lemmatized mode is turned on, use the **already-present `blingfire`**
tokenizer (used in `orchestrator.py` for sentence splitting) for lightweight
normalization, plus simple suffix-stripping; no spaCy/NLTK. The lemmatized path
imports its helper lazily inside `term_audit.py` so the default exact path loads
nothing extra. → Rejected: spaCy/NLTK — heavy mandatory model downloads,
disproportionate for an optional audit refinement.

## Data Model — TerminologyAuditResult
| field | type | notes |
|---|---|---|
| terminology_hit_rate | float | `matched_approved / total_approved`; `1.0` when `total_approved == 0` (vacuously satisfied) |
| unapplied_terms | list[str] | approved `source_text`/`target_text` keys whose `target_text` did not appear in any block |
| rejected_injections | list[str] | rejected `target_text` values that DID appear in output (leaks) |
| total_approved | int | count of approved terms in scope (targets × domain) |
| matched_approved | int | count of approved terms whose `target_text` was found |

Attached as `JobRecord.audit`; in-memory only (same lifecycle as
`JobQualityRecord`), not part of any `TranslatableDocument` wire schema.

## Migration / Rollback
No DB migration (read-only over existing `terms` table; only adds a
`get_rejected` SELECT). No schema/wire change to IR or job persistence — `audit`
is an additive optional in-memory field, backward-compatible with existing jobs
(defaults to `None`). Rollback is removal of the `term_audit.py` call site and
the `audit` field; nothing persists, so no data cleanup is required. The audit
is inert by construction (read-only), so even if it raises it must be caught and
recorded as an empty/unavailable result without failing the job (mirrors BR-56).

## Open Risks
- `.cdd/code-map.yml` was not consulted (not present in allowed paths / not
  verified this session); component locations were grounded by direct reads of
  the allowed files instead. If the code-map is stale, confirm no other consumer
  of `post_translate_hook` exists before implementation.
- Non-IR `block_id` instability (BR-58) does not affect the audit (it matches on
  `mt` text, not `block_id`), but if a future change keys audit results by block,
  revisit BR-58 coupling.
- D-1 exact substring matching can over-count when a rejected term is a substring
  of an approved term's target; the matcher should prefer whole-token boundaries
  for `rejected_injections` — flag for test-strategist to pin.
