# Evidence: real-document coverage, before vs after

Measured against the two real `.docx` files the user reported. Those files stay
**untracked** (`docs/TEST_DOC/`, AC-8); no test reads them. This is a main-Claude
verification run, not a test fixture. Scripts used are in this directory.

Method. Ground truth = every `<w:p>` anywhere under `doc._body`, materialized into
a list (never keyed by `id()` — see `id-key-hazard.md`), text taken as the
concatenation of its `<w:t>` descendants. A paragraph counts as *collected* when
its whitespace-normalized text appears in the whitespace-normalized concatenation
of every collected `Segment`. Normalization is required because
`_p_text_with_breaks` renders `<w:br>`/`<w:tab>` as `\n`, which a raw `<w:t>`
concatenation does not; without it, two paragraphs of `W-RM0901-G6` register as
false "drops".

Source swapped via scratch snapshot + restore, never `git checkout`. SHA verified
identical after each restore.

## Paragraph coverage

| document | paragraphs | missing before | missing after |
|---|---:|---:|---:|
| `EN-P-QC1102-D7 量测系统分析(MSA)程序.docx` | 275 | 65 (7.3% of chars) | **0** |
| `W-RM0901-G6 机器设备保养及维护管理准则.docx` | 523 | 218 (25.2% of chars) | **0** |

Table groups collected rose from 1 → 3 and 1 → 7: the nested tables that were
previously invisible now each ship as their own payload.

## Redundant emission, and the giant-cell hazard

`row.cells` yields a horizontally-merged `<w:tc>` once per spanned column, so
before this change the layout-frame cell was emitted — and translated — several
times over.

| document | | non-empty cells | redundant emits | redundant chars | largest single cell |
|---|---|---:|---:|---:|---:|
| EN-P-QC1102-D7 | before | 52 | 9 | 26,203 | 8,729 |
| EN-P-QC1102-D7 | after | 113 | 23 | 101 | **207** |
| W-RM0901-G6 | before | 36 | 5 | 13,626 | 4,540 |
| W-RM0901-G6 | after | 384 | 87 | 330 | **343** |

The residual "redundant emits" after the change are distinct cells that happen to
share short identical text (headers, `N/A`); BR-81's `(tgt, src_text, col)` tmap
collapses those into one LLM call anyway. The 26,203 → 101 collapse in redundant
*characters* is the merged-cell fix.

The `largest single cell` column is the load-bearing one. `docx_processor.py`
carries a comment recording a live failure: a 4,827-char cell came back from
PANJIT's `gpt-oss:120b` as 370 chars with `ok=True` — over 90% of the content gone
with no trace. Both wire formats accept a complete-but-shortened cell (see
`design.md` §Open Risks); neither can detect it. After the BR-114 frame reroute no
cell on the main path exceeds ~350 characters, because a document-body-sized blob
is no longer a table cell. This is the collection-stage protection design.md
predicted, and it is why the reroute — not a length-ratio guard — was the right
fix here. A general per-cell length-ratio guard remains a separate change.

## Note on the 17.1% / 35.8% figures

`change-request.md` cites 7,359/43,134 (17.1%) and 11,172/31,169 (35.8%). Those
denominators count the pre-change collector's *emitted* characters, which include
the merged cell's duplicate emissions, so they are not a document-text ratio. The
table above is the reproducible measurement and is what the contracts cite.
