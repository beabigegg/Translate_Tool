# Regression Report — truncation-length-guard

Required because the guard runs at the DOCX table-cell acceptance seam on every DOCX
job, and the user-named hazard is that a false positive re-translates a correct
translation. Two things needed durable evidence: zero false positives on real data
(the load-bearing safety property) and that non-truncated output is unchanged (AC-7).

## 1. Zero false positives on real data — the load-bearing property

Main Claude ran `is_suspiciously_short(source, translation, target)` against **all 342
distinct real source/target/translation triples** in the user's translation cache
(the actual accepted output of real runs). **Zero were flagged.** Not one legitimate
translation is misclassified as truncated. This is the exact "worse than the bug"
hazard the user named (`固定門檻會誤殺`), and the composition model holds it decisively
on real data. An acronym-shape sub-check (CJK source ≥15 chars, translation < 0.3·E)
also found **0** real occurrences.

## 2. Truncation detected (AC-1)

The recorded 4,827→370-style case (long CJK source, translation at ratio 0.077) is
flagged True by the pure function and, at the cell seam, routes into recovery — proven
on both the JSON-envelope and legacy pipe-grid paths
(`test_docx_nested_tables.py::TestTruncationGuardCellSeam`, parametrized over both).

## 3. Never-source recovery — verified by sabotage

The critical invariant: recovery keeps the LONGEST of {original reply, recovered
reassembly} and NEVER substitutes source, NEVER a BR-25 placeholder. Main Claude
sabotaged the write (`_recovered_cells[s.text] = s.text`, source-substitute) and 3
tests went RED including `test_recovery_keeps_longest_on_exhaustion_never_source`;
source restored byte-identical (sha verified). So a flagged cell can only gain a
fuller re-translation or cost one wasted LLM call — it can never lose content.

## 4. Non-truncated output unchanged (AC-7)

The guard's three fail-safes mean most cells never reach the flag: source < 15 chars
(most cell text), uncalibrated target, or E==0. Existing table/cell suites stay green:
`test_table_context_translation.py`, `test_docx_nested_tables.py`,
`test_table_serialization.py`, `test_json_translation_body.py`. Full suite: **1466
passed, 4 skips, 1 xfailed, 0 failed** (`test-evidence.yml`, phase `full`); evidence
timestamp postdates every source/test/contract file it covers. `truncation_rate.py` is
NOT this change's metric (it counts render-time `render_truncated`, unrelated) — AC-7
evidence is the guard's own tests + the real-data 0-FP measurement, per corrected D5.

## 5. Accepted residual — bare-acronym extreme compression (monkey finding #5)

monkey-test-engineer found one genuine false positive it did not paper over: a long
pure-CJK source translated to a **bare Latin acronym only** (e.g. a 22-char Chinese
phrase → `ISO 9001`, ratio 0.109) IS flagged — length alone cannot distinguish it from
a truncation. **Accepted as a documented residual, not a blocker**, because:
(a) absent from all 342 real cache pairs (0 real occurrences);
(b) a realistic acronym-plus-number (`ISO 9001 認證`, ratio 0.33) is NOT flagged;
(c) contained by the never-source + keep-longest recovery — it can only gain a fuller
re-translation or waste one LLM call, never lose content or substitute source.
Tracked by an `xfail(strict=True)` (flips to XPASS and forces review when the model is
tightened). Follow-up if it ever manifests on real data: an acronym/code-shape
exemption in the fail-safe set. See `design.md` Open Risks and monkey-test-report.md.

## 6. Scope boundary (AC / D1)

DOCX table-cell acceptance seam only. The body/segment path and PPTX/XLSX table cells
sharing `parse_json` are explicitly out of scope (follow-ups); `test_json_translation_body.py::TestLengthGuardOutOfScope`
confirms the body path is unaffected.

## Verdict

No regression. Zero false positives on 342 real pairs, truncation detected,
never-source recovery sabotage-verified, non-truncated output unchanged. The one
adversarial-only FP is contained (no content loss), absent from real data, and
xfail-tracked.
