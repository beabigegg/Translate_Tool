# Change Request

## Original Request

P2-2（改善計畫 §4.1）：把現有 `app/backend/models/translatable_document.py`（已有 `ElementType` / `BoundingBox` / `TranslatableDocument` 雛形）成熟化為仿 BabelDOC 的 IR 中介層，作為「解析 → 翻譯 → 渲染」三段解耦的單一資料模型：
1. 擴充 `ElementType`，加入 layout 偵測所需的區域型別（至少 `TABLE` / `FIGURE` / `FORMULA` / `LIST`，現有僅到 `TABLE_CELL` 等文字級型別）。
2. 在 IR 上明確表示 `reading_order`，取代 parser 內 `round(y0,10pt)` 分桶啟發式（痛點 9 的資料面基礎）。
3. IR 可完整序列化 / 反序列化：bbox + 字型 metadata + element type + reading order，使「不重解析即可重渲染、不重渲染即可換 MT 引擎」成立。
4. 建立黃金樣本回歸測試集（PDF/DOCX/PPTX 各 N 份）與新舊路徑雙跑比對框架，供整個 P2 版面軌道（layout/renderer/text-expansion/table）共用。

## Business / User Goal

讓解析、翻譯、渲染三段以單一 IR 解耦，換 MT 引擎或換渲染器都不需動其他兩段，並讓後續 DocLayout-YOLO 接入有明確的資料落點。黃金樣本回歸框架是整個 P2 高風險版面重構的安全網。

## Non-goals

- 不在本 change 接入 DocLayout-YOLO（`p2-layout-detection`）。
- 不在本 change 收斂渲染器（`p2-renderer-convergence`）。
- 不改變翻譯主路徑行為與 API 介面。
- 不處理 OCR / 公式辨識（P3）。

## Constraints

- 須先讀現況 `models/translatable_document.py`（320 行）與 `renderers/base.py`（已有 `BaseRenderer` / `RenderMode`），以擴充而非重寫為原則，維持既有欄位與 `to_dict` 相容。
- 序列化格式需向下相容既有呼叫端（parsers / renderers / processors）。
- 黃金樣本回歸須可在 CI gate 內執行（離線、不需網路 / GPU）。

## Known Context

- IR 模型：`app/backend/models/translatable_document.py`
- 渲染抽象：`app/backend/renderers/base.py`（`BaseRenderer`, `RenderMode = {INLINE, SIDE_BY_SIDE, OVERLAY}`）
- PDF 解析現況：`app/backend/parsers/pdf_parser.py`（415 行，`round(y0,10pt)` 閱讀順序）
- 改善計畫 §4.1、§5.1 風險表「IR 重構大改 → 回歸風險」緩解策略

## Open Questions

- 黃金樣本集放置位置與大小上限（建議 `tests/fixtures/golden/`，每格式 3–5 份代表性文件）。

## Requested Delivery Date / Priority

P2 軌道 A 基石，最高優先。`p2-layout-detection` / `p2-renderer-convergence` 依賴本 change。
