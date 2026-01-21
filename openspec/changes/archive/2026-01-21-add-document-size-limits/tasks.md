## 1. Implementation

- [x] 1.1 定義 MAX_SEGMENTS 和 MAX_TEXT_LENGTH 常數
- [x] 1.2 在 `_collect_docx_segments()` 中新增檢查
- [x] 1.3 在 `translate_pptx()` 中新增檢查（PPTX 沒有獨立的收集函式）
- [x] 1.4 在 `translate_xlsx_xls()` 中新增檢查（XLSX 沒有獨立的收集函式）
- [x] 1.5 設計友善的錯誤訊息格式
- [x] 1.6 允許透過設定調整限制值（透過函式參數）
- [x] 1.7 測試超大文件的處理行為

## 2. Implementation Notes

### 新增的常數（第 206-209 行）
```python
MAX_SEGMENTS = 10000      # 最大段落/儲存格數量
MAX_TEXT_LENGTH = 100000  # 最大總字元數
```

### 新增的例外類別和檢查函式（第 372-439 行）
- `DocumentSizeLimitExceeded`: 自訂例外類別，包含詳細的元資料
- `check_document_size_limits()`: 統一的檢查函式

### 修改的函式
1. `_collect_docx_segments()`: 新增 `max_segments` 和 `max_text_length` 參數
2. `translate_pptx()`: 新增 `max_segments` 和 `max_text_length` 參數
3. `translate_xlsx_xls()`: 新增 `max_segments` 和 `max_text_length` 參數

### 測試檔案
- `/home/egg/project/Translate_Tool/test_document_size_limits.py`: 13 個單元測試全部通過
