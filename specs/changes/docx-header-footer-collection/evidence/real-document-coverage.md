# Evidence: real-document header/footer coverage, before vs after

Measured against the two real `.docx` files (untracked `docs/TEST_DOC/`, read by no
test; this is a main-Claude verification run). Script:
`evidence/probe_hf_coverage.py`. Source swapped via scratch snapshot + restore,
never `git checkout`; SHA verified identical after restore.

## Method

Ground truth = every header/footer paragraph text (extracted with the SAME
txbxContent-excluding xpath the native path now uses, so the measurement matches
the collected domain) plus every header/footer table cell, across all six
per-section slots and every section, deduplicated to unique whitespace-normalized
strings. A unique text counts as *collected* when it appears in the
whitespace-normalized concatenation of all collected `Segment`s.

## Result

| document | unique header/footer texts | missing before (main) | missing after |
|---|---:|---:|---:|
| `EN-P-QC1102-D7 量测系统分析(MSA)程序.docx` | 11 | 7 | **0** |
| `W-RM0901-G6 机器设备保养及维护管理准则.docx` | 11 | 9 | **0** |

"Missing before" is less than 11 because a few header texts (e.g. the company
name) also occur in the document body, so the body walk already collected them;
the 7 and 9 are the header/footer-**only** unique texts that were silently dropped
on main. Examples dropped before, collected after: `编制单位`, `第9页共12页`,
`版本/版次`. Both documents' headers are 15-cell tables; the footers are single
page-number paragraphs. Neither has header/footer textboxes (0 `txbxContent` in
any header/footer part), so the Option C txbxContent-strip is exercised as a
guarantee, not because these files need it.

## What this does NOT cover (honest scope)

- Header-anchored textboxes on Linux remain unhandled (a pre-existing textbox-scope
  gap; COM owns them on Windows). Absent in these files.
- The body's pre-existing textbox double-count is untouched (design.md Open Risks).
- On Windows the COM shapes pass still translates header-anchored shapes; the
  native path and COM own disjoint domains, so no double-translation — verified by
  construction (the native extraction excludes txbxContent), unit-tested, not
  observable on the Linux CI.
