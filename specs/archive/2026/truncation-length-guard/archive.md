# Archive — truncation-length-guard

## Change Summary

A well-formed but truncated LLM reply (gpt-oss:120b returned 370 chars for a 4,827-char
DOCX table cell with ok=True) passed every wire-format check and silently lost >90% of
the cell. A new composition-aware length guard at the DOCX table-cell acceptance write
site flags `translated_len < 0.3·E` where `E = 3.51·cjk + 0.75·latin_alpha` (per-target
coefficient table, seeded Vietnamese from 233 real cache pairs), and on a flag reuses the
BR-82 split-and-retranslate recovery, keeping the longest of {original, recovered} —
never substituting source. It fails safe (never flags) on an uncalibrated target, a
source <15 chars, or E==0.

## Final Behavior

Truncated cells are detected and recovered to a fuller translation; legitimate short
translations are not flagged (0 false positives across all 342 real cache pairs). k, the
coefficients, and MIN_SOURCE_CHARS are config.py constants (not env vars). The recovery
never substitutes source and never applies a BR-25 placeholder; a WARNING is emitted for
observability only.

## Final Contracts Updated

- `contracts/business/business-rules.md` 0.33.1 → 0.34.0: BR-117 (`docx-cell-truncation-length-guard`).
- `contracts/CHANGELOG.md`: paired entry.
- `docs/adr/0020-truncation-length-guard.md` (two reversal-guarded invariants: fail-safe-on-uncalibrated-target, never-replace-with-source).

## Final Tests Added / Updated

`tests/test_length_guard.py` (57 tests incl. adversarial FP-boundary fuzz), plus
integration additions in `test_docx_nested_tables.py` and `test_json_translation_body.py`.
Full suite 1466 passed, 1 xfail, 0 failed.

## Final CI/CD Gates

No new gate, no CI/CD contract change, no workflow edit.

## Production Reality Findings

- **The load-bearing property held on real data.** The user-named hazard (a false
  positive re-translates a correct translation — worse than the bug) was measured against
  all 342 real cache triples: 0 false positives. The composition model — not a single
  length ratio — is what makes this possible; expansion varies 0.8×–4.9× with CJK density.
- **A phantom consumer in the design was caught and corrected (3rd such catch this loop).**
  D5 named `tests/metrics/truncation_rate.py` as consuming the new WARNING, but
  `compute_truncation_rate` counts render-time `render_truncated` and parses no log. The
  WARNING is observability-only with no automated consumer; design.md D5, ADR-0020, and
  the manifest's Required Tests were corrected. D5's core "no IR field" call stood.
- **The seam line-citation was wrong and corrected.** implementation-planner found the
  guard belongs at the acceptance WRITE site (docx L1054-1058, the JSON/grid happy path
  where the accepted short reply is written), NOT the BR-82 fallback (~L1088-1132) that
  design.md and the draft BR-117 both cited — that else-branch is the RECOVERY the guard
  calls, reached only when parse_json returns None. BR-117 and design.md were corrected.
- **The coefficient-table key had to match the live target string.** The pipeline passes
  full names (`"Vietnamese"`, not `"vi"`); the table is keyed by the normalized full name.
- **One accepted residual (contained, xfail-tracked).** A long pure-CJK source → bare
  Latin acronym (ratio ~0.11) is flagged — length alone cannot distinguish it from a
  truncation. Accepted because it is absent from all 342 real pairs and contained by
  never-source + keep-longest (zero content loss). QA approved-with-risk; spec-architect
  co-signed (high-risk Tier 1).

## Lessons Promoted to Standards

- **Contract/ADR (applied during the change):** BR-117 and ADR-0020 encode the durable
  design principles — the composition length model, the three fail-safe conditions, and
  the two reversal-guarded invariants (fail-safe-on-uncalibrated-target;
  never-replace-with-source). The generalizable heuristic "when a detector signal is
  inherently ambiguous (length alone cannot separate a legit acronym from a truncation),
  contain the false positive via a recovery that cannot lose content — never a tighter
  threshold" lives in ADR-0020, where product/design behavior belongs.
- **CLAUDE.md: none (net growth 0).** The two candidate agent-workflow lessons are already
  covered: the D5 phantom-consumer catch is an instance of the existing seam-verification
  learning (confirm an assigned attribute actually has a READER downstream — a phantom
  consumer is the mirror image, the same verify-the-claimed-reader discipline); the design
  principle above is product behavior, correctly in ADR-0020 not CLAUDE.md.

## Follow-up Work

- **`truncation-guard-acronym-exemption`** — an acronym/code-shape exemption in the
  fail-safe set, owner application-team, MUST be scaffolded before the coefficient model
  is extended to any NEW target or to non-prose (label/code) cells. Tracked by an
  xfail(strict) in test_length_guard.py + design.md Open Risks.
- The guard is DOCX-cell-scope only; the body/segment path and PPTX/XLSX table cells
  sharing `parse_json` are follow-ups pending evidence.
- `<w:sdt>` content controls inside DOCX table cells still dropped (absent in the real
  files); the BR-109 sampler walks only top-level `doc.tables`.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
