# Change Request

## Original Request

P1-8（improvement-plan.md §4.1）：`renderers/pdf_generator.py` 的 `_insert_text_in_rect` 每次插字都從磁碟讀取字型檔，造成重複 I/O。在 module 層級加入 LRU 快取（font buffer cache），讓相同字型路徑只讀磁碟一次，後續呼叫從記憶體取得。成功標準：測試可驗證相同字型第二次呼叫不觸發磁碟 I/O；全套測試通過。

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
