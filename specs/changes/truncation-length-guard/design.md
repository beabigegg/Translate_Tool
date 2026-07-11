# Design: truncation-length-guard

## Summary
gpt-oss:120b silently returned 370 chars for a 4,827-char DOCX layout cell with
`ok=True`; the reply is schema-valid, coordinate-complete, non-echo, so BOTH the
JSON envelope (`table_serializer.parse_json`) and the legacy pipe-grid accept it
and >90% of the content vanishes. This change adds a shared, script-composition-
aware length guard that flags a translation as suspiciously short when
`translated_len < k·E`, where `E = a·cjk + b·latin_alpha` from a per-target
coefficient table. On a flag, the existing BR-82 split-and-retranslate block is
reused to recover the cell; recovery is bounded to one attempt, can never loop,
keeps the longest attempt, and NEVER substitutes source. The two load-bearing,
reversal-guarded invariants (ADR-0020) are: fail-safe on any uncalibrated target,
and never-replace-with-source on recovery.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| New guard helper | `app/backend/utils/length_guard.py` (new) | Pure composition length model + `is_suspiciously_short()`; no I/O, no LLM dep |
| Config constants | `app/backend/config.py` | `TRUNCATION_GUARD_K`, per-target coefficient table, `MIN_SOURCE_CHARS` (mirror `MAX_TABLE_NESTING_DEPTH`, NOT env) |
| Cell-acceptance seam | `app/backend/processors/docx_processor.py` ~L1054-1058 (acceptance write; calls BR-82 recovery at ~L1059-1132) | Call guard per accepted cell; route flagged cells into existing BR-82 recovery; keep-longest + WARNING mark |
| Composition helpers | `app/backend/utils/text_utils.py` | Reuse `has_cjk`/per-char CJK test + numeric exclusion (BR-68); may add a small `count_composition()` helper |
| Observability | `app/backend/utils/logging_utils.py` `TranslateTool` logger | The truncation-recovered WARNING is observability-only; it has NO automated consumer. `tests/metrics/truncation_rate.py` is UNRELATED (it counts render-time `render_truncated`) and is NOT this change's regression metric. |

## Key Decisions

- **D1 — Guard placement: DOCX table-cell acceptance seam only.** The only
  evidenced hazard is a merged "layout" cell holding a whole document section
  (docx ~L1093). The body/segment path already sends bounded per-paragraph
  segments through `translate_texts`; no body truncation is evidenced. Called at
  the cell-assembly seam covering both the whole-table JSON path and the BR-82
  per-cell fallback reassembly. → Rejected *guard body path too*: speculatively
  widens a Tier-1 every-job acceptance path with no evidence; scoped out as a
  follow-up. The helper is target-agnostic so body/PPTX/XLSX adoption is a later
  additive step against the same pure function.

- **D2 — Length model + fail-safe.** Per-target coefficient table keyed by
  normalized target, seeded with Vietnamese `a=3.51, b=0.75`; `k=0.3`. →
  Rejected *single conservative default for all targets*: a shared low `a` would
  either mis-fire on CJK-heavy pairs or never fire; explicit per-target entries
  keep the model honest and force the fail-safe for anything unlisted. **Exact
  fail-safe (guard MUST NOT flag when ANY holds):** (1) target absent from the
  coefficient table; (2) normalized source length `< MIN_SOURCE_CHARS = 15`
  (the calibration floor); (3) `E == 0` (no cjk and no latin-alpha, e.g.
  all-numeric — also BR-68). **`k=0.3` justification:** 0% false positives on all
  233 real pairs at every tested `k` up to 0.5, so 0.3 sits a full 0.2 absolute
  margin below the FP-free ceiling while keeping a ~4× margin above the recorded
  bug ratio (0.077); lower than 0.4/0.5 to stay conservative against a
  single-language-pair calibration, matching AC-1.

- **D3 — Recovery: reuse BR-82 split-and-retranslate, bound = 1.** On a flag the
  cell is split on `"\n"` and re-translated per line via `translate_texts`
  (docx L1101-1132, verified reusable) — each call is bounded so pieces do not
  re-truncate. `MAX_RECOVERY_ATTEMPTS = 1`; the recovery does not re-enter the
  guard seam, so it cannot loop by construction. **Terminal outcome on
  exhaustion: keep the LONGEST of {original short reply, recovered reassembly}
  and emit a WARNING mark — NEVER substitute source, NEVER apply BR-25
  placeholder.** → Rejected *retry-same-payload*: reproduces the truncation, the
  payload size is the cause; → Rejected *mark-and-keep-original*: discards a
  possibly-better recovered reassembly. Max content recovered is the goal.

- **D4 — Mixed composition (numeric excluded, BR-68).** Whitespace-normalize,
  then per char: CJK char → `cjk`; else `str.isalpha()` non-CJK → `latin`; digits,
  punctuation, whitespace ignored. `E = 3.51·cjk + 0.75·latin`. → Rejected
  *single length ratio*: expansion varies 0.8×–4.9× with CJK density (the user's
  `固定門檻會誤殺` hazard).

- **D5 — IR marker: neither reuse `render_truncated` nor add a new field.**
  `render_truncated` (L240, ADR-0004/BR-38) is a RENDER-time bbox marker — a
  different concept — so reuse would overload it. A NEW IR field would be a
  dead write: the DOCX cell path works over `final_tmap` strings, not
  `TranslatableElement`, and no downstream reader exists (CLAUDE.md
  silently-discarded-write lesson). The durable "mark" is a WARNING on the
  `TranslateTool` logger (BR-109) with a stable prefix — **observability only, no
  automated consumer.** (Corrected against live source: `tests/metrics/truncation_rate.py`
  → `compute_truncation_rate` counts `el.render_truncated` and sums
  `metadata["overflow_area"]`; it parses no log and measures the render-time bbox
  concept — it does NOT consume this WARNING and is NOT this change's regression
  metric. AC-7 regression evidence comes from the guard's own unit/integration
  tests plus a real-doc before/after on the recorded 4827→370 case.) → Rejected
  *add `suspected_truncation` field now*: no consumer, so it would be dead until a
  UI reader lands; recovery already fixes content. Result: `data-shape-contract.md`
  is NOT touched.

- **D6 — Interaction ordering at the cell seam.** (1) BR-68 numeric cells are
  never serialized/sent → guard never sees them (E==0 fail-safe backstops any
  slip). (2) Existing `parse_json` shape/echo validation runs first; only a
  shape-VALID reply reaches the new per-cell guard. (3) Flagged cells route into
  the existing BR-82 split-and-retranslate recovery — the guard adds a NEW
  failure mode (well-formed-but-short) on top of BR-82's existing
  shape-mismatch trigger; it does not replace BR-82. (4) BR-108 meta-refusal is a
  DIFFERENT reject reason on the body path only (≤200-char self-referential
  reply → discard→source per BR-25); it does not co-occur at this cell seam. If
  the body path later adopts the guard, BR-108 refusal check runs FIRST, the
  truncation guard only on non-refusal replies.

## New Business Rule (shape only — contract-reviewer writes exact text)
Provisional **BR-117** (LIVE highest is BR-116; bump `schema-version` 0.33.1 →
0.34.0). Defines: the composition length model `E = a·cjk + b·latin_alpha` with a
per-target coefficient table; the `translated_len < k·E` flag that FAILS SAFE
(no flag) on an uncalibrated target or a source below the minimum length; and the
recovery contract — reuse BR-82 split-and-retranslate, bounded to one attempt,
that on exhaustion keeps the longest attempt and marks it and NEVER substitutes
source (distinct from BR-25). Scope: DOCX table-cell acceptance seam; BR-68
numeric exempt.

## Migration / Rollback
Purely additive. New pure module + three `config.py` constants (coefficient
table, `k`, `MIN_SOURCE_CHARS`); no schema, no data migration, no env var. The
default coefficient table lists only calibrated targets, so every uncalibrated
target is fail-safe (no flag) out of the box. Rollback is a code revert of the
new helper and its single call site plus the constants; behavior returns to
accept-as-is. No IR/data-shape change to reverse.

## Open Risks

- **Bare-acronym extreme compression is a known false positive (accepted residual).**
  A long pure-CJK source translated to a bare Latin acronym only (e.g. a 22-char
  Chinese phrase → `ISO 9001`, ratio 0.109) IS flagged — length alone cannot
  distinguish it from a truncation. ACCEPTED, not blocking, because: (1) it is absent
  from all 342 real cache pairs (main Claude verified 0 real occurrences); (2) a
  realistic acronym-plus-number (`ISO 9001 認證`, ratio 0.33) is NOT flagged; (3) the
  never-source + keep-longest recovery CONTAINS it — a flagged acronym cell can only
  gain a fuller re-translation or cost one wasted LLM call, it can NEVER lose content
  or substitute source. Tracked by an `xfail(strict=True)` in test_length_guard.py
  (flips to XPASS and forces review when the model is later tightened). Follow-up if
  it ever manifests on real data: an acronym/code-shape exemption (short all-Latin/
  digit/uppercase translation) in the fail-safe set. See monkey-test-report.md finding #5. **Follow-up owner: application-team (BR-117 owner); opened 2026-07-11 as a tracked residual — a dedicated change (`truncation-guard-acronym-exemption`) must be scaffolded before the coefficient model is extended to any NEW target or to non-prose (label/code) cells.**
- Calibration rests on ONE dominant language pair (→Vietnamese, CJK-heavy).
  Coefficients for other targets are unproven; the fail-safe (no entry → no flag)
  is what keeps that unproven surface harmless, so it is load-bearing.
- Guard/recovery is DOCX-only because the reusable BR-82 block lives there;
  PPTX/XLSX table cells hitting the same shared `parse_json` are NOT guarded.
  Follow-up if truncation is observed on those formats.
- Body/segment path is intentionally out of scope; a single >4k-char body
  paragraph could in principle truncate un-guarded. Follow-up on evidence.
