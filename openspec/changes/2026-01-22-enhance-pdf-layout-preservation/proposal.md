# Change: 升級 PDF 解析引擎並支援版面保留翻譯

## Why

目前 PDF 處理存在以下核心問題：

1. **流式文字提取的局限性**：使用 PyPDF2 的 `extract_text()` 僅能取得純文字流，無法獲取文字的座標位置、字型大小、閱讀順序等關鍵資訊。

2. **閱讀順序錯亂**：多欄排版的 PDF 文件常出現文字區塊讀取順序錯誤，導致翻譯後語句不連貫。

3. **無法區分元素類型**：無法識別頁首、頁尾、標題、正文、表格等不同元素，全部混為一體翻譯。

4. **版面資訊完全丟失**：輸出的 DOCX 檔案無法保留原始 PDF 的版面配置。

5. **不支援掃描型 PDF**：無法處理圖片型或掃描型 PDF 文件。

參考 Tool_OCR 專案的實作，該專案已具備完整的 bbox 座標提取、版面分析、OCR 識別等能力，可作為整合基礎。

## What Changes

### Phase 1: 基礎升級 (低風險高收益)
- 引入 PyMuPDF 取代/增強 PyPDF2
- 實作 bbox 座標提取與閱讀順序排序
- 統一內部座標系並定義排序規則
- 支援頁首/頁尾過濾
- 整合 PyMuPDF 內建表格偵測

### Phase 2: 架構重構
- 建立 `TranslatableDocument` 統一中間層模型
- 解耦解析層、翻譯層、輸出層
- 新增 `layout_mode` 與 `output_format` 輸出參數

### Phase 3: 高級版面保留 (選配)
- 從 Tool_OCR 移植 `TextRegionRenderer` 座標渲染器
- 實作譯文字型動態縮放
- 支援多語言字型 (NotoSans 家族)
- 生成座標定位的 PDF 輸出

### Phase 4: OCR 支援 (按需)
- 引入 `DocumentTypeDetector` 自動判斷 PDF 類型
- 定義 OCR 觸發門檻 (平均每頁可抽取文字數)
- 可選 PaddleOCR 模組支援掃描型 PDF
- GPU/CPU 模式自動切換

## Impact

- **Affected specs**: translator-core
- **Affected code**:
  - `app/backend/processors/pdf_processor.py` - PDF 處理核心
  - `app/backend/processors/orchestrator.py` - 處理流程調度
  - `app/backend/config.py` - 新增配置項
  - 新增 `app/backend/models/translatable_document.py` - 中間層模型
  - 新增 `app/backend/renderers/` - 輸出渲染器模組

- **New dependencies**:
  - Phase 1: `PyMuPDF>=1.23.0`
  - Phase 3: `reportlab>=4.0.0`, NotoSans 字型檔案
  - Phase 4 (可選): `paddleocr>=3.0.0`, `paddlex[ocr]>=3.0.0`, `python-magic>=0.4.27`

## Success Criteria

1. PDF 文字提取包含 bbox 座標資訊
2. 多欄排版 PDF 的閱讀順序正確
3. 頁首/頁尾可被識別並選擇性跳過翻譯
4. 表格區域可被識別
5. (Phase 3+) 可生成保留原始版面的翻譯 PDF
