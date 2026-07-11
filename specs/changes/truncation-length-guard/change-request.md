# Change Request

## Original Request

Detect and recover complete-but-shortened LLM translations (silent truncation). A well-formed but truncated reply passes every wire-format check: gpt-oss:120b returned 370 chars for a 4,827-char DOCX cell with ok=True (>90% of content lost), and BOTH the JSON envelope (`table_serializer.parse_json`) and the legacy pipe-grid accept it — schema-valid, all coordinates present, non-echo. `docx_processor.py` ~L1093 records this exact live case in a comment. Neither wire format detects a truncated-but-well-formed reply, so the biggest cells silently lose most of their translation.

Affected surface: the translation-acceptance seams — the table cell path (`table_serializer.parse_json` / `json_translation`) and the body/segment path (`translate_texts`/`translate_once` return).
Desired behavior: a shared, script-composition-aware length guard flags a translation as suspiciously short when `translated_len < k * E` where `E = a*cjk_source_chars + b*latin_source_chars`. The guard MUST fail safe. On detection the recovery MUST NOT replace the translation with the source (worse than the bug); instead re-translate by splitting on newlines and translating pieces at the existing per-paragraph granularity (the BR-82 fallback pattern at docx_processor.py ~L1101), with bounded retries. Threshold `k` and coefficients live as `config.py` constants (mirror `MAX_TABLE_NESTING_DEPTH`), NOT env vars.
Success criterion: the recorded 4,827→370 truncation is detected and recovered (re-translated cell length a plausible multiple of the source, not <10%); a synthetic set of legitimate short translations across CJK-heavy and latin-heavy sources is NOT flagged (0 false positives on calibration-derived fixtures); numeric/passthrough cells (BR-68) are exempt; existing non-truncated output is unchanged.

Calibration (main Claude, from 233 distinct real cache pairs; full data in evidence/calibration-facts.md):
- Expected translated length E = 3.51*cjk_source_chars + 0.75*latin_source_alnum_chars (whitespace-normalized; CJK→Vietnamese).
- Guard `translated_len < k*E` false-positive rate on the 233 real pairs: k=0.2→0%, 0.3→0%, 0.4→0%, 0.5→0%. The 4827→370 case has ratio 0.077 (far below 0.3*E). Huge gap between legitimate-short and truncated.
- 233 pairs is ONE dominant language pair (mostly →Vietnamese, CJK-heavy). Other targets need a conservative default OR per-target coefficients; the guard MUST fail safe when coefficients are unknown.

Verified seams (main Claude):
- `table_serializer.parse_json` (L159) accepts table cell JSON; `json_translation.build_table_payload` (L72) builds it.
- The recovery pattern already exists: `docx_processor.py` ~L1093-1110 splits a big cell on "
" and re-translates per-paragraph via `translate_texts` (BR-82 fallback). The guard's recovery reuses this.
- BR-68 numeric cells are never sent (passthrough) — exempt by construction.
- Open design questions (for spec-architect/ADR): guard placement (cell path only vs body too); per-target coefficients vs conservative default; k as config constant; recovery action (split-and-retry vs retry-same) and its retry bound; mixed-composition source handling; interaction with BR-82 fallback and BR-108 meta-refusal guard.
## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
