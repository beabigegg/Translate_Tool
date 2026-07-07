# Contracts Changelog

All notable contract surface changes belong here.
Format: Keep-a-Changelog (https://keepachangelog.com/).
Versions are semantic per contract type.

While a contract is at 0.x (draft), entries here are optional.
Once a contract reaches 1.0.0, every schema-version bump must have
a corresponding entry below.

## [css 0.3.1] — 2026-07-08
Added: `StageDetailPanel`/`StageBadge` component-rules row (JudgePanel precedent) — single-column panel inside `TranslationProgress.jsx` rendering `current_stage`/current-segment content incl. the judge sub-state (tier badge, attempt counter, scoring/retranslating substep); explicit "renders nothing when no current-segment detail" visibility rule, mirroring `JudgePanel`'s disabled/unavailable rule. Colors via CSS vars only. Added in change `translation-progress-detail-ui`.

## [api 0.10.2] — 2026-07-08
Added: `JobStatus` — 8 new optional/nullable fields (`current_stage` plus `current_segment_source`, `current_segment_draft`, `current_segment_qe_score`, `current_segment_adopted`, `current_segment_judge_tier`, `current_segment_judge_attempt`, `current_segment_judge_substep`); `current_stage` enum is `translate`/`critique`/`qe`/`adopt`/`judge`. Closed pre-existing drift: `status_detail` and `layout_viz_available` (already live in `app/backend/api/schemas.py`) are now documented in the `JobStatus` schema table. Updated `GET /jobs/{job_id}` endpoint note with the new fields' null-cases. Additive-only — no existing field renamed/removed/retyped. Regenerated `openapi.yml`/`openapi.json`. Added in change `translation-progress-detail-ui`.

## [data 0.17.2] — 2026-07-08
Added: `JobStatus / JobRecord — current-segment snapshot fields` optional-columns entry — the 8 fields backing the additive current-segment snapshot (translate/critique/qe/adopt/judge), documenting null cases and the single-overwritten-struct (never a list/history) invariant per ADR-0010. Backend-only origin; never supplied by clients. Added in change `translation-progress-detail-ui`.

## [business 0.24.2] — 2026-07-08
Added: BR-105 (`eta-multi-phase-pipeline`) — `GET /jobs/{job_id}`'s `eta_seconds` is now a 3-term sum (translate / critique+QE / judge), each term using its own observed per-phase rate once that phase has started, else a coarse pre-observed estimate scaled by that phase's max-iterations config; critique+QE term omitted when both are disabled; judge term omitted when `JUDGE_ENABLED=false` or the winning provider is `deepseek` (BR-97 mirror). Replaces the prior single-phase extrapolation internally; `eta_seconds`'s type/nullability is unchanged. Added in change `translation-progress-detail-ui`.

## [business 0.24.1] — 2026-07-07
Added: Table Y (QA/quality-pipeline mechanism relationships) — cross-reference table documenting how the in-line critique loop (BR-89, BR-90), post-job bulk COMET scoring (BR-55, BR-56, permanently dashboard-only after the former post-job re-translation bridge was retired), and LLM-as-judge (BR-72 through BR-77, BR-97 through BR-100) relate; records that mechanisms (1) and (3) share no state and can disagree by design. No new rule ids; no behavior change. Added in change qa-mechanism-docs.

## [api 0.10.1] — 2026-07-07
Updated: JobStatus.quality_score_avg note — added advisory/non-gating clarification (informational dashboard value; never triggers re-translation). No schema/type/nullability change. Added in change qa-mechanism-docs.

## [data 0.17.1] — 2026-07-07
Updated: Quality Evaluation (QE) Score Representation intro — added advisory/non-gating clarification for JobQualityRecord (dashboard-only; never triggers re-translation; cross-reference to business-rules.md Table Y; notes the retired post-job re-translation bridge). No schema change. Added in change qa-mechanism-docs.

## [api 0.9.0] — 2026-06-27
Added: `JobStatus.warnings` — optional `string[]` field (null/empty when no degradation; two verbatim values: fitz→ReportLab fallback string and PDF→bilingual DOCX routing string; type always `string[]` or `null`, never a bare string). Updated: `GET /jobs/{job_id}` endpoint note to document `warnings` field semantics. Additive optional field — backward-compatible. Added in change `pdf-renderer-fallback-warn`.

## [data 0.17.0] — 2026-07-07
Updated: `Critique gate usage` row (Quality-Metrics-Gating Extensions) — QE scoring for the critique loop is now issued via ONE round-based batched `score_blocks()` call per iteration round (flat `[(src, draft), (src, revised), ...]` list across every segment revised that round) instead of one two-element call per segment × iteration. Segment `i`'s draft/revised scores are read back at flat indices `2*i` / `2*i + 1`. Adoption rule unchanged (strict-greater-than; tie keeps draft; BR-89). Non-breaking — describes an internal call-shape change only, no IR/persistence schema change. Added in change `batch-critique-qe-scoring`.

## [data 0.13.0] — 2026-06-27
Added: `JobStatus / JobRecord — warnings field` optional column subsection — `string[]`, nullable, null/empty when no degradation; two verbatim warning strings (fitz→ReportLab fallback; PDF→bilingual DOCX routing); type always `string[]` or `null`; additive optional field, backward-compatible; cross-reference to `api-contract.md JobStatus` schema. Added in change `pdf-renderer-fallback-warn`.

## [business 0.12.0] — 2026-06-19
Added: BR-59 (terminology-audit-scope — only `approved` terms in hit-rate denominator; `unverified`, `needs_review`, `rejected` excluded). Added: BR-60 (terminology-audit-match-algorithm — case-insensitive exact substring default; optional configurable lemmatized mode using `blingfire`; no spaCy/NLTK). Added: BR-61 (terminology-audit-safe-degradation — audit exception caught, WARNING logged, `JobRecord.audit=None`, job not failed; mirrors BR-56). Added: Table Q (terminology audit decision table, 9 condition rows).

## [data 0.8.0] — 2026-06-19
Added: `## Terminology Audit Representation` section — `TerminologyAuditResult` in-memory shape (terminology_hit_rate, unapplied_terms, rejected_injections, total_approved, matched_approved), `JobRecord.audit` optional field (parallel to `JobRecord.quality`), nullability/invalid-data rules (whole-token boundary required for `rejected_injections`), known-consumers table. Additive optional field; fully backward-compatible.

## [data 0.7.0] — 2026-06-19
Updated: `BlockQualityScore.block_id` clarified — `element_id` for PDF-IR path; synthetic positional `"{ext}:{file_stem}:{index}"` for non-IR formats (DOCX/PPTX/XLSX) and PDF-PyPDF2-fallback; run-stable only, not durable across re-submissions. Added: non-IR block_id collision row to nullability/invalid-data rules. (DR-1 resolution for p2-comet-qe)

## [business 0.11.0] — 2026-06-19
Added: BR-58 (qe-block-id-best-effort — non-IR formats use synthetic positional block_id; collision/missing must degrade not fail; consumers must not rely on stability across re-submissions). Updated: Table P with new BR-58 condition row.

## [business 0.10.0] — 2026-06-19
Added: BR-54 (qe-score-model-and-range — score range is model-dependent; consumers must check `model` field). Added: BR-55 (qe-invocation-timing — synchronous post-translation step; re-classify if moved async). Added: BR-56 (qe-safe-degradation — QE failure never fails the translation job; caught + WARNING + qe_status unavailable). Added: BR-57 (qe-enable-disable-flag — QE_ENABLED=false skips step entirely; default opt-out). Added: Table P (QE scoring decision table).

## [env 0.6.0] — 2026-06-19
Added: QE_ENABLED (bool, default false — opt-in enable flag for COMET/xCOMET scoring; restart required). Added: QE_MODEL_NAME (string, default Unbabel/wmt22-cometkiwi-da — HuggingFace model name or local path). Added: QE_DEVICE (enum cpu/cuda/mps, default cpu — inference device; invalid value falls back to cpu with WARNING). Updated: .env.example.template and env.schema.json.

## [data 0.6.0] — 2026-06-19
Added: `## Quality Evaluation (QE) Score Representation` section — BlockQualityScore shape, JobQualityRecord in-memory shape, nullability/invalid-data rules. QE scores are stored separately from the IR; no IR wire-schema change. Added: quality_evaluator.py to Known consumers of the IR table (read-only consumer of element_id, content, translated_content). Added: two rows to Invalid Data Behavior table.

## [api 0.5.0] — 2026-06-19
Added: GET /jobs/{job_id}/quality endpoint — per-block COMET/xCOMET quality scores; 200 (status: available/pending/disabled/unavailable), 404 job not found. Added: BlockQualityScore schema (block_id, score, model). Added: JobQualityResponse schema (job_id, status enum, scores array). Updated: api-inventory.md 0.1.0→0.2.0 with new route. Non-breaking additive endpoint.

## [ci 0.4.0] — 2026-06-18
Added: `layout-detector-dependency-gate` — verifies onnxruntime (CPU only) is the only new ML runtime; blocks on ultralytics or onnxruntime-gpu in requirements. Added: `## Layout Detector Dependency Gate` section with pass/fail conditions and model-weight bundling note.

## [env 0.4.0] — 2026-06-18
Added: LAYOUT_DETECTOR_MODEL_PATH (optional string, no default — falls back to HuggingFace auto-download) and LAYOUT_DETECTOR_ENABLED (optional boolean, default true — rollback switch to round(y0,10pt) heuristic). Updated: .env.example.template and env.schema.json.

## [data 0.4.2] — 2026-06-18
Added: `### ElementType producer inventory` — layout_detector.py recorded as IR producer alongside pdf_parser.py. Added: normative heron-101 → ElementType label mapping table (D-4). Updated: `Known consumers` table — pdf_parser.py producer row updated to reflect delegation to layout detector; layout_detector.py added as producer. No wire-schema change.

## [business 0.7.0] — 2026-06-18
Added: BR-32 (local-inference-privacy — page images must never leave the process during layout detection; module must have no network imports). Added: BR-33 (layout-detection-fail-soft — inference failure on any page triggers WARNING + per-page fallback to round(y0,10pt); job continues). Added: Table J (layout detection failure handling decision table).

## [ci 0.3.0] — 2026-06-18
Added: Informational Gate Promotion Policy — quarantine-to-informational-sub-job rule for third-party library non-determinism; parent gate stays required. Added: snapshot initialization `MUST NOT` auto-pass rule — new fixture binaries must be accompanied by committed `.ir.json` snapshot in the same PR.

## [ci 0.2.0] — 2026-06-18
Added: `golden-sample-regression` gate — offline dual-run comparison over `tests/fixtures/golden/` (no network, no GPU); required on PR; blocks merge on any pre-existing-field regression. Added: Required Check Policy section with golden-sample-regression gate specification.

## [data 0.4.1] — 2026-06-18
Added: `### ElementType wire-value convention` — all `ElementType` members MUST use lowercase wire values; frozen by ADR 0002; uppercase case is a breaking change requiring major version bump.

## [data 0.4.0] — 2026-06-18
Added: `## Intermediate Representation (IR) — TranslatableDocument` section (p2-ir-document-model). Added: four region-level `ElementType` values (`TABLE`, `FIGURE`, `FORMULA`, `LIST`) — non-breaking additive enum expansion. Added: `reading_order` optional field (`integer|null`, default `null`) to `TranslatableElement` serialized shape — backward-compatible; old-format documents (lacking the key) deserialize with `reading_order=None`. Added: round-trip guarantee, backward-compatibility rule, `to_dict` compatibility rule, decoupling guarantee, known-consumers table. Added: two IR-specific invalid-data behavior rows.

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
