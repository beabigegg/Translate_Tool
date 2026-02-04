# Change: Add Image OCR Translation Capability

## Why
目前專案僅支援文字型內容的翻譯，圖片中的文字（如截圖、掃描文件、圖表標籤）會被跳過。使用者需要翻譯嵌入在文件中的圖片文字，或直接翻譯圖片檔案。

## What Changes
- **新增 OCR 引擎整合**：導入 PaddleOCR (PP-OCRv5) 進行文字偵測與識別
- **新增圖片解析器**：`image_parser.py` 處理獨立圖檔 (PNG, JPG, TIFF, BMP)
- **新增圖片處理器**：`image_processor.py` 協調 OCR + 翻譯 + 渲染流程
- **修改現有解析器**：PDF/DOCX/PPTX/XLSX 解析器增加圖片提取邏輯
- **新增圖片渲染器**：在原圖上覆蓋翻譯文字或生成並排對照圖
- **環境更新**：新增 paddlepaddle-gpu、paddleocr、paddlex 依賴

## Impact
- Affected specs: `translation-backend` (新增圖片處理流程)
- Affected code:
  - `app/backend/parsers/` - 新增 image_parser.py，修改現有解析器
  - `app/backend/processors/` - 新增 image_processor.py
  - `app/backend/services/` - 新增 ocr_service.py
  - `app/backend/renderers/` - 新增 image_renderer.py
  - `app/backend/config.py` - 新增 OCR 相關設定
  - `requirements.txt` 或環境設定檔 - 新增依賴

## Dependencies
### 新增套件
參考 Tool_OCR 專案 (`/home/egg/project/Tool_OCR/venv`) 已驗證可用的版本：
- `paddlepaddle-gpu==3.2.0` (從 PaddlePaddle 官方源安裝)
- `paddleocr>=3.3.0`
- `paddlex[ocr]>=3.3.0`
- `opencv-python>=4.8.0` (圖片處理)
- `pillow>=10.0.0` (圖片 I/O)

### 預載模型
使用已下載的模型 (`/home/egg/.paddlex/official_models/`)：
- `PP-OCRv5_server_det` - 文字偵測模型
- `PP-OCRv5_server_rec` - 文字識別模型
- `PP-LCNet_x1_0_doc_ori` - 文件方向分類 (可選)

## Out of Scope
- 手寫文字識別 (需要特殊模型)
- 表格結構重建 (複雜，可作為後續功能)
- 即時 OCR 預覽 (效能考量)
