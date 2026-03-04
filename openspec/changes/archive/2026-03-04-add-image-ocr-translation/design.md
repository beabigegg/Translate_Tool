# Design: Image OCR Translation

## Context
Translate_Tool 目前處理文件中的純文字內容，但跳過所有圖片區塊。許多文件包含重要的圖片文字（截圖、掃描頁、圖表），這些內容需要被翻譯。

### 現有架構
```
Document → Parser → TranslatableDocument → TranslationService → Processor → Renderer → Output
```

### 預期整合點
```
Document → Parser ──────────────────→ TranslatableDocument → ...
              ↓
         ImageExtractor → OCRService → ImageElements (merged into TranslatableDocument)
```

## Goals / Non-Goals

### Goals
- 偵測圖片是否包含文字
- 提取圖片中的文字並翻譯
- 在輸出中呈現翻譯後的圖片
- 支援獨立圖檔翻譯
- 利用現有 PP-OCRv5 模型

### Non-Goals
- 手寫文字識別
- 表格結構精確重建
- 即時 OCR 串流
- 圖片內文字樣式完美還原

---

## Lessons from Tool_OCR (踩坑經驗)

基於 `/home/egg/project/Tool_OCR` 專案的實戰經驗，以下是關鍵教訓：

### 坑 1: GPU 記憶體爆炸
**問題**: 模型累積在 GPU 記憶體，導致 OOM
**解法**:
- 實作 Service Pool 模式控制並發
- 閒置超時卸載 (5 分鐘)
- 緊急清理 (90% 記憶體時觸發)
- CPU Fallback 自動切換

### 坑 2: PDF DPI/縮放問題
**問題**: 錯誤的 DPI 導致偵測失敗
**解法**:
- 固定使用 **150 DPI** (A4 產生 ~1240x1754 像素，最佳範圍)
- 雙向縮放: 超出 1200-2000px 範圍才調整

### 坑 3: 文件方向問題
**問題**: 掃描文件可能旋轉 90°/270°，但元數據顯示 0°
**解法**: 啟用 `use_doc_orientation_classify=True` 自動檢測並校正

### 坑 4: PaddlePaddle 3.x 裝置設定
**問題**: PaddlePaddle 3.x 改為全域設定裝置，不是每個實例
**解法**: 使用 `paddle.device.set_device()` 全域設定，不在 PaddleOCR 初始化時傳入

### 坑 5: 淡線條偵測失敗
**問題**: 淡色邊框/線條無法被 PP-Structure 偵測
**解法**: Layout Preprocessing 服務
- CLAHE 對比度增強 (推薦)
- 銳化處理
- 可選二值化

### 坑 6: DeprecationWarning 被當錯誤
**問題**: PaddleX/PaddleOCR 的棄用警告在某些情況下被當作錯誤
**解法**: 使用 `warnings.catch_warnings()` 抑制

### 坑 7: 表格 Cell 爆炸問題
**問題**: PP-StructureV3 在類似 datasheet 的文件上過度偵測 cell
**解法**: `table_parsing_mode` 設定
- `"conservative"` (推薦預設)
- `"classification_only"` (只分類，不切割)
- `"disabled"` (完全停用)

### 坑 8: 記憶體監控多後端
**問題**: 沒有單一方案適用所有環境
**解法**: 多後端 Fallback 鏈
```python
# 優先順序:
# 1. pynvml (最準確)
# 2. torch.cuda (如果有 PyTorch)
# 3. paddle.device.cuda (如果有 PaddlePaddle)
# 4. none (基本檢查)
```

### 坑 9: Ollama + PaddleOCR VRAM 競爭 ⚠️ 重要
**問題**: 兩個模型無法同時載入 8GB GPU
| 模型 | VRAM 需求 |
|------|-----------|
| TranslateGemma:12b (Ollama) | ~8-10 GB |
| PaddleOCR (偵測+識別) | ~2-4 GB |
| **同時載入** | **12-14 GB** ❌ |

**解法**: 順序處理 + 明確模型生命週期管理
```
[階段 1: OCR] 載入 PaddleOCR → 處理所有圖片 → 卸載 PaddleOCR
     ↓
[階段 2: 翻譯] 載入 Ollama → 翻譯所有文字(含OCR結果) → 卸載 Ollama
     ↓
[階段 3: 渲染] 無需 GPU → 將翻譯結果渲染回圖片
```

**現有優勢**:
- Ollama 已實作 `keep_alive: 0` 立即卸載機制 (`ollama_client.py:unload_model()`)
- 每個 Job 結束後會呼叫 `release_resources()` 釋放 VRAM

---

## VRAM Coordination Strategy (新增)

### 記憶體預算分配

```
8GB GPU 記憶體分配:
├── 系統保留: ~0.5 GB (CUDA overhead)
├── OCR 階段: ~3.5 GB (PaddleOCR det+rec)
├── 翻譯階段: ~7 GB (TranslateGemma:12b)
└── 緩衝區: ~0.5 GB (臨時張量)

關鍵: OCR 和翻譯 **絕不同時載入**
```

### 處理流程 (修訂版)

```
┌─────────────────────────────────────────────────────────────┐
│ Job Start                                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Document Parsing (CPU)                              │
│ - 解析 PDF/DOCX/PPTX                                        │
│ - 提取純文字 → text_elements[]                               │
│ - 提取圖片 → image_list[]                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: OCR Processing (GPU - PaddleOCR)                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 2.1 Load PaddleOCR models (~3.5 GB VRAM)                │ │
│ │ 2.2 For each image in image_list[]:                     │ │
│ │     - Preprocess (scale to 1200-2000px)                 │ │
│ │     - Detect text regions                               │ │
│ │     - Recognize text                                    │ │
│ │     - Store: ocr_results[image_id] = {boxes, texts}     │ │
│ │ 2.3 Unload PaddleOCR models                             │ │
│ │     - paddle.device.cuda.empty_cache()                  │ │
│ │     - gc.collect()                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ⚠️ VRAM 必須完全釋放後才能進入下一階段                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
           [VRAM 檢查點: 確認 < 1GB 使用中]
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Translation (GPU - Ollama)                         │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 3.1 Merge all texts:                                    │ │
│ │     all_texts = text_elements + ocr_extracted_texts     │ │
│ │ 3.2 Load TranslateGemma:12b (~8 GB VRAM)                │ │
│ │ 3.3 Batch translate all_texts                           │ │
│ │ 3.4 Unload Ollama model (keep_alive: 0)                 │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Rendering (CPU)                                    │
│ - 將翻譯文字寫回文件                                          │
│ - 將翻譯文字渲染回圖片 (overlay/side_by_side)                 │
│ - 組裝最終輸出                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Job Complete                                                 │
└─────────────────────────────────────────────────────────────┘
```

### GPU Memory Coordinator (新增元件)

```python
class GPUMemoryCoordinator:
    """協調 OCR 和 Ollama 的 VRAM 使用，確保不會同時載入"""

    _lock = threading.Lock()
    _current_owner: Optional[str] = None  # "ocr" | "ollama" | None

    @contextmanager
    def acquire_for_ocr(self, timeout: float = 300):
        """取得 GPU 給 OCR 使用"""
        with self._lock:
            if self._current_owner == "ollama":
                raise RuntimeError("必須先卸載 Ollama 模型")
            self._current_owner = "ocr"
        try:
            yield
        finally:
            with self._lock:
                self._current_owner = None
                self._force_cleanup()

    @contextmanager
    def acquire_for_ollama(self, timeout: float = 300):
        """取得 GPU 給 Ollama 使用"""
        with self._lock:
            if self._current_owner == "ocr":
                raise RuntimeError("必須先卸載 OCR 模型")
            self._current_owner = "ollama"
        try:
            yield
        finally:
            with self._lock:
                self._current_owner = None

    def _force_cleanup(self):
        """強制清理 GPU 記憶體"""
        gc.collect()
        if paddle.is_compiled_with_cuda():
            paddle.device.cuda.empty_cache()
        # 等待 VRAM 釋放
        time.sleep(1)

    def verify_vram_available(self, required_mb: int) -> bool:
        """驗證有足夠 VRAM"""
        # 使用 pynvml 或 paddle API 檢查
        ...
```

### 降級策略

當 GPU 記憶體不足時的處理方式:

| 情況 | 策略 |
|------|------|
| OCR 時 VRAM 不足 | CPU fallback (慢但可用) |
| Ollama 載入失敗 | 重試 3 次，間隔指數增長 |
| 兩者都失敗 | 純 CPU 模式 (非常慢) |
| 8GB 以下 GPU | 預設使用 CPU OCR |

### 設定參數 (新增)

```python
# === VRAM 協調設定 ===
VRAM_TOTAL_MB = 8192                      # GPU 總記憶體
VRAM_RESERVED_MB = 512                    # 系統保留
VRAM_OCR_BUDGET_MB = 3500                 # OCR 預算
VRAM_OLLAMA_BUDGET_MB = 7000              # Ollama 預算
VRAM_VERIFY_AFTER_UNLOAD = True           # 卸載後驗證
VRAM_CLEANUP_WAIT_SECONDS = 1.0           # 清理等待時間

# === 處理模式 ===
OCR_OLLAMA_SEQUENTIAL = True              # 強制順序處理 (推薦)
ENABLE_CPU_FALLBACK_OCR = True            # OCR 允許 CPU fallback
ENABLE_CPU_FALLBACK_OLLAMA = False        # Ollama CPU 太慢，不建議
```

---

## Decisions

### Decision 1: OCR 引擎選擇 - PaddleOCR
**選擇**: PaddleOCR (PP-OCRv5 server models)

**理由**:
- 已有可用模型在 `/home/egg/.paddlex/official_models/`
- Tool_OCR 專案已驗證可正常運作
- 支援 80+ 語言，與專案多語言需求匹配
- 本地運行，符合使用 Ollama 的架構風格
- PP-OCRv5 準確度高，尤其對 CJK 字符

**替代方案**:
- EasyOCR: 較輕量但準確度略低
- Tesseract: 開源老牌但中文效果差
- Vision LLM: API 費用高，不適合批量

### Decision 2: 圖片文字判斷策略
**選擇**: OCR 偵測結果數量 + 信心度閾值

**流程**:
```python
def has_translatable_text(image) -> bool:
    detection_result = ocr_detector.detect(image)
    # 條件: 至少 1 個文字區域，信心度 > 0.5
    return len(detection_result.boxes) > 0 and detection_result.confidence > 0.5
```

**理由**:
- 不需要額外模型判斷「純圖 vs 文字圖」
- 利用 OCR 偵測階段的副產品
- 可調整閾值控制敏感度

### Decision 3: 輸出渲染模式
**選擇**: 提供多種模式，預設覆蓋模式

| 模式 | 說明 | 適用場景 |
|------|------|----------|
| `overlay` | 在原文字位置覆蓋翻譯 | 簡潔輸出 |
| `side_by_side` | 原圖 + 翻譯圖並排 | 對照校對 |
| `annotation` | 保留原文，翻譯作為標註 | 學習用途 |

**實作**: 類似現有 PDF 的 `LAYOUT_PRESERVATION_MODE`

### Decision 4: 整合架構 (參考 Tool_OCR)
**選擇**: Service Pool 模式 + 懶載入

```
app/backend/
├── services/
│   ├── ocr_service.py          # NEW: OCR 核心服務 (單例+懶載入)
│   └── ocr_service_pool.py     # NEW: 服務池管理並發
├── parsers/
│   └── image_parser.py         # NEW: 獨立圖檔解析
├── processors/
│   └── image_processor.py      # NEW: 圖片翻譯處理
└── renderers/
    └── image_renderer.py       # NEW: 圖片渲染輸出
```

**Service Pool 模式** (從 Tool_OCR 學習):
```python
class OCRServicePool:
    """控制 OCR 服務實例數量，防止 GPU 記憶體爆炸"""
    _instance = None

    def __init__(self, config):
        self.max_services_per_device = 1  # 每 GPU 最多 1 個
        self.max_total_services = 2       # 總共最多 2 個
        self.acquire_timeout = 300.0      # 等待超時 5 分鐘

    @contextmanager
    def acquire_context(self, device_id, task_id):
        """Context manager 確保服務釋放"""
        service = self._acquire(device_id, task_id)
        try:
            yield service
        finally:
            self._release(service)
            self._clear_cache()  # 釋放後清理快取
```

**對現有解析器的修改**:
- `pdf_parser.py`: 提取圖片區塊交給 OCR 服務
- `docx_parser.py`: 提取嵌入圖片
- `pptx_parser.py`: 提取投影片圖片

### Decision 5: 模型載入策略 (參考 Tool_OCR)
**選擇**: 懶載入 + 語言分離 + 超時卸載

```python
class OCRService:
    def __init__(self):
        self.ocr_engines = {}        # 按語言快取: {'ch': engine, 'en': engine}
        self._model_last_used = {}   # 追蹤最後使用時間
        self.idle_timeout = 300      # 5 分鐘閒置後卸載

    def get_ocr_engine(self, lang: str = 'ch') -> PaddleOCR:
        """懶載入指定語言的 OCR 引擎"""
        if lang not in self.ocr_engines:
            # 抑制棄用警告
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                self.ocr_engines[lang] = PaddleOCR(
                    lang=lang,
                    use_textline_orientation=True  # 取代已棄用的 use_angle_cls
                )
        self._model_last_used[lang] = datetime.now()
        return self.ocr_engines[lang]

    def cleanup_idle_models(self):
        """清理閒置超時的模型"""
        now = datetime.now()
        for lang, last_used in list(self._model_last_used.items()):
            if (now - last_used).seconds > self.idle_timeout:
                del self.ocr_engines[lang]
                del self._model_last_used[lang]
                gc.collect()
                paddle.device.cuda.empty_cache()
```

### Decision 6: GPU 裝置與記憶體管理 (參考 Tool_OCR)
**選擇**: 全域裝置設定 + 多層記憶體監控 + CPU Fallback

```python
def configure_device(self):
    """PaddlePaddle 3.x 全域裝置設定"""
    if paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
        paddle.device.set_device(f'gpu:{self.device_id}')
        self.use_gpu = True
    else:
        paddle.device.set_device('cpu')
        self.use_gpu = False

def check_memory_and_fallback(self, required_mb: int = 2500) -> bool:
    """檢查記憶體，不足時自動切換 CPU"""
    if not self.use_gpu:
        return True

    # 檢查可用記憶體
    props = paddle.device.cuda.get_device_properties(self.device_id)
    total = props.total_memory / 1024 / 1024  # MB
    # ... 計算可用記憶體

    if available_mb < required_mb:
        logger.warning(f"GPU 記憶體不足 ({available_mb}MB < {required_mb}MB)，切換至 CPU")
        self.activate_cpu_fallback()
        return True
    return True
```

**記憶體閾值** (從 Tool_OCR):
- 警告閾值: 80%
- 臨界閾值: 95% (開始節流)
- 緊急閾值: 98% (強制清理)

### Decision 7: 圖片縮放策略 (參考 Tool_OCR)
**選擇**: 雙向縮放，目標 1200-2000px

```python
def preprocess_image_for_ocr(image: Image) -> Image:
    """預處理圖片以獲得最佳 OCR 效果"""
    width, height = image.size
    max_dim = max(width, height)
    min_dim = min(width, height)

    # 最佳範圍: 1200-2000px
    if max_dim > 2000:
        # 縮小至 1600px
        scale = 1600 / max_dim
        image = image.resize((int(width * scale), int(height * scale)))
    elif min_dim < 1200:
        # 放大至 1600px
        scale = 1600 / min_dim
        image = image.resize((int(width * scale), int(height * scale)))

    return image
```

**對於 PDF 轉圖片**:
- 固定使用 **150 DPI** (經 Tool_OCR 驗證為最佳)
- A4 紙張 → ~1240x1754 像素，在最佳範圍內

---

## Risks / Trade-offs

| 風險 | 影響 | 緩解措施 (參考 Tool_OCR) |
|------|------|--------------------------|
| GPU 記憶體不足 | OCR 失敗 | Service Pool + CPU Fallback + 閒置卸載 |
| OCR 處理時間長 | 使用者等待 | 批量處理 + 進度回報 + 並發控制 |
| 依賴套件衝突 | 安裝失敗 | 參考 Tool_OCR venv 的驗證版本 |
| 圖片文字遮蓋不完美 | 殘留原文 | 提供手動調整選項 |
| 文件旋轉問題 | 偵測錯誤 | 啟用方向自動分類 |
| 淡線條偵測失敗 | 漏掉邊框 | Layout Preprocessing (CLAHE) |

---

## Migration Plan

### Phase 1: 環境準備
1. 更新 translate-tool conda 環境，參考 Tool_OCR venv 的套件版本
2. 驗證 PP-OCRv5 模型從 `~/.paddlex/official_models/` 載入正常
3. 測試 GPU/CPU fallback 機制

### Phase 2: 核心功能
1. 實作 `ocr_service.py` (含 Service Pool、懶載入、記憶體監控)
2. 實作 `image_parser.py` + `image_processor.py`
3. 實作 `image_renderer.py`

### Phase 3: 整合現有流程
1. 修改 PDF/DOCX/PPTX 解析器提取圖片
2. 整合到翻譯管道
3. 新增設定選項

### Phase 4: 測試與調優
1. 單元測試 (含記憶體壓力測試)
2. 整合測試
3. 效能調優

### Rollback
- 設定 `ENABLE_IMAGE_OCR = False` 可完全停用功能
- 不影響現有文字翻譯流程

---

## Configuration Reference (參考 Tool_OCR)

```python
# === OCR 核心設定 ===
ENABLE_IMAGE_OCR = True                    # 總開關
OCR_MODEL_PATH = "~/.paddlex/official_models"
OCR_CONFIDENCE_THRESHOLD = 0.5             # 信心度閾值

# === GPU/記憶體設定 ===
OCR_USE_GPU = True                         # 優先使用 GPU
OCR_GPU_DEVICE_ID = 0
OCR_GPU_MEMORY_LIMIT_MB = 6144             # 6GB 限制
OCR_ENABLE_CPU_FALLBACK = True             # 自動切換 CPU
OCR_MEMORY_WARNING_THRESHOLD = 0.80
OCR_MEMORY_CRITICAL_THRESHOLD = 0.95

# === 模型管理 ===
OCR_ENABLE_LAZY_LOADING = True
OCR_MODEL_IDLE_TIMEOUT_SECONDS = 300       # 5 分鐘閒置卸載

# === Service Pool ===
OCR_MAX_SERVICES_PER_DEVICE = 1
OCR_MAX_TOTAL_SERVICES = 2
OCR_SERVICE_ACQUIRE_TIMEOUT = 300.0

# === 圖片處理 ===
OCR_IMAGE_SCALING_ENABLED = True
OCR_IMAGE_SCALING_MIN_DIMENSION = 1200
OCR_IMAGE_SCALING_MAX_DIMENSION = 2000
OCR_IMAGE_SCALING_TARGET = 1600
OCR_PDF_DPI = 150                          # PDF 轉圖片 DPI

# === 文件處理 ===
OCR_USE_DOC_ORIENTATION_CLASSIFY = True    # 自動旋轉校正
OCR_USE_TEXTLINE_ORIENTATION = True

# === 輸出模式 ===
OCR_OUTPUT_MODE = "overlay"                # overlay | side_by_side | annotation
```

---

## Open Questions
1. ~~使用 PaddleOCR 還是 PaddleX 的 API?~~ → 使用 PaddleOCR，PaddleX 作為依賴
2. ~~是否需要支援批量圖片檔案上傳?~~ → 支援，複用現有多檔上傳機制
3. ~~翻譯後圖片的格式?~~ → 與輸入相同或統一為 PNG
4. 是否需要 Layout Preprocessing (CLAHE)? → 先不加，有需要再開啟
