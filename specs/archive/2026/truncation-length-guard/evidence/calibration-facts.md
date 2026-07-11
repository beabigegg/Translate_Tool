# Truncation-guard change — calibration facts (for /cdd-new, the last user-picked change)

## The defect
A "complete-but-shortened" cell/segment translation passes every wire-format check:
gpt-oss:120b returned 370 chars for a 4,827-char cell with ok=True (>90% lost). Both the
JSON envelope (parse_json) and the legacy pipe-grid accept it — schema-valid, all
coordinates present, non-echo. Neither format detects a truncated-but-well-formed reply.
docx_processor.py L950-985 records this live case in a comment.

## Calibration (233 distinct cache pairs, norm src >= 15 chars, mostly -> Vietnamese)
Expected translated length model (whitespace-normalized):
    E = 3.51 * (CJK source chars) + 0.75 * (latin source alnum chars)
- CJK-dominant pairs (n=100): median 3.51 target chars per CJK char.
- Latin-dominant pairs (n=2): median 0.75 (thin sample; needs a conservative default).

Guard = flag when translated_len < k * E. False-positive rate on the 233 real pairs:
    k=0.2 -> 0.0%   k=0.3 -> 0.0%   k=0.4 -> 0.0%   k=0.5 -> 0.0%
The 4,827->370 truncation has ratio 0.077 (way below 0.3*E). Huge gap between legitimate
short translations and truncation — a composition-aware guard at k=0.3 catches the bug
with ~0% false positive on this data.

## Design constraints (the user's stated risk: "固定門檻會誤殺")
- Do NOT use a single length RATIO — expansion varies 0.8x-4.9x with source CJK density.
  Use the composition model E = a*cjk + b*latin.
- Coefficients are calibrated for ->Vietnamese CJK-heavy docs. Other targets need a
  conservative default (low a, so E is small, so the guard rarely fires) OR per-target
  coefficients. The guard must FAIL SAFE: when unsure, do NOT flag.
- On detection, DO NOT replace with source (the "worse than the bug" outcome the user
  named). Recover the content: retry the LLM call, or reuse the existing per-cell/per-line
  split path (BR-82 fallback splits a big cell on "\n" — docx L962) to re-translate pieces.
  Keeping the truncated reply is also bad (370/4827); retry/split is the right action.
- 233 pairs is ONE dominant language pair — the design must state this and be conservative.

## Open design questions (for spec-architect / ADR)
1. Where does the guard sit — table-cell path only, or body path too? (The live case is a cell.)
2. Per-target coefficients vs one conservative default; is k a config constant (like
   MAX_TABLE_NESTING_DEPTH, not an env var)?
3. Recovery action: retry-same, split-and-retry, or split-only. Bounded retries (never loop).
4. What counts as "source composition" for a mixed cell (CJK + latin + numeric)?
5. Interaction with BR-68 numeric passthrough (numeric cells never sent) and BR-82 fallback.

This is design-heavy: needs spec-architect + a new ADR. Backed by evidence/truncation-calibration.
