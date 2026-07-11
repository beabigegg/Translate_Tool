# ADR 0020: Composition-aware truncation guard with fail-safe and never-replace-with-source recovery

## Status
proposed

## Context
gpt-oss:120b returned 370 chars for a 4,827-char DOCX "layout" cell (a merged
`<w:tc>` holding an entire document section) with `ok=True`. The reply is
well-formed: schema-valid JSON, every `(row, col)` coordinate present, not an
echo of the source. Both wire formats — the JSON envelope
(`table_serializer.parse_json`, L159) and the legacy pipe-grid — therefore accept
it, and over 90% of the content silently vanishes. No existing check (empty,
echo, shape, BR-108 refusal) detects a well-formed-but-truncated reply. The live
case is recorded in a comment at `docx_processor.py` ~L1093.

Calibration over 233 distinct real cache pairs (mostly →Vietnamese, CJK-heavy,
normalized source ≥ 15 chars) gives an expected-length model
`E = 3.51·cjk + 0.75·latin_alpha` and a flag `translated_len < k·E` with 0% false
positives at every tested `k` from 0.2 to 0.5; the recorded bug sits at ratio
0.077. Two hazards dominate the design. First, the user's explicit risk
(`固定門檻會誤殺`): a false positive re-translates a CORRECT translation — worse
than the bug — and the calibration is only one language pair. Second, an obvious
but wrong "fix" — replacing a short translation with its source — is also worse
than the bug (370/4827 truncated text still carries more meaning than untranslated
source).

## Decision
1. **A pure, composition-aware guard.** `is_suspiciously_short()` in a new
   `app/backend/utils/length_guard.py` computes `E = a·cjk + b·latin_alpha` from a
   per-target coefficient table and flags `translated_len < k·E`. `k`, the
   coefficient table (seeded with Vietnamese `a=3.51, b=0.75`), and
   `MIN_SOURCE_CHARS=15` are `config.py` constants (mirroring
   `MAX_TABLE_NESTING_DEPTH`), NOT env vars. `k=0.3`: a 0.2 absolute margin below
   the FP-free ceiling (0.5) and ~4× above the recorded bug ratio.
2. **Placement: the DOCX table-cell acceptance seam only.** The only evidenced
   hazard is a merged layout cell. The body/segment path already sends bounded
   per-paragraph segments; it is scoped out (follow-up), and the guard function is
   target-agnostic so later adoption is additive.
3. **Recovery reuses the BR-82 split-and-retranslate block** (docx L1101-1132):
   split on `"\n"`, re-translate per line via `translate_texts`. Bounded to
   `MAX_RECOVERY_ATTEMPTS = 1`; recovery never re-enters the guard seam, so it
   cannot loop. On exhaustion, keep the LONGEST of {original reply, recovered
   reassembly} and emit a WARNING mark on the `TranslateTool` logger (BR-109) —
   observability only, no automated consumer (`tests/metrics/truncation_rate.py`
   is unrelated: it counts render-time `render_truncated`, not this WARNING).
4. **No IR field.** `render_truncated` (ADR-0004/BR-38) is a RENDER-time bbox
   marker — a different concept — and a new field would be a dead write with no
   reader on the tmap-based cell path. The WARNING log is the durable mark;
   `data-shape-contract.md` is untouched.
5. A new business rule (provisional BR-117) records the model, the fail-safe, and
   the recovery contract; `schema-version` bumps 0.33.1 → 0.34.0.

## Consequences
- **Reversal-guarded invariant 1 — fail-safe on uncalibrated targets.** The guard
  MUST NOT flag when the target is absent from the coefficient table, the
  normalized source is `< MIN_SOURCE_CHARS`, or `E == 0`. Because the seeded table
  lists only calibrated targets, every other target is fail-safe by construction.
  A future change that adds a broad "conservative default" coefficient for
  unlisted targets, or lowers `MIN_SOURCE_CHARS`, would re-arm the exact
  false-positive-re-translates-correct-output hazard on unproven language pairs and
  must not be made silently — it requires its own calibration evidence.
- **Reversal-guarded invariant 2 — never replace with source, never loop.**
  Recovery keeps the longest available translation and marks it; it NEVER
  substitutes source text and NEVER applies the BR-25 placeholder for a
  truncation flag, and it is bounded to one non-re-entrant attempt. A future
  change that "simplifies" exhaustion handling to write source, or that re-runs
  the guard on recovered pieces, reintroduces a worse-than-the-bug outcome or an
  unbounded loop and must be rejected.
- Additive: new pure module + three constants + one call site; rollback is a code
  revert. No schema, data, env, or IR change.
- Scope residuals (accepted, follow-up on evidence): PPTX/XLSX table cells sharing
  `parse_json` are unguarded because the reusable recovery block lives only in the
  DOCX path; the body/segment path is unguarded. Neither is worsened here.
- Distinct from BR-108 (meta-refusal, body path, a different reject reason) and
  layered on top of BR-82 (adds a new well-formed-but-short trigger for the same
  recovery machinery, does not replace the shape-mismatch trigger).
