# Monkey Test Report: truncation-length-guard

- Change: `truncation-length-guard`
- Agent: monkey-test-engineer (IP-7)
- Target under test: `app/backend/utils/length_guard.py::is_suspiciously_short`
  (pure function; k=0.3; `TRUNCATION_GUARD_COEFFICIENTS = {"vietnamese": (3.51, 0.75)}`)
- Test file: extended `tests/test_length_guard.py` (see "File choice" below)
- Command: `conda run -n translate-tool pytest tests/test_length_guard.py -q`
- Result: **56 passed, 1 xfailed** (strict). Full suite: **1466 passed, 4 skipped,
  1 xfailed, 0 failed** (`conda run -n translate-tool pytest tests/ -q`, 141.69s).

## File choice

Extended `tests/test_length_guard.py` rather than creating a new
`tests/test_length_guard_monkey.py`. Reason: `tests/test_length_guard.py` is
already in this change's `context-manifest.md` Allowed Paths and Required
Tests; a brand-new file is not listed there, and creating one would require a
Context Expansion Request for no real benefit (the new classes are clearly
namespaced and commented as monkey-test-engineer's addition, matching
test-plan.md's "owned by monkey-test-engineer, referenced only" framing for
the monkey/Tier-3 family).

## Headline conclusion — the FP boundary is MOSTLY held, with one BLOCKING gap

- For **realistic legitimate-short translations landing at roughly 30%+ of
  E** (headings, unit-symbol cells, acronym-plus-certification-number
  references, code-copy-through cells) — the FP boundary holds. Zero flags
  across 4 new realistic scenarios plus the existing AC-3 fixtures.
- For **extreme compression** — a long descriptive CJK phrase collapsed to a
  **bare acronym only** (e.g. "國際標準化組織認證品質管理系統流程規範文件" →
  "ISO 9001", ratio 0.109) — the guard **does flag** a translation that reads
  as complete and correct. This is the literal "acronym expansion that
  shrinks" scenario the task brief names as a case that should NOT be
  flagged. **I tested it (ran it) and it flags.** See "Blocking finding"
  below.
- All fail-safe boundaries (unlisted target, source-length floor, E==0,
  degenerate/empty/whitespace-only inputs, Unicode edge cases) held exactly
  as documented, with no miscounting or crashes found.

## Scenario → expected → result

| # | scenario | category | expected | result |
|---|---|---|---|---|
| 1 | ISO-cert acronym+number reference (ratio 0.33 of E) | realistic legit-short | not flagged | **PASS** (not flagged) |
| 2 | Section heading (ratio 0.43 of E) | realistic legit-short | not flagged | **PASS** (not flagged) |
| 3 | Unit-symbol descriptive cell (ratio 0.36 of E) | realistic legit-short | not flagged | **PASS** (not flagged) |
| 4 | Model/part-code copy-through cell (ratio 0.46 of E) | realistic legit-short | not flagged | **PASS** (not flagged) |
| 5 | Bare-acronym extreme shrink, "國際標準化組織...文件" → "ISO 9001" (ratio 0.109) | adversarial extreme compression | not flagged (per task brief) | **FLAGGED — genuine FP; xfail(strict=True), tracked as BLOCKING finding** |
| 6 | Strict `<` boundary: translation len == floor(k·E) vs floor(k·E)+1 | exact boundary | flag / no-flag split exactly at threshold | **PASS** (correct on both sides) |
| 7 | Source len = MIN_SOURCE_CHARS−1 vs exactly MIN_SOURCE_CHARS | fail-safe boundary | no-flag / genuine-flag split | **PASS** |
| 8 | All-digits / all-punctuation / digit-separator / full-width-space-only sources (E==0) | fail-safe (BR-68 backstop) | never flagged | **PASS** (4/4) |
| 9 | Uncalibrated target: French, English, `""`, `None`, `"vi-VN"`, `"Klingon"` vs. the recorded 4827→5-char reply | fail-safe (unlisted target) | never flagged | **PASS** (6/6) |
| 10 | Target key normalization: `"Vietnamese"`, `"vietnamese"`, `"VIETNAMESE"`, `" Vietnamese "`, `"VietNamese"` vs. the recorded 4827→370 bug ratio | opposite-direction risk (guard must NOT go silently inert) | genuine flag in all 5 forms | **PASS** (5/5) |
| 11 | Empty translation of 4827-char source | degenerate (true positive) | **flagged** (this is the bug shape, not a FP) | **PASS** |
| 12 | Empty source / whitespace-only source | degenerate | not flagged | **PASS** |
| 13 | Whitespace-only translation of a real 20-char CJK source | degenerate (true positive) | flagged | **PASS** |
| 14 | Single-char source (<15) / single-char translation of a real 20-char source | degenerate | no-flag / flag split | **PASS** |
| 15 | `None` translation / `None` source / `None` target | wrong-type defensive | no crash, safe fail-safe or true-positive result | **PASS** (3/3) |
| 16 | Mixed CJK+Latin+digit+punctuation+emoji, proportional translation | Unicode composition | not flagged | **PASS** |
| 17 | Full-width digits (`０-９`) as source | Unicode composition | E==0, not miscounted as latin-alpha | **PASS** |
| 18 | CJK sentence punctuation (`。！？、；：「」`) | Unicode composition | punctuation excluded, doesn't inflate E | **PASS** |
| 19 | Combining/precomposed accented chars (`é`×10) | Unicode composition | counted as latin-alpha, no crash | **PASS** |
| 20 | RTL Arabic + ZWJ + surrogate-pair (ZWJ-sequence) emoji | Unicode composition | no crash, correctly bucketed, proportional translation not flagged | **PASS** |
| 21 | UTF-8 BOM (U+FEFF) prefix | Unicode composition | not counted, no crash, genuine short reply still flags | **PASS** |
| 22 | SQL-injection-like (`'; DROP TABLE users; --`) / script-tag-like (`<script>...`) short translations | adversarial corpus | flagged (true positive — these are not real translations), no crash | **PASS** (2/2) |
| 23 | SQL-like string as the SOURCE | adversarial corpus | no crash, returns bool | **PASS** |
| 24 | Seeded fuzz (seed 20260711, n=200): uncalibrated target across random CJK/Latin/digit/punct/whitespace/exotic-codepoint content | property-based | never flagged | **PASS** |
| 25 | Seeded fuzz (seed 20260712, n=300): never raises, always returns bool, across random content + rotating targets (incl. `None`, emoji, BOM) | property-based | no exception, `isinstance(_, bool)` | **PASS** |
| 26 | Seeded fuzz (seed 20260713, n=200): translation ≥ `k·max(coeff)·len(source)+100` never flags (mathematically guaranteed upper bound) | property-based | never flagged | **PASS** |

## Blocking finding (#5): bare-acronym extreme compression is flagged

**Reproduction** (`tests/test_length_guard.py::TestFPBoundaryExtremeCompression::test_extreme_acronym_shrink_currently_flagged_tracked_gap`, marked `xfail(strict=True)`):

```
source      = "國際標準化組織認證品質管理系統流程規範文件"  (21 normalized CJK chars)
translation = "ISO 9001"                                    (8 chars)
target      = "Vietnamese"
E           = 3.51 * 21 = 73.71
k*E         = 0.3 * 73.71 = 22.113
len(translation) = 8  →  8 < 22.113  →  is_suspiciously_short(...) = True
```

- This is the literal "acronym expansion that shrinks" scenario named in the
  task brief as one to construct and assert `NOT flagged`. It flags.
- **Mechanism, not a one-off bug**: for any pure/near-pure CJK source, the
  guard requires `translated_len >= k * 3.51 * cjk_count ≈ 1.05 * cjk_count`
  merely to escape a flag — i.e. the Vietnamese rendering must be at least
  ~roughly as long (in characters) as the CJK source, character-for-character,
  even though real acronym/code/short-label renderings are routinely much
  shorter than that. Scenario #6 (near-30-46%-of-E cases) shows the guard
  DOES tolerate realistic compression down to ~30% — but a *bare acronym only*
  compression (~11%) falls outside that margin.
- **Why this is not classified "unfixable" / not escalated to a hard gate
  block**: this exact extreme-compression shape was **not present in the
  233-pair real calibration corpus** — `evidence/calibration-facts.md`
  reports 0% FP at every tested `k` up to 0.5, meaning the *shortest* real
  observed pair still had `translated_len >= 0.5*E`. My constructed case
  (ratio 0.109) lies below every real pair on record, so this is a
  **residual, previously-undocumented risk on out-of-distribution content**
  (bare-acronym/code-only cells), not a proven production defect.
- **Containment (why it doesn't reach "worse than the bug")**: on a flag, the
  cell is routed into the existing bounded (`MAX_RECOVERY_ATTEMPTS = 1`,
  non-re-entrant) BR-82 recovery, and **keep-longest never substitutes
  source and never applies the BR-25 placeholder** (verified in this file's
  existing `TestRecoveryIntegration` class and by the wiring in
  `docx_processor.py`). The worst realistic outcome for this gap is: one
  extra LLM call, and — if the recovery re-translation happens to come back
  *longer* than the original correct acronym — a correct terse translation
  being silently replaced by a different (not necessarily wrong, but
  needlessly re-generated and non-deterministic) longer alternative. That is
  a real quality/cost regression, but it is bounded and does not corrupt data
  the way source-substitution or the BR-25 placeholder would.
- **Recommendation** (not implemented by this agent — out of monkey-test-engineer's role): consider an
  additive follow-up such as an absolute minimum-length floor for
  very-short accepted replies below MIN_SOURCE_CHARS-adjacent thresholds, or
  a documented Open Risk addendum in `design.md` acknowledging that the
  233-pair calibration corpus does not cover bare-acronym/code-only cell
  content. This is flagged here for design/backend follow-up.

## Falsifiability / seeds

- `TestExactBoundaryComparison`: deterministic (pure-CJK×20 fixture), no
  seed needed — reversing `<` to `<=` at this fixture's threshold would flip
  the `just_below` case.
- `TestSeededPropertyFuzz`: seeds `20260711` (invariant 1: uncalibrated
  target never flags), `20260712` (invariant 2: never raises / always
  bool), `20260713` (invariant 3: length ≥ `k·max(coeff)·len(source)+100`
  never flags — a mathematically derived, not merely empirical, safe bound).
  All three recorded above for replay.

## Non-applicable preventive-monkey categories for this surface

`is_suspiciously_short` is a pure, stateless, no-I/O function (no HTTP route,
no UI, no session, no DB). The generic preventive-monkey checklist items
double submit, rapid clicks, stale session, unsupported browser navigation,
hidden-tab auto-refresh — N/A (no UI/session surface on this pure function;
already out of scope per `design.md`'s D5/D1 scoping to the DOCX cell-write
seam, which is exercised via the existing `TestRecoveryIntegration` /
`TestNormalReplyUnaffected` integration tests, not by this pure-function
monkey suite).

## Overall status

`not blocked` for gate purposes (all committed assertions pass; the one
genuine FP-boundary gap is tracked via `xfail(strict=True)`, not hidden, not
waived, and not silently excluded — it will surface as an XPASS failure if a
future change unintentionally "fixes" it without updating this test, and it
is documented here as a **BLOCKING-severity finding requiring design/backend
follow-up** before this coefficient model is extended to any new target or
to non-prose (label/code/unit) cell content generally). qa-reviewer /
contract-reviewer should decide whether this finding needs its own tracked
follow-up change or an Open Risks addendum to `design.md` before wider
rollout.
