# Change Request

## Original Request

User (verbatim, Chinese), across two turns:

> 「那如果是之前遇到的, 文件中有表中表, 外表是一個大框架, 包覆內文, 內表才是真實的表格, 會如何處理?」
>
> 「非急迫. 你可以先處理好json問題, 再繼續處理表中表問題。表中表的文件你之後可以拿test_doc中的檔案去測試。我的希望是使用/loop模式, 你就把這兩個都做到沒問題為止」

The user described the exact document shape from memory and asked how it is
handled. Nobody had checked. It is not handled at all. The JSON wire-format
change (`json-structured-translation-io`) has since merged, which is what makes
this fix tractable.

Restated in the three required elements:

1. **Affected surface** — the `<w:tbl>` branch of the block walk in
   `app/backend/processors/docx_processor.py` (~L261-285), and whatever it feeds:
   the `cell` segment type, the BR-81 dedup key, and the whole-table translation
   path.
2. **Desired behavior** — inner-table cells are collected and translated as their
   own table payload; an outer cell that is a layout frame contributes its direct
   paragraphs to the body path instead of being sent as one giant table cell; a
   merged cell is translated once, not once per spanned column.
3. **Observable success criterion** — re-running the two `docs/TEST_DOC/` files
   collects 100% of their text (0 chars silently dropped, asserted by comparing
   collected-segment characters against a full recursive walk); the 4,827-char
   merged body cell is translated exactly once; existing single-level table tests
   stay green.

## Business / User Goal

Silent partial translation. The output document is produced without a crash or a
warning, and a large fraction of it is still in the source language.

## Known Context

All measured on `main` after `json-structured-translation-io` merged, against the
user's real files. `docs/TEST_DOC/` is untracked and MUST stay untracked.

- `docx_processor.py` walks each `<w:tbl>` and reads only `cell.paragraphs` — the
  cell's **direct** paragraphs. A nested table hangs off `cell.tables`, which the
  file never reads: `grep -c "cell.tables"` returns **0**.
- Measured loss:

  | document | dropped | total | share | nested tables |
  |---|---:|---:|---:|---:|
  | `EN-P-QC1102-D7 量测系统分析(MSA)程序.docx` | 7,359 | 43,134 | 17.1% | 8 |
  | `W-RM0901-G6 机器设备保养及维护管理准则.docx` | 11,172 | 31,169 | 35.8% | 24 |

- **The behaviour is inverted.** In `W-RM0901-G6` the single top-level table is a
  page **layout frame**: rows 0-11 are a revision history, and row 12 is a merged
  cell spanning all four columns holding **111 paragraphs (4,827 chars — the entire
  document body)** plus **6 nested real tables**. Today that 4,827-char blob is sent
  through the whole-table translation path as ONE table cell, while the 6 real
  tables inside it are dropped entirely.
- **Merged cells are translated once per spanned column.** `row.cells` yields a
  merged cell once per column it spans, and BR-81's dedup key is `(tgt, text, col)`,
  so `col` differs and the duplicates survive dedup. That one merged cell emits 4
  identical segments: **52 cell segments for 49 distinct `<w:tc>` elements** in that
  table, and its 4,827 chars are translated **4 times**.
- Verified by executing the processor's own walk logic against a constructed
  minimal `.docx` (outer 1×1 frame + inner 2×2 table): the walk saw exactly one
  segment, `'OUTER-FRAME-TEXT'`; all four inner cells were invisible.
- No contract mentions nested tables. `.pptx` and `.xlsx` have no nesting surface.
- The BR-109 document-context sampler in `orchestrator.py` also walks only
  `doc.tables` (top level), so a nested-only document samples thin. That affects the
  one-sentence summary, not the output text.

## Non-goals

- **Out of scope:** the critique-loop call volume; the residual double LibreOffice
  `.xls` conversion; body-envelope batching; BR-108's reply-dominant meta-refusal
  redesign (all four are tracked follow-ups from earlier changes).
- **Out of scope:** `.pptx` and `.xlsx` — neither has a nesting surface.
- No change to the JSON wire format itself (data-shape 0.18.0), to BR-111/BR-112,
  or to the `JSON_STRUCTURED_TRANSLATION_ENABLED` kill switch.

## Constraints

- The coordinate-carrying JSON cell list (data-shape 0.18.0) has **no shape
  constraint**, so a nested table can be sent as its own payload. The old pipe-grid
  demanded a single `num_rows × num_cols` matrix that a nested table cannot occupy —
  which is why this fix was not tractable before. The frozen legacy pipe-grid path
  (reachable at `JSON_STRUCTURED_TRANSLATION_ENABLED=0`) must keep working, so
  whatever is done here must degrade sanely when the flag is off.
- Acceptance must be asserted on **collected segment content** and the real
  translated output, never on an internal attribute. Four prior changes in this
  subsystem shipped or nearly shipped a defect that a boundary assertion would have
  caught.
- Deduplication is a contract surface: BR-81 defines the `tmap` key. Changing how a
  merged cell is keyed requires updating that rule in the same change.
- `docs/TEST_DOC/` holds the user's real documents. It is untracked and must remain
  so; no test may depend on it being present.

## Open Questions

- Is an outer cell "a layout frame" a decidable property, or a heuristic? Candidate
  signals: the cell spans the full table width, contains a nested table, and holds
  many direct paragraphs. Getting this wrong in either direction is bad — a real
  table cell routed to the body path loses its row context; a layout frame left on
  the table path keeps the current defect. `design.md` must decide, and must say
  what happens when the signals disagree.
- Should nesting recurse arbitrarily deep, or one level? The user's documents nest
  one level. Unbounded recursion needs a depth guard.
- How is a nested table's identity carried? The existing `table_id` is
  `id(child_element)`. Coordinates are per-table, so an inner table needs its own
  `table_id` and its own payload rather than being merged into the outer table's
  coordinate space.
- Does fixing the merged-cell duplication change BR-81's key, or is it enough to
  deduplicate on the underlying `<w:tc>` element before emitting segments?

## Requested Delivery Date / Priority

The user deprioritized it relative to the JSON change ("非急迫"), which has now
merged. This is the last item in the queue. The 35.8% figure argues it matters more
to daily use than anything shipped in the last four changes.
