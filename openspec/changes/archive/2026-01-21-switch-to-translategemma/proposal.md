# Change: 切換翻譯後端至本地 TranslateGemma:12b

## Why
目前翻譯功能依賴外部 Dify API，存在以下問題：
1. **網路依賴**：需要穩定的網路連線
2. **API 費用**：每次翻譯都需要 API 呼叫成本
3. **隱私顧慮**：文件內容需上傳至第三方服務
4. **延遲問題**：網路延遲影響翻譯速度

Google 新發布的 TranslateGemma:12b 模型提供高品質的本地翻譯能力，支援 55+ 語言，效能超越 Gemma 3 27B 基準模型。

## What Changes
- **新增 Ollama 整合**：安裝並配置 Ollama 服務運行 TranslateGemma:12b
- **建立專用 Conda 環境**：Python 3.11.14，善用現有 conda 環境的套件共用
- **更新預設後端**：將 Ollama + TranslateGemma 設為預設翻譯後端
- **調整 Prompt 格式**：採用 TranslateGemma 專用的 Prompt 模板
- **保留 Dify 支援**：作為備選方案，現有 Dify 功能不移除

## Impact
- Affected specs: translation-backend (新建)
- Affected code:
  - `document_translator_gui_with_backend.py` - OllamaClient 類別、prompt 建構
  - `api.txt` - 可能需要更新配置格式
- 新增依賴：
  - Ollama 服務（系統層級）
  - TranslateGemma:12b 模型（約 8GB）

## 風險評估
| 風險 | 影響 | 緩解措施 |
|------|------|----------|
| GPU 記憶體不足 | 模型無法運行 | 提供 CPU-only 降級選項 |
| 翻譯品質差異 | 部分語言翻譯不如 Dify | 保留 Dify 作為備選 |
| Ollama 服務不穩定 | 翻譯中斷 | 實作健康檢查和自動重試 |

## Conda 環境套件共用分析

### 現有環境
| 環境 | Python 版本 | 可共用套件 |
|------|-------------|-----------|
| ccr | 3.11.14 | requests, openpyxl, python-docx, libsqlite |
| iqkg | 3.11.14 | requests, openpyxl, python-docx, libsqlite |
| pjctrl | 3.11.x | pypdf2, libsqlite |
| base | 3.13.x | requests, sqlite |

### 建議：使用 ccr 環境（或克隆）
- Python 版本完全符合需求 (3.11.14)
- 已有 `requests`、`openpyxl`、`python-docx` 等核心依賴
- 僅需額外安裝：`python-pptx`、`PyPDF2`、`blingfire`/`pysbd`

### 缺少的套件
需要安裝到新環境或現有環境：
- `python-pptx` - PowerPoint 處理
- `PyPDF2` - PDF 讀取（pjctrl 有）
- `blingfire` 或 `pysbd` - 句子分割（可選）
