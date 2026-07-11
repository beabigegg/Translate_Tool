# Evidence: real-document body-textbox fold eliminated

Measured on the two real `.docx` files (untracked `docs/TEST_DOC/`, read by no test).
Script: `evidence/probe_paracell_delta.py`. Source swapped via scratch snapshot +
restore, never `git checkout`; sha verified identical after restore.

## Method note

A first probe counted "textbox text folded into its host paragraph" but had a blind
spot: when a textbox sits in a paragraph with NO other text (the common real case),
the host paragraph's own text is empty, so a host-match guard skipped it. And a naive
substring probe over-counts coincidental matches (the textbox strings `判定`, `OK`,
`年度计划` also occur as genuine independent content in unrelated paragraphs). The
clean, coincidence-free measure is the **total para/cell character delta**: coincidental
content exists identically before and after, so the delta is purely the eliminated fold.

## Result

| document | textboxes | para/cell chars before | after | delta |
|---|---:|---:|---:|---:|
| `EN-P-QC1102-D7 量测系统分析(MSA)程序.docx` | 10 (51 txbx chars) | 10177 | 10124 | **−53** |
| `W-RM0901-G6 机器设备保养及维护管理准则.docx` | 0 | 7715 | 7715 | **0** |

The −53 on the textbox-bearing document ≈ the 51 characters of textbox text (plus a
couple of whitespace/join chars) that were previously FOLDED into the para/cell stream
and translated a second time; they are now collected exactly once, via the dedicated
`_txbx_iter_texts` path (`txbx_chars` = 51, unchanged). The textbox-FREE document is
byte-identical (0 delta), confirming AC-5. Unit tests prove the per-segment behavior
precisely on synthetic fixtures.
